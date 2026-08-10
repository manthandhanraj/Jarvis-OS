"""Launch and close Windows applications without shell injection risk."""
from __future__ import annotations

import os
import re
import subprocess
import winreg
from pathlib import Path

from automation.base import ActionResult, Controller
from config.settings import AutomationSettings

_APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
_URI_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*:")
_UNSAFE = re.compile(r"[^a-z0-9 ._+:\\/\-]")
_NO_WINDOW = 0x08000000


class AppLauncher(Controller):
    def __init__(self, cfg: AutomationSettings) -> None:
        super().__init__("apps")
        self.cfg = cfg
        self._start_menus: list[Path] = []

    def initialize(self) -> None:
        candidates = [
            Path(os.environ.get("ProgramData", r"C:\ProgramData"))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        self._start_menus = [p for p in candidates if p.is_dir()]
        self._available = True
        self.log.info("App launcher ready (%d start-menu roots).", len(self._start_menus))

    @staticmethod
    def _sanitize(name: str) -> str:
        return _UNSAFE.sub("", name.strip().lower()).strip()

    def _resolve_alias(self, name: str) -> str:
        return self.cfg.app_aliases.get(name, name)

    @staticmethod
    def _from_app_paths(target: str) -> str | None:
        key = target if target.lower().endswith(".exe") else f"{target}.exe"
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(
                        root, rf"{_APP_PATHS_KEY}\{key}", 0, winreg.KEY_READ | view
                    ) as handle:
                        value, _ = winreg.QueryValueEx(handle, "")
                        path = Path(str(value).strip('"'))
                        if path.is_file():
                            return str(path)
                except OSError:
                    continue
        return None

    def _from_start_menu(self, target: str) -> str | None:
        wanted = target.lower()
        partial: Path | None = None
        for root in self._start_menus:
            try:
                for link in root.rglob("*.lnk"):
                    stem = link.stem.lower()
                    if stem == wanted:
                        return str(link)
                    if partial is None and wanted in stem:
                        partial = link
            except OSError:
                continue
        return str(partial) if partial else None

    @staticmethod
    def _spawn(path: str) -> None:
        suffix = Path(path).suffix.lower()
        if suffix in (".cmd", ".bat", ".lnk"):
            subprocess.Popen(
                ["cmd", "/c", "start", "", path],
                shell=False,
                creationflags=_NO_WINDOW,
            )
            return
        subprocess.Popen([path], shell=False, close_fds=True)

    def open_app(self, name: str) -> ActionResult:
        raw = self._sanitize(name)
        if not raw:
            return ActionResult(False, "Kaunsa app kholna hai, naam batao.")

        target = self._resolve_alias(raw)

        if _URI_SCHEME.match(target):
            try:
                os.startfile(target)  # noqa: S606 - trusted alias-mapped URI
                return ActionResult(True, f"{raw.title()} khol raha hoon.")
            except OSError as exc:
                return ActionResult(False, f"{raw} nahi khul paaya: {exc}")

        direct = Path(target)
        if direct.is_file():
            resolved: str | None = str(direct)
        else:
            import shutil
            resolved = (
                shutil.which(target)
                or self._from_app_paths(target)
                or self._from_start_menu(target)
            )

        if resolved:
            try:
                self._spawn(resolved)
                self.log.info("Launched '%s' -> %s", raw, resolved)
                return ActionResult(True, f"{raw.title()} khol diya.")
            except OSError as exc:
                self.log.error("Launch failed for %s: %s", resolved, exc)

        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", target],
                shell=False,
                creationflags=_NO_WINDOW,
            )
            return ActionResult(True, f"{raw.title()} launch kar raha hoon.")
        except OSError as exc:
            self.log.error("Fallback launch failed for %s: %s", target, exc)
            return ActionResult(False, f"'{raw}' naam ka app mila nahi.")

    def close_app(self, name: str) -> ActionResult:
        raw = self._sanitize(name)
        if not raw:
            return ActionResult(False, "Kaunsa app band karna hai?")

        target = self._resolve_alias(raw)
        process = target if target.lower().endswith(".exe") else f"{target}.exe"

        if process.lower() in self.cfg.protected_processes:
            self.log.warning("Blocked kill of protected process: %s", process)
            return ActionResult(False, f"{process} system process hai, band nahi karunga.")

        try:
            completed = subprocess.run(
                ["taskkill", "/IM", process, "/F", "/T"],
                capture_output=True,
                text=True,
                timeout=self.cfg.process_kill_timeout_s,
                creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ActionResult(False, f"Band nahi kar paaya: {exc}")

        if completed.returncode == 0:
            self.log.info("Killed process %s", process)
            return ActionResult(True, f"{raw.title()} band kar diya.")
        return ActionResult(False, f"{raw.title()} chal hi nahi raha tha.")
