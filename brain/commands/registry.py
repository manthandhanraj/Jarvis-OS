"""Assembles the full command list in priority order (through Day 14)."""
from __future__ import annotations

from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command
from brain.commands.builtin import HelpCommand, build_builtin_commands
from brain.commands.coding import build_dev_commands
from brain.commands.files import build_file_commands
from brain.commands.gaming import build_game_commands
from brain.commands.memory_cmds import build_memory_commands
from brain.commands.system import build_system_commands
from brain.commands.web import build_web_commands
from memory.memory_service import MemoryService


def build_commands(
    automation: WindowsAutomationService,
    memory: MemoryService | None = None,
) -> list[Command]:
    """Specific handlers first; generic app open/close last, builtins after that.

    File commands come before web/apps but are internally guarded by a
    file/folder signal, so 'notepad kholo' still routes to open_app.
    """
    system = build_system_commands(automation)
    generic_apps = system[-2:]      # CloseAppCommand, OpenAppCommand
    specific_system = system[:-2]

    commands: list[Command] = []
    commands.extend(specific_system)
    commands.extend(build_file_commands(automation))
    commands.extend(build_web_commands(automation))
    commands.extend(build_game_commands(automation))
    commands.extend(build_dev_commands(automation))
    if memory is not None:
        commands.extend(build_memory_commands(memory))
    commands.extend(generic_apps)
    commands.extend(build_builtin_commands())
    commands.append(HelpCommand(commands))
    return commands
