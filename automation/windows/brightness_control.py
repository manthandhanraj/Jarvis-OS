"""Display brightness via screen-brightness-control with a WMI fallback."""
from __future__ import annotations

import subprocess

from automation.base import ActionResult, Controller
from config.settings import AutomationSettings

_NO_WINDOW = 0x08000000
_PS_GET = (
    "(Get-CimInstance -Namespace root/WMI "
    "-ClassName WmiMonitorBrightness).CurrentBrightness"
)
_PS_SET = (
    "(Get-CimInstance -Namespace root/WMI "
    "-ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{value})"
)


class BrightnessController(Controller):
    def __init__(self, cfg: AutomationSettings) -> None:
        super().__init__("brightness")
        self.cfg = cfg
        self._sbc = None

    def initialize(self) -> None:
        try:
            import screen_brightness_control as sbc
            sbc.get_brightness()
            self._sbc = sbc
            self.log.info("Brightness backend: screen-brightness-control.")
        except Exception as exc:  # noqa: BLE001
            self._sbc = None
            self.log.warning("sbc unavailable (%s). Using WMI fallback.", exc)
        self._available = True

    @staticmethod
    def _powershell(command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_NO_WINDOW,
        )

    def get_brightness(self) -> int | None:
        if self._sbc is not None:
            try:
                levels = self._sbc.get_brightness()
                if levels:
                    return int(levels[0])
            except Exception as exc:  # noqa: BLE001
                self.log.debug("sbc read failed: %s", exc)
        try:
            result = self._powershell(_PS_GET)
            first = result.stdout.strip().splitlines()
            if first and first[0].strip().isdigit():
                return int(first[0].strip())
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.error("WMI brightness read failed: %s", exc)
        return None

    def set_brightness(self, percent: int) -> ActionResult:
        percent = max(0, min(100, int(percent)))
        if self._sbc is not None:
            try:
                self._sbc.set_brightness(percent)
                return ActionResult(True, f"Brightness {percent} percent kar di.")
            except Exception as exc:  # noqa: BLE001
                self.log.debug("sbc set failed: %s", exc)
        try:
            result = self._powershell(_PS_SET.format(value=percent))
            if result.returncode == 0:
                return ActionResult(True, f"Brightness {percent} percent kar di.")
            self.log.error("WMI brightness set error: %s", result.stderr.strip())
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.error("WMI brightness set failed: %s", exc)
        return ActionResult(False, "Ye display brightness control support nahi karta.")

    def change_brightness(self, delta: int) -> ActionResult:
        current = self.get_brightness()
        if current is None:
            return ActionResult(False, "Current brightness padh nahi paaya.")
        return self.set_brightness(current + delta)
