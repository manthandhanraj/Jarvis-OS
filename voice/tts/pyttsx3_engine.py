"""Layered offline TTS. Piper (neural) -> SAPI5 -> pyttsx3.

The class is still named Pyttsx3TTS so no other module needs editing, but
pyttsx3 is now only the last resort:

* Piper is a small VITS model run through ONNX Runtime. It sounds close to a
  real person, runs offline on CPU, and is the reason this file exists -- the
  stock Windows "David" voice is what made JARVIS sound robotic.
* SAPI5 (comtypes SpVoice) is the fallback: robotic but always present, and
  synchronous, unlike pyttsx3's driver loop.
* pyttsx3 gets a FRESH engine per call, because reusing one engine across a
  long-running session loop makes SAPI's event loop stall and go silent.

Piper models are looked up on disk rather than downloaded at runtime; drop the
.onnx (plus its .onnx.json) anywhere under models/piper and it is picked up.
Set JARVIS_PIPER_MODEL to point at a specific file to override the search.
"""
from __future__ import annotations

import io
import os
import wave
from pathlib import Path

import numpy as np

from config.settings import TTSSettings
from utils.exceptions import ModuleInitializationError
from utils.logger import get_logger
from voice.tts.base import TTSEngine

_SVSF_DEFAULT = 0  # SAPI: speak synchronously (blocks until done)

# Searched in order, relative to the project root and the working directory.
_MODEL_DIRS = ("models/piper", "models", "voices", ".")


def _wpm_to_sapi_rate(wpm: int) -> int:
    """pyttsx3 uses words-per-minute (~200 default); SAPI uses -10..10."""
    return max(-10, min(10, round((wpm - 200) / 20)))


def _wpm_to_length_scale(wpm: int) -> float:
    """Piper's length_scale is a duration multiplier: >1 slower, <1 faster."""
    return max(0.6, min(1.8, 200.0 / max(60, wpm)))


