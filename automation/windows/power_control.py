"""Shutdown, restart, sleep, lock and sign-out control.

SAFETY: destructive actions (shutdown, restart, sign out) are DISABLED by
default so running/testing JARVIS never powers off your machine. To actually
allow them, launch with the environment variable set:

    PowerShell:  $env:JARVIS_ARM_POWER = "1"; python main.py
    CMD:         set JARVIS_ARM_POWER=1 && python main.py

Lock and sleep stay live because they are non-destructive and recoverable.
Cancel always works, so 'cancel shutdown' can stop a real scheduled shutdown.
"""
from __future__ import annotations

import os
import subprocess

from automation.base import ActionResult, Controller
from config.settings import AutomationSettings

_NO_WINDOW = 0x08000000
_ARM_ENV = "JARVIS_ARM_POWER"
_MIN_SAFE_DELAY = 60  # seconds; gives ample time to 'cancel shutdown'
_ARMED_VALUES = {"1", "true", "yes", "on", "arm", "armed"}


class PowerController(Controller):
    def __init__(self, cfg: AutomationSettings) -> None:
        super().__init__("power")
        self.cfg = cfg
        self._armed = os.environ.get(_ARM_ENV, "").strip().lower() in _ARMED_VALUES

    def initialize(self) -> None:
        self._available = True
        state = "ARMED (real power actions enabled)" if self._armed else "SAFE MODE (simulated)"
        self.log.info("Power controller ready — %s.", state)

    @property
    def armed(self) -> bool:
        return self._armed

    def _run(self, args: list[str]) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.error("Power command %s failed: %s", args, exc)
            return False, str(exc)
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            self.log.error("Power command %s returned %d: %s", args, result.returncode, message)
            return False, message
        return True, ""

    def _blocked(self, action: str) -> ActionResult:
        self.log.warning("Blocked %s: power actions not armed (SAFE MODE).", action)
        return ActionResult(
            True,
            f"[SAFE MODE] {action} ko rok diya — ye ek test run tha, laptop safe hai. "
            f"Sach mein {action} karna ho to JARVIS ko arm karke chalao: "
            f'PowerShell mein `$env:{_ARM_ENV}="1"; python main.py`.',
        )

    def shutdown(self, delay: int | None = None) -> ActionResult:
        if not self._armed:
            return self._blocked("shutdown")
        seconds = max(_MIN_SAFE_DELAY, self.cfg.shutdown_delay_s if delay is None else delay)
        ok, err = self._run(["shutdown", "/s", "/t", str(seconds)])
        if ok:
            return ActionResult(
                True,
                f"PC {seconds} second mein shutdown hoga. "
                "Rokna ho to abhi bolo 'cancel shutdown'.",
            )
        return ActionResult(False, f"Shutdown fail hua: {err}")

    def restart(self, delay: int | None = None) -> ActionResult:
        if not self._armed:
            return self._blocked("restart")
        seconds = max(_MIN_SAFE_DELAY, self.cfg.restart_delay_s if delay is None else delay)
        ok, err = self._run(["shutdown", "/r", "/t", str(seconds)])
        if ok:
            return ActionResult(
                True,
                f"PC {seconds} second mein restart hoga. "
                "Rokna ho to abhi bolo 'cancel shutdown'.",
            )
        return ActionResult(False, f"Restart fail hua: {err}")

    def cancel(self) -> ActionResult:
        ok, _ = self._run(["shutdown", "/a"])
        if ok:
            return ActionResult(True, "Shutdown cancel kar diya.")
        return ActionResult(True, "Koi shutdown schedule hi nahi tha.")

    def sign_out(self) -> ActionResult:
        if not self._armed:
            return self._blocked("sign out")
        ok, err = self._run(["shutdown", "/l"])
        return ActionResult(ok, "Sign out kar raha hoon." if ok else f"Sign out fail: {err}")

    def lock(self) -> ActionResult:
        ok, err = self._run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return ActionResult(ok, "PC lock kar diya." if ok else f"Lock fail: {err}")

    def sleep(self) -> ActionResult:
        ok, err = self._run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return ActionResult(ok, "PC ko sula raha hoon." if ok else f"Sleep fail: {err}")
