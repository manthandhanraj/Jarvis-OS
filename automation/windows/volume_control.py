"""Master volume via pycaw (absolute) with a ctypes media-key fallback."""
from __future__ import annotations

import ctypes

from automation.base import ActionResult, Controller
from config.settings import AutomationSettings

_VK_MUTE = 0xAD
_VK_DOWN = 0xAE
_VK_UP = 0xAF
_KEYEVENTF_KEYUP = 0x0002
_KEY_STEP_PERCENT = 2


class VolumeController(Controller):
    """COM objects are created per call so the controller is thread-safe."""

    def __init__(self, cfg: AutomationSettings) -> None:
        super().__init__("volume")
        self.cfg = cfg
        self._use_pycaw = False

    def initialize(self) -> None:
        try:
            self._endpoint()
            self._use_pycaw = True
            self.log.info("Volume backend: pycaw (absolute control).")
        except Exception as exc:  # noqa: BLE001
            self._use_pycaw = False
            self.log.warning("pycaw unavailable (%s). Using media-key fallback.", exc)
        self._available = True

    @staticmethod
    def _endpoint():
        from ctypes import POINTER, cast

        import comtypes
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    @staticmethod
    def _tap(vk_code: int, times: int = 1) -> None:
        user32 = ctypes.windll.user32
        for _ in range(max(1, times)):
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, _KEYEVENTF_KEYUP, 0)

    def get_volume(self) -> int | None:
        if not self._use_pycaw:
            return None
        try:
            return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)
        except Exception as exc:  # noqa: BLE001
            self.log.error("Volume read failed: %s", exc)
            return None

    def set_volume(self, percent: int) -> ActionResult:
        percent = max(0, min(100, int(percent)))
        if self._use_pycaw:
            try:
                endpoint = self._endpoint()
                endpoint.SetMute(0, None)
                endpoint.SetMasterVolumeLevelScalar(percent / 100.0, None)
                return ActionResult(True, f"Volume {percent} percent kar diya.")
            except Exception as exc:  # noqa: BLE001
                self.log.error("Volume set failed: %s", exc)
        self._tap(_VK_DOWN, 50)
        self._tap(_VK_UP, max(0, percent // _KEY_STEP_PERCENT))
        return ActionResult(True, f"Volume approx {percent} percent kar diya.")

    def change_volume(self, delta: int) -> ActionResult:
        current = self.get_volume()
        if current is not None:
            return self.set_volume(current + delta)
        taps = max(1, abs(delta) // _KEY_STEP_PERCENT)
        self._tap(_VK_UP if delta > 0 else _VK_DOWN, taps)
        word = "badha" if delta > 0 else "kam kar"
        return ActionResult(True, f"Volume {word} diya.")

    def set_mute(self, muted: bool) -> ActionResult:
        if self._use_pycaw:
            try:
                self._endpoint().SetMute(1 if muted else 0, None)
                return ActionResult(True, "Volume mute kar diya." if muted else "Volume wapas on hai.")
            except Exception as exc:  # noqa: BLE001
                self.log.error("Mute failed: %s", exc)
        self._tap(_VK_MUTE)
        return ActionResult(True, "Mute toggle kar diya.")