class Pyttsx3TTS(TTSEngine):
    def __init__(self, cfg: TTSSettings) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.voice.tts")
        self._backend = "none"
        self._voice = None        # SAPI SpVoice COM object
        self._piper = None        # PiperVoice
        self._piper_cfg = None    # SynthesisConfig or None
        self._sd = None           # sounddevice module, for Piper playback

    # ---- init --------------------------------------------------------------

    def initialize(self) -> None:
        if self._init_piper():
            self._backend = "piper"
            return
        if self._init_sapi():
            self._backend = "sapi"
            self.log.info("TTS ready (SAPI5, rate=%d).", self.cfg.rate)
            return
        if self._probe_pyttsx():
            self._backend = "pyttsx3"
            self.log.info("TTS ready (pyttsx3 fallback, rate=%d).", self.cfg.rate)
            return
        raise ModuleInitializationError(
            "No TTS backend available. Install piper-tts, comtypes or pyttsx3."
        )

    # ---- piper -------------------------------------------------------------

    def _find_model(self) -> Path | None:
        override = os.environ.get("JARVIS_PIPER_MODEL", "").strip()
        if override:
            path = Path(override)
            return path if path.is_file() else None

        hint = (self.cfg.voice_hint or "").lower()
        roots = {Path.cwd(), Path(__file__).resolve().parents[2]}
        found: list[Path] = []
        for root in roots:
            for rel in _MODEL_DIRS:
                directory = root / rel
                if directory.is_dir():
                    found.extend(sorted(directory.glob("*.onnx")))
        if not found:
            return None
        if hint:
            for path in found:
                if hint in path.name.lower():
                    return path
        return found[0]

    def _init_piper(self) -> bool:
        model = self._find_model()
        if model is None:
            self.log.info("No Piper voice model found; using a system voice.")
            return False
        try:
            import sounddevice as sd
            from piper import PiperVoice

            voice = PiperVoice.load(str(model))
            syn_cfg = None
            try:  # SynthesisConfig is optional across Piper versions
                from piper import SynthesisConfig
                syn_cfg = SynthesisConfig(
                    volume=max(0.0, min(1.0, self.cfg.volume)),
                    length_scale=_wpm_to_length_scale(self.cfg.rate),
                )
            except Exception:  # noqa: BLE001
                self.log.debug("Piper SynthesisConfig unavailable; using defaults.")

            self._piper = voice
            self._piper_cfg = syn_cfg
            self._sd = sd
            self.log.info("TTS ready (Piper neural voice '%s').", model.stem)
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.warning("Piper unavailable (%s). Falling back to a system voice.", exc)
            self._piper = None
            return False

    def _piper_wav_bytes(self, text: str) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            if self._piper_cfg is not None:
                self._piper.synthesize_wav(text, wav_file, syn_config=self._piper_cfg)
            else:
                self._piper.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    def _speak_piper(self, text: str) -> bool:
        try:
            raw = self._piper_wav_bytes(text)
            with wave.open(io.BytesIO(raw), "rb") as wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                frames = wav_file.readframes(wav_file.getnframes())
            if width != 2:
                raise RuntimeError(f"unexpected sample width {width}")
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if channels > 1:
                samples = samples.reshape(-1, channels)
            self._sd.play(samples, rate)
            self._sd.wait()
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.warning("Piper speak failed (%s). Falling back to a system voice.", exc)
            self._piper = None
            if self._init_sapi():
                self._backend = "sapi"
            else:
                self._backend = "pyttsx3"
            return False

    # ---- sapi --------------------------------------------------------------

    def _init_sapi(self) -> bool:
        try:
            import comtypes
            import comtypes.client
            try:
                comtypes.CoInitialize()
            except OSError:
                pass
            voice = comtypes.client.CreateObject("SAPI.SpVoice")
            voice.Rate = _wpm_to_sapi_rate(self.cfg.rate)
            voice.Volume = max(0, min(100, round(self.cfg.volume * 100)))
            self._select_sapi_voice(voice)
            self._voice = voice
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.warning("SAPI TTS unavailable (%s).", exc)
            self._voice = None
            return False

    def _select_sapi_voice(self, voice) -> None:
        hint = (self.cfg.voice_hint or "").lower()
        if not hint:
            return
        try:
            tokens = voice.GetVoices()
            for i in range(tokens.Count):
                token = tokens.Item(i)
                if hint in token.GetDescription().lower():
                    voice.Voice = token
                    self.log.info("Selected voice: %s", token.GetDescription())
                    return
        except Exception as exc:  # noqa: BLE001
            self.log.debug("SAPI voice selection skipped: %s", exc)

    def _speak_sapi(self, text: str) -> bool:
        try:
            if self._voice is None and not self._init_sapi():
                return False
            self._voice.Speak(text, _SVSF_DEFAULT)
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.warning("SAPI speak failed (%s). Falling back to pyttsx3.", exc)
            self._voice = None
            return False

    # ---- pyttsx3 -----------------------------------------------------------

    @staticmethod
    def _probe_pyttsx() -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.stop()
            return True
        except Exception:  # noqa: BLE001
            return False

    def _speak_pyttsx(self, text: str) -> None:
        """Fresh engine per call -- avoids the stuck run-loop bug entirely."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.cfg.rate)
            engine.setProperty("volume", self.cfg.volume)
            self._select_pyttsx_voice(engine)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as exc:  # noqa: BLE001
            self.log.error("pyttsx3 speak failed: %s", exc)

    def _select_pyttsx_voice(self, engine) -> None:
        hint = (self.cfg.voice_hint or "").lower()
        if not hint:
            return
        try:
            for voice in engine.getProperty("voices"):
                meta = f"{voice.id} {getattr(voice, 'name', '')}".lower()
                if hint in meta:
                    engine.setProperty("voice", voice.id)
                    return
        except Exception:  # noqa: BLE001
            pass

    # ---- speak -------------------------------------------------------------

    def speak(self, text: str) -> None:
        if not text:
            return
        if self._backend == "piper" and self._piper is not None:
            if self._speak_piper(text):
                return
        if self._backend == "sapi" and self._speak_sapi(text):
            return
        self._speak_pyttsx(text)

    def shutdown(self) -> None:
        self._voice = None
        self._piper = None
        self._backend = "none"
