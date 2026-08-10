"""System control commands: apps, volume, brightness, power."""
from __future__ import annotations

from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import extract_percent, has_keyword, strip_triggers

_OPEN_TRIGGERS = ("open", "launch", "start", "run", "kholo", "khol", "chalu karo",
                  "chalu", "chala do", "shuru karo")
_CLOSE_TRIGGERS = ("close", "kill", "quit", "exit", "band karo", "band kar",
                   "bandh karo", "terminate")
_APP_FILLER = ("app", "application", "program", "software", "ko", "the")


class _AutomationCommand(Command):
    def __init__(self, service: WindowsAutomationService) -> None:
        self.service = service


class OpenAppCommand(_AutomationCommand):
    name = "open_app"
    description = "Open an application"
    risk = RiskLevel.SAFE
    canonical = "open {target}"
    target_hint = "application name, e.g. chrome, notepad, spotify"

    def matches(self, text: str) -> bool:
        return has_keyword(text, _OPEN_TRIGGERS)

    def _app_name(self, text: str) -> str:
        return strip_triggers(text, _OPEN_TRIGGERS, extra_filler=_APP_FILLER)

    def describe(self, text: str) -> str:
        return f"Open '{self._app_name(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.apps.open_app(self._app_name(text)).message)


class CloseAppCommand(_AutomationCommand):
    name = "close_app"
    description = "Close a running application"
    risk = RiskLevel.MEDIUM
    canonical = "close {target}"
    target_hint = "application name to close"

    def matches(self, text: str) -> bool:
        return has_keyword(text, _CLOSE_TRIGGERS)

    def _app_name(self, text: str) -> str:
        return strip_triggers(text, _CLOSE_TRIGGERS, extra_filler=_APP_FILLER)

    def describe(self, text: str) -> str:
        return f"Close '{self._app_name(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.apps.close_app(self._app_name(text)).message)


class VolumeCommand(_AutomationCommand):
    name = "set_volume"
    description = "Set or change the volume"
    risk = RiskLevel.SAFE
    canonical = "set volume to {target}"
    target_hint = "a percentage 0-100, or 'up'/'down'"
    _triggers = ("volume", "sound", "awaaz", "aawaz", "vol")
    _up = ("up", "badhao", "increase", "tez", "zyada", "raise", "badha")
    _down = ("down", "kam", "decrease", "ghatao", "low", "reduce", "dhima")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def describe(self, text: str) -> str:
        return "Adjust volume"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        step = ctx.settings.automation.volume_step
        if has_keyword(text, ("mute", "silent", "chup")):
            return CommandResult(self.service.volume.set_mute(True).message)
        if has_keyword(text, ("unmute", "unsilent")):
            return CommandResult(self.service.volume.set_mute(False).message)
        percent = extract_percent(text)
        if percent is not None:
            return CommandResult(self.service.volume.set_volume(percent).message)
        if has_keyword(text, self._up):
            return CommandResult(self.service.volume.change_volume(step).message)
        if has_keyword(text, self._down):
            return CommandResult(self.service.volume.change_volume(-step).message)
        return CommandResult("Volume kitna karun? Number ya up/down bolo.")


class BrightnessCommand(_AutomationCommand):
    name = "set_brightness"
    description = "Set or change screen brightness"
    risk = RiskLevel.SAFE
    canonical = "set brightness to {target}"
    target_hint = "a percentage 0-100, or 'up'/'down'"
    _triggers = ("brightness", "roshni", "screen light", "display light")
    _up = ("up", "badhao", "increase", "tez", "zyada", "raise", "badha")
    _down = ("down", "kam", "decrease", "ghatao", "low", "reduce", "dhima")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def describe(self, text: str) -> str:
        return "Adjust brightness"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        step = ctx.settings.automation.brightness_step
        percent = extract_percent(text)
        if percent is not None:
            return CommandResult(self.service.brightness.set_brightness(percent).message)
        if has_keyword(text, self._up):
            return CommandResult(self.service.brightness.change_brightness(step).message)
        if has_keyword(text, self._down):
            return CommandResult(self.service.brightness.change_brightness(-step).message)
        return CommandResult("Brightness kitni karun? Number ya up/down bolo.")


class PowerCommand(_AutomationCommand):
    name = "power"
    description = "Shutdown, restart, sleep, lock or sign out"
    risk = RiskLevel.HIGH
    canonical = "shutdown"
    target_hint = "one of: shutdown, restart, sleep, lock, sign out"
    _device = ("pc", "computer", "laptop", "system", "machine", "windows", "cpu")
    _cancel = ("cancel shutdown", "abort shutdown", "shutdown cancel", "stop shutdown",
               "shutdown roko", "restart cancel")
    # Unambiguous shutdown phrases (no object word needed).
    _shutdown = ("shutdown", "shut down", "power off", "band kar do pc", "pc band")
    # Ambiguous phrase: only a shutdown if paired with a device word, so
    # "turn off the music/lights/volume" never powers off the PC.
    _shutdown_ambiguous = ("turn off",)
    _restart = ("restart", "reboot", "reset pc", "dobara start")
    _sleep = ("sleep", "suspend", "sula do", "so jao pc")
    _lock = ("lock", "lock screen", "lock kar", "lock karo")
    _signout = ("sign out", "signout", "log out", "logout", "log off")

    def _wants_shutdown(self, text: str) -> bool:
        if has_keyword(text, self._shutdown):
            return True
        return has_keyword(text, self._shutdown_ambiguous) and has_keyword(text, self._device)

    def matches(self, text: str) -> bool:
        if has_keyword(text, self._cancel + self._restart + self._sleep
                       + self._lock + self._signout):
            return True
        return self._wants_shutdown(text)

    def describe(self, text: str) -> str:
        if has_keyword(text, self._cancel):
            return "Cancel any scheduled shutdown"
        if has_keyword(text, self._restart):
            return "Restart the PC"
        if has_keyword(text, self._sleep):
            return "Put the PC to sleep"
        if has_keyword(text, self._lock):
            return "Lock the PC"
        if has_keyword(text, self._signout):
            return "Sign out of Windows"
        return "Shut down the PC"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        power = self.service.power
        if has_keyword(text, self._cancel):
            return CommandResult(power.cancel().message)
        if has_keyword(text, self._restart):
            return CommandResult(power.restart().message)
        if has_keyword(text, self._sleep):
            return CommandResult(power.sleep().message)
        if has_keyword(text, self._lock):
            return CommandResult(power.lock().message)
        if has_keyword(text, self._signout):
            return CommandResult(power.sign_out().message)
        return CommandResult(power.shutdown().message)


class CancelShutdownCommand(_AutomationCommand):
    """Separate SAFE command so 'cancel shutdown' needs no confirmation."""

    name = "cancel_shutdown"
    description = "Cancel a scheduled shutdown or restart"
    risk = RiskLevel.SAFE
    canonical = "cancel shutdown"
    _phrases = ("cancel shutdown", "abort shutdown", "shutdown cancel",
                "stop shutdown", "shutdown roko", "restart cancel", "shutdown mat karo")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def describe(self, text: str) -> str:
        return "Cancel scheduled shutdown"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.power.cancel().message)


def build_system_commands(service: WindowsAutomationService) -> list[Command]:
    """Order matters: specific handlers first, generic app open/close last."""
    return [
        CancelShutdownCommand(service),
        PowerCommand(service),
        VolumeCommand(service),
        BrightnessCommand(service),
        CloseAppCommand(service),
        OpenAppCommand(service),
    ]
