"""Microphone capture with energy-based endpointing (no extra VAD dep)."""
from __future__ import annotations

import time

import numpy as np

from config.settings import MicSettings
from utils.exceptions import ModuleInitializationError
from utils.logger import get_logger


class Microphone:
    def __init__(self, cfg: MicSettings) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.voice.mic")
        self._sd = None
        self._blocksize = int(cfg.sample_rate * cfg.frame_ms / 1000)

    def initialize(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:  # noqa: BLE001
            raise ModuleInitializationError(
                "sounddevice not installed. Run: pip install sounddevice numpy"
            ) from exc
        self._sd = sd
        self.log.info("Microphone ready (rate=%d, block=%d).", self.cfg.sample_rate, self._blocksize)

    @staticmethod
    def _rms(frame: np.ndarray) -> float:
        if frame.size == 0:
            return 0.0
        f = frame.astype(np.float64)
        return float(np.sqrt(np.mean(f * f)))

    def _open_stream(self):
        return self._sd.InputStream(
            samplerate=self.cfg.sample_rate,
            channels=self.cfg.channels,
            dtype="float32",
            blocksize=self._blocksize,
        )

    def _calibrate(self, stream) -> float:
        frames = max(1, int(self.cfg.calibrate_seconds * 1000 / self.cfg.frame_ms))
        vals = []
        for _ in range(frames):
            data, _ = stream.read(self._blocksize)
            vals.append(self._rms(data[:, 0]))
        ambient = sorted(vals)[len(vals) // 2] if vals else 0.0
        threshold = max(self.cfg.silence_threshold, ambient * self.cfg.calibration_multiplier)
        self.log.debug("Calibrated threshold=%.5f (ambient=%.5f).", threshold, ambient)
        return threshold

    def record_utterance(self) -> np.ndarray:
        """Record until the user starts, then stops, speaking. Returns float32 mono."""
        if self._sd is None:
            raise ModuleInitializationError("Microphone.initialize() not called.")
        preroll = max(1, int(self.cfg.preroll_ms / self.cfg.frame_ms))
        hangover = max(1, int(self.cfg.silence_hangover_s * 1000 / self.cfg.frame_ms))
        max_frames = int(self.cfg.max_utterance_s * 1000 / self.cfg.frame_ms)
        start_deadline = time.monotonic() + self.cfg.start_timeout_s

        collected: list[np.ndarray] = []
        ring: list[np.ndarray] = []
        started = False
        silent = 0
        spoken_frames = 0

        with self._open_stream() as stream:
            threshold = self._calibrate(stream)
            while True:
                data, _ = stream.read(self._blocksize)
                mono = data[:, 0].copy()
                level = self._rms(mono)
                if not started:
                    ring.append(mono)
                    if len(ring) > preroll:
                        ring.pop(0)
                    if level >= threshold:
                        started = True
                        collected.extend(ring)
                        collected.append(mono)
                    elif time.monotonic() > start_deadline:
                        self.log.info("No speech within timeout.")
                        return np.zeros(0, dtype=np.float32)
                else:
                    collected.append(mono)
                    spoken_frames += 1
                    if level < threshold:
                        silent += 1
                        if silent >= hangover:
                            break
                    else:
                        silent = 0
                    if spoken_frames >= max_frames:
                        self.log.info("Max utterance length reached.")
                        break

        if not collected:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(collected).astype(np.float32)

    def record_fixed(self, seconds: float) -> np.ndarray:
        """Fixed-length capture used by the wake-word poller."""
        if self._sd is None:
            raise ModuleInitializationError("Microphone.initialize() not called.")
        n = int(seconds * self.cfg.sample_rate)
        data = self._sd.rec(n, samplerate=self.cfg.sample_rate,
                            channels=self.cfg.channels, dtype="float32")
        self._sd.wait()
        return data[:, 0].astype(np.float32)

    def shutdown(self) -> None:
        self._sd = None
