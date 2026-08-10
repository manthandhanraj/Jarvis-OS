"""Opens editors/terminals and runs local projects."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from automation.base import ActionResult, Controller
from automation.dev.project_scanner import Project, ProjectScanner
from config.settings import DevSettings

_NEW_CONSOLE = 0x00000010
_NO_WINDOW = 0x08000000
_PY_ENTRIES = ("main.py", "app.py", "run.py", "manage.py", "src/main.py", "bot.py")


class CodeWorkspace(Controller):
    def __init__(self, cfg: DevSettings, scanner: ProjectScanner) -> None:
        super().__init__("dev")
        self.cfg = cfg
        self.scanner = scanner
        self._editor: str | None = None
        self._terminal: str | None = None

    def initialize(self) -> None:
        self._editor = shutil.which(self.cfg.editor_command)
        self._terminal = shutil.which(self.cfg.terminal_command)
        self._available = True
        self.log.info(
            "Code workspace ready (editor=%s, terminal=%s).",
            self._editor or "not found",
            self._terminal or "powershell",
        )

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _spawn_editor(self, path: str) -> bool:
        if self._editor:
            suffix = Path(self._editor).suffix.lower()
            args = (
                ["cmd", "/c", self._editor, path]
                if suffix in (".cmd", ".bat")
                else [self._editor, path]
            )
            try:
                subprocess.Popen(args, shell=False, creationflags=_NO_WINDOW)
                return True
            except OSError as exc:
                self.log.warning("Editor launch failed: %s", exc)
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", self.cfg.editor_command, path],
                shell=False,
                creationflags=_NO_WINDOW,
            )
            return True
        except OSError as exc:
            self.log.error("Editor fallback failed: %s", exc)
            return False

    def list_projects(self, limit: int = 12) -> ActionResult:
        projects = self.scanner.refresh()
        if not projects:
            return ActionResult(False, "Koi project mila nahi. Workspace roots settings mein check karo.")
        shown = projects[:limit]
        lines = [f"- {p.name} ({p.kind})" for p in shown]
        extra = "" if len(projects) <= limit else f"\n...aur {len(projects) - limit} aur."
        return ActionResult(True, f"{len(projects)} projects mile:\n" + "\n".join(lines) + extra)

    def open_editor(self, name: str) -> ActionResult:
        if not name:
            if self._spawn_editor("."):
                return ActionResult(True, "VS Code khol diya.")
            return ActionResult(False, "VS Code khol nahi paaya.")

        project = self.scanner.find(name)
        if project is None:
            return ActionResult(False, f"'{name}' naam ka project mila nahi.")
        if self._spawn_editor(project.path):
            return ActionResult(True, f"{project.name} VS Code mein khol diya.")
        return ActionResult(False, "VS Code khol nahi paaya.")

    def open_terminal(self, name: str) -> ActionResult:
        project = self.scanner.find(name) if name else None
        workdir = project.path if project else str(Path.home())

        script = f"Set-Location {self._ps_quote(workdir)}"
        if project and project.venv:
            activate = str(Path(project.venv) / "Scripts" / "Activate.ps1")
            script += f"; & {self._ps_quote(activate)}"

        if self._terminal:
            args = [self._terminal, "-d", workdir, "powershell", "-NoExit", "-Command", script]
            flags = _NO_WINDOW
        else:
            args = ["powershell", "-NoExit", "-Command", script]
            flags = _NEW_CONSOLE

        try:
            subprocess.Popen(args, shell=False, creationflags=flags)
        except OSError as exc:
            self.log.error("Terminal launch failed: %s", exc)
            return ActionResult(False, f"Terminal khul nahi paaya: {exc}")

        if project and project.venv:
            return ActionResult(True, f"{project.name} ka terminal khol diya, venv activate hai.")
        if project:
            return ActionResult(True, f"{project.name} ka terminal khol diya.")
        return ActionResult(True, "Terminal khol diya.")

    @staticmethod
    def _node_script(folder: Path) -> str:
        try:
            data = json.loads((folder / "package.json").read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
        except (OSError, ValueError):
            return "start"
        for candidate in ("dev", "start", "serve"):
            if candidate in scripts:
                return candidate
        return "start"

    def _build_run_command(self, project: Project) -> list[str] | None:
        folder = Path(project.path)

        if project.kind in ("python", "django"):
            python = (
                str(Path(project.venv) / "Scripts" / "python.exe")
                if project.venv
                else "python"
            )
            if project.kind == "django" and (folder / "manage.py").is_file():
                return [python, "manage.py", "runserver"]
            for entry in _PY_ENTRIES:
                if (folder / entry).is_file():
                    return [python, entry]
            return None

        if project.kind == "node":
            return ["cmd", "/c", "npm", "run", self._node_script(folder)]
        if project.kind == "rust":
            return ["cmd", "/c", "cargo", "run"]
        if project.kind == "go":
            return ["cmd", "/c", "go", "run", "."]
        return None

    def run_project(self, name: str) -> ActionResult:
        if not name:
            return ActionResult(False, "Kaunsa project run karna hai?")
        project = self.scanner.find(name)
        if project is None:
            return ActionResult(False, f"'{name}' naam ka project mila nahi.")

        command = self._build_run_command(project)
        if command is None:
            return ActionResult(
                False, f"{project.name} ka entry point detect nahi hua ({project.kind})."
            )

        try:
            subprocess.Popen(
                command,
                cwd=project.path,
                shell=False,
                creationflags=_NEW_CONSOLE,
                env=os.environ.copy(),
            )
        except OSError as exc:
            self.log.error("Run failed for %s: %s", project.name, exc)
            return ActionResult(False, f"Run nahi kar paaya: {exc}")

        self.log.info("Running %s -> %s", project.name, command)
        return ActionResult(True, f"{project.name} run kar diya ({project.kind}).")

    def coding_mode(self, name: str) -> ActionResult:
        project = self.scanner.find(name) if name else None
        if name and project is None:
            return ActionResult(False, f"'{name}' naam ka project mila nahi.")

        target = project.name if project else ""
        editor = self.open_editor(target)
        terminal = self.open_terminal(target)
        if not editor.ok and not terminal.ok:
            return ActionResult(False, "Coding mode start nahi ho paaya.")

        label = project.name if project else "workspace"
        return ActionResult(True, f"Coding mode on. {label} ka editor aur terminal ready hai.")
