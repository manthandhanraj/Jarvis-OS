"""Offline STT via faster-whisper. Tries GPU, auto-falls back to CPU.

Two Windows-specific hazards are handled here.

1. PyAV: faster-whisper imports `av` only to decode audio *files*. JARVIS always
   feeds raw numpy arrays, so that code path never runs -- but the module-level
   import still breaks the whole package when Windows Smart App Control blocks
   PyAV's bundled DLLs ("An Application Control policy has blocked this file").
   `_ensure_av()` therefore registers a harmless stub under `av` when the real
   package cannot load, which keeps faster-whisper importable. Anything that
   actually touches PyAV raises a clear error instead of failing silently.

2. CUDA: the GPU path needs the NVIDIA cuBLAS/cuDNN runtime DLLs. When those are
   missing, faster-whisper still *loads* the model on CUDA but raises at the
   first transcribe (e.g. 'cublas64_12.dll not found'). A tiny silent warm-up
   right after loading surfaces that at startup, and we fall back to CPU/int8
   automatically. A second guard in transcribe() rebuilds on CPU if a CUDA error
   ever slips through at runtime.
"""
from __future__ import annotations

import sys
import types

import numpy as np

from config.settings import STTSettings
from utils.exceptions import ModuleInitializationError
from utils.logger import get_logger
from voice.stt.base import STTEngine

_WARMUP_SAMPLES = 16000  # ~1s of silence; enough to force the encoder to run

# Submodules faster-whisper may import from PyAV. Each needs a sys.modules entry
# so that `from av.audio.resampler import AudioResampler` resolves to the stub.
_AV_SUBMODULES = (
    "av",
    "av.audio",
    "av.audio.frame",
    "av.audio.resampler",
    "av.audio.stream",
    "av.container",
    "av.codec",
    "av.codec.context",
    "av.error",
    "av.filter",
    "av.packet",
    "av.stream",
    "av.video",
    "av.video.frame",
)

_AV_MESSAGE = (
    "PyAV is unavailable on this system (its DLLs are blocked by Windows "
    "Application Control). Audio-file decoding is disabled; JARVIS records "
    "from the microphone as numpy arrays and does not need it."
)


def _stub_attribute(qualname: str) -> type:
    """Build a placeholder that is safe as a class, a callable and an except target."""

    def _blocked(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError(f"{qualname}: {_AV_MESSAGE}")

    return type(qualname.rsplit(".", 1)[-1], (Exception,), {"__init__": _blocked})


class _StubModule(types.ModuleType):
    """Module whose every attribute is an unusable-but-importable placeholder."""

    def __getattr__(self, name: str):  # noqa: ANN204
        if name.startswith("__"):
            raise AttributeError(name)
        return _stub_attribute(f"{self.__name__}.{name}")


def _ensure_av() -> bool:
    """Return True if the real PyAV loaded, False if a stub was installed."""
    if isinstance(sys.modules.get("av"), _StubModule):
        return False
    try:
        import av  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        for name in _AV_SUBMODULES:
            if not isinstance(sys.modules.get(name), _StubModule):
                sys.modules[name] = _StubModule(name)
        return False


class WhisperSTT(STTEngine):
    def __init__(self, cfg: STTSettings) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.voice.stt")
        self._model = None
        self._device = "cpu"
        self._compute = "int8"
        self._fell_back = False

    def _resolve_device(self) -> tuple[str, str]:
        device, compute = self.cfg.device, self.cfg.compute_type
        if device == "auto":
            device = "cpu"
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
            except Exception:  # noqa: BLE001
                device = "cpu"
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"
        return device, compute

    def _build(self, device: str, compute: str):
        """Load the model and force the compute backend to initialize.

        Constructing WhisperModel does not touch CUDA; the missing-DLL error
        only fires on the first real transcribe. Running a silent warm-up here
        makes that happen now instead of on the user's first spoken command.
        """
        _ensure_av()
        from faster_whisper import WhisperModel

        model = WhisperModel(self.cfg.model_size, device=device, compute_type=compute)
        probe = np.zeros(_WARMUP_SAMPLES, dtype=np.float32)
        segments, _info = model.transcribe(probe, language=self.cfg.language, beam_size=1)
        list(segments)  # force CTranslate2 to run the encoder (raises if CUDA libs missing)
        return model

    def initialize(self) -> None:
        if not _ensure_av():
            self.log.warning(
                "PyAV unavailable; continuing without it (microphone input is unaffected)."
            )
        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise ModuleInitializationError(
                f"faster-whisper could not be imported: {exc}"
            ) from exc

        device, compute = self._resolve_device()
        try:
            self._model = self._build(device, compute)
        except Exception as exc:  # noqa: BLE001
            if device == "cpu":
                raise ModuleInitializationError(
                    f"Whisper CPU initialization failed: {exc}"
                ) from exc
            self.log.warning(
                "Whisper on %s/%s not usable (%s). Falling back to CPU/int8.",
                device, compute, exc,
            )
            device, compute = "cpu", "int8"
            self._fell_back = True
            try:
                self._model = self._build(device, compute)
            except Exception as exc2:  # noqa: BLE001
                raise ModuleInitializationError(
                    f"Whisper CPU fallback failed: {exc2}"
                ) from exc2

        self._device, self._compute = device, compute
        self.log.info("Whisper '%s' loaded on %s/%s.", self.cfg.model_size, device, compute)

    def _run(self, audio: np.ndarray) -> str:
        segments, _info = self._model.transcribe(
            audio.astype(np.float32),
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
        )
        return "".join(seg.text for seg in segments).strip()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if self._model is None:
            raise ModuleInitializationError("WhisperSTT.initialize() not called.")
        if audio is None or audio.size == 0:
            return ""
        try:
            return self._run(audio)
        except RuntimeError as exc:
            if self._device == "cuda" and not self._fell_back:
                self.log.warning("CUDA transcribe failed (%s). Rebuilding on CPU/int8.", exc)
                self._fell_back = True
                self._model = self._build("cpu", "int8")
                self._device, self._compute = "cpu", "int8"
                return self._run(audio)
            raise

    def shutdown(self) -> None:
        self._model = None
