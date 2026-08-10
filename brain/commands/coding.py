"""Developer commands: coding mode, open editor/terminal, run, list projects."""
from __future__ import annotations

from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import has_keyword, strip_triggers

_PROJECT_FILLER = ("project", "folder", "repo", "repository", "code", "the", "ko",
                   "wala", "naam", "named", "called")


class _DevCommand(Command):
    def __init__(self, service: WindowsAutomationService) -> None:
        self.service = service


class ListProjectsCommand(_DevCommand):
    name = "list_projects"
    description = "List your code projects"
    risk = RiskLevel.SAFE
    canonical = "list projects"
    _phrases = ("list projects", "show projects", "my projects", "projects dikhao",
                "kitne projects", "saare projects", "which projects")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.dev.list_projects().message)


class CodingModeCommand(_DevCommand):
    name = "coding_mode"
    description = "Start coding mode (editor + terminal) for a project"
    risk = RiskLevel.SAFE
    canonical = "coding mode {target}"
    target_hint = "project name (optional)"
    _phrases = ("coding mode", "code mode", "let's code", "lets code", "start coding",
                "coding shuru", "dev mode", "development mode")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def _project(self, text: str) -> str:
        return strip_triggers(text, self._phrases + ("for", "on", "with"),
                              extra_filler=_PROJECT_FILLER)

    def describe(self, text: str) -> str:
        project = self._project(text)
        return f"Start coding mode for '{project}'" if project else "Start coding mode"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.dev.coding_mode(self._project(text)).message)


class RunProjectCommand(_DevCommand):
    name = "run_project"
    description = "Run a project"
    risk = RiskLevel.MEDIUM
    canonical = "run {target}"
    target_hint = "project name to run"
    _triggers = ("run project", "execute project", "run karo", "chalao project",
                 "start project", "project run", "run the", "run")

    def matches(self, text: str) -> bool:
        if not has_keyword(text, self._triggers):
            return False
        return not has_keyword(text, ("coding", "code mode", "editor", "terminal"))

    def _project(self, text: str) -> str:
        return strip_triggers(text, self._triggers, extra_filler=_PROJECT_FILLER)

    def describe(self, text: str) -> str:
        return f"Run project '{self._project(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        project = self._project(text)
        if not project:
            return CommandResult("Kaunsa project run karun? Naam batao.")
        return CommandResult(self.service.dev.run_project(project).message)


class OpenEditorCommand(_DevCommand):
    name = "open_editor"
    description = "Open a project in VS Code"
    risk = RiskLevel.SAFE
    canonical = "open {target} in vscode"
    target_hint = "project name (optional)"
    _triggers = ("open in vscode", "open vscode", "vs code kholo", "vscode kholo",
                 "open editor", "editor kholo", "open in code", "code kholo")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def _project(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("in", "with"),
                              extra_filler=_PROJECT_FILLER + ("vscode", "vs", "code", "editor"))

    def describe(self, text: str) -> str:
        project = self._project(text)
        return f"Open '{project}' in VS Code" if project else "Open VS Code"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.dev.open_editor(self._project(text)).message)


class OpenTerminalCommand(_DevCommand):
    name = "open_terminal"
    description = "Open a terminal, optionally in a project with its venv"
    risk = RiskLevel.SAFE
    canonical = "open terminal {target}"
    target_hint = "project name (optional)"
    _triggers = ("open terminal", "terminal kholo", "open cmd", "open powershell",
                 "launch terminal", "terminal khol")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def _project(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("in", "for", "with"),
                              extra_filler=_PROJECT_FILLER + ("terminal", "cmd", "powershell"))

    def describe(self, text: str) -> str:
        project = self._project(text)
        return f"Open terminal in '{project}'" if project else "Open a terminal"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.dev.open_terminal(self._project(text)).message)


def build_dev_commands(service: WindowsAutomationService) -> list[Command]:
    """Order matters: coding-mode and editor/terminal before the generic run."""
    return [
        ListProjectsCommand(service),
        CodingModeCommand(service),
        OpenEditorCommand(service),
        OpenTerminalCommand(service),
        RunProjectCommand(service),
    ]
