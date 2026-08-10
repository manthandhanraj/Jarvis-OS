"""Offline wake word via a callback-driven rolling-window STT keyword spotter.

History matters here, because two earlier designs both failed:

1. Fixed 2s clips: the microphone was closed while Whisper transcribed (~1-2s on
   CPU), so about half of all speech landed in a dead gap and the wake word had
   to be repeated many times.
2. A reader thread calling stream.read(): on Windows PortAudio needs COM
   initialised on the calling thread, and without it the reads returned pure
   silence (rms=0.0000) even though the microphone itself was fine.

So capture now uses sounddevice's callback mode. PortAudio invokes the callback
from the audio thread it owns and prepares itself, which sidesteps the COM
problem entirely and keeps filling the buffer while Whisper runs on the main
thread -- gapless capture with no threading of our own.

Matching is deliberately lenient (exact phrase, substring hints, then a fuzzy
word match) because a small model hears 'jarvis' as 'javis', 'jervis', 'service'.
Level and transcript are logged at INFO: tuning a wake word blind is impossible.
"""
from __future__ import annotations

import difflib
import threading
import time
from collections import deque

import numpy as np

from config.settings import WakeWordSettings
from utils.logger import get_logger
from utils.text import normalize
from voice.audio.microphone import Microphone
from voice.stt.base import STTEngine
from voice.wakeword.base import WakeWordDetector

# Words a mishearing of "jarvis" tends to collapse to.
_CORE_WORDS = ("jarvis", "jaarvis", "jervis", "javis", "jarvez", "service", "harvest")
# Cheap substring signals that survive most mistranscriptions.
_HINTS = ("jarv", "arvi", "arvis", "jervi")
_FUZZY_CUTOFF = 0.70

_MIN_WINDOW_S = 2.5     # shorter windows give Whisper too little context
_HOP_S = 0.6            # how often a fresh snapshot is transcribed
_ENERGY_FLOOR = 0.0025  # absolute RMS floor; below this the room is truly quiet
_KEEP_TAIL_S = 0.9      # audio retained after a miss so windows overlap


class KeywordWakeWord(WakeWordDetector):
    def __init__(self, mic: Microphone, stt: STTEngine, cfg: WakeWordSettings) -> None:
        self.mic = mic
        self.stt = stt
        self.cfg = cfg
        self.log = get_logger("jarvis.voice.wake")
        self._phrases = tuple(normalize(p) for p in cfg.phrases)
        self._window_s = max(_MIN_WINDOW_S, float(cfg.window_s))
        self._lock = threading.Lock()
        self._buffer: deque[np.ndarray] = deque()
        self._max_blocks = 1
        self._keep_blocks = 1
        self._status_logged = False

    # ---- matching ----------------------------------------------------------

    def _heard(self, text: str) -> bool:
        t = normalize(text)
        if not t:
            return False
        if any(p and p in t for p in self._phrases):
            return True
        if any(h in t for h in _HINTS):
            return True
        for word in t.split():
            if len(word) < 4:
                continue
            for core in _CORE_WORDS:
                if difflib.SequenceMatcher(None, word, core).ratio() >= _FUZZY_CUTOFF:
                    self.log.info("Fuzzy wake match: %r ~ %r", word, core)
                    return True
        return False

    # ---- capture -----------------------------------------------------------

    def _callback(self, indata, _frames, _time_info, status) -> None:
        """Called by PortAudio's own audio thread; must stay fast and never raise."""
        if status and not self._status_logged:
            self.log.warning("Audio input status: %s", status)
            self._status_logged = True
        mono = np.asarray(indata[:, 0], dtype=np.float32).copy()
        with self._lock:
            self._buffer.append(mono)
            while len(self._buffer) > self._max_blocks:
                self._buffer.popleft()

    def _snapshot(self) -> np.ndarray:
        with self._lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(list(self._buffer)).astype(np.float32)

    def _trim_to_tail(self) -> None:
        """Drop consumed audio but keep a short tail so windows overlap."""
        with self._lock:
            while len(self._buffer) > self._keep_blocks:
                self._buffer.popleft()

    def _clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def _log_input_device(self, sd) -> None:
        try:
            info = sd.query_devices(kind="input")
            self.log.info(
                "Wake input device: %s (channels=%s, default_rate=%s)",
                info.get("name"), info.get("max_input_channels"),
                info.get("default_samplerate"),
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning("Could not query input device: %s", exc)

    # ---- main loop ---------------------------------------------------------

    def wait_for_wake(self) -> bool:
        sd = self.mic._sd
        if sd is None:
            raise RuntimeError("Microphone.initialize() not called before wake loop.")

        rate = self.mic.cfg.sample_rate
        block = self.mic._blocksize
        self._max_blocks = max(1, int(self._window_s * rate / block))
        self._keep_blocks = max(1, int(_KEEP_TAIL_S * rate / block))
        min_samples = int(1.0 * rate)

        self._clear()
        self._status_logged = False
        self._log_input_device(sd)
        self.log.info(
            "Waiting for wake word (rolling %.1fs window, floor=%.4f) ...",
            self._window_s, _ENERGY_FLOOR,
        )

        stream = sd.InputStream(
            samplerate=rate,
            channels=self.mic.cfg.channels,
            dtype="float32",
            blocksize=block,
            callback=self._callback,
        )
        quiet_logged = 0.0
        with stream:
            time.sleep(min(self._window_s, 1.5))  # let the buffer fill once
            try:
                while True:
                    time.sleep(_HOP_S)
                    audio = self._snapshot()
                    if audio.size < min_samples:
                        continue

                    level = self.mic._rms(audio)
                    if level < _ENERGY_FLOOR:
                        now = time.monotonic()
                        if now - quiet_logged > 5.0:   # heartbeat, not spam
                            self.log.info("Wake window quiet (rms=%.4f).", level)
                            quiet_logged = now
                        self._trim_to_tail()
                        continue

                    text = self.stt.transcribe(audio, rate)
                    self.log.info("Wake window rms=%.4f heard=%r", level, text)
                    if self._heard(text):
                        self.log.info("Wake word detected.")
                        return True
                    self._trim_to_tail()
            finally:
                self._clear()
