"""Built-in conversational and control commands."""
from __future__ import annotations

from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import has_keyword


class GreetCommand(Command):
    name = "greet"
    description = "Greet the user"
    risk = RiskLevel.SAFE
    canonical = "hello"
    _greetings = ("hello", "hi", "hey", "namaste", "namaskar", "hola", "yo", "sup")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._greetings)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult("Namaste! Main JARVIS. Kya kaam hai?")


class ThanksCommand(Command):
    name = "thanks"
    description = "Respond to thanks"
    risk = RiskLevel.SAFE
    canonical = "thanks"
    _thanks = ("thanks", "thank you", "shukriya", "dhanyawad", "thx")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._thanks)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult("Koi baat nahi! Aur kuch?")


class IdentityCommand(Command):
    name = "identity"
    description = "Explain who JARVIS is"
    risk = RiskLevel.SAFE
    canonical = "who are you"
    _phrases = ("who are you", "what are you", "your name", "tum kaun", "aap kaun",
                "kaun ho", "naam kya")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        s = ctx.settings
        return CommandResult(
            f"Main {s.app_name} hoon, aapka personal AI assistant. "
            "Apps, browser, coding, games, files aur system control kar sakta hoon."
        )


class ExitCommand(Command):
    name = "exit"
    description = "Shut down the assistant"
    risk = RiskLevel.SAFE
    canonical = "exit"
    _phrases = ("exit", "quit", "goodbye", "bye", "band karo jarvis",
                "so jao", "sleep jarvis", "shutdown jarvis", "bandh ho jao")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult("Theek hai, main so raha hoon. Bye!", should_exit=True)


class HelpCommand(Command):
    name = "help"
    description = "List what JARVIS can do"
    risk = RiskLevel.SAFE
    canonical = "help"
    _phrases = ("help", "madad", "what can you do", "kya kar sakte", "commands",
                "options", "kya kar sakta")

    def __init__(self, commands: list[Command]) -> None:
        self._commands = commands

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        seen: set[str] = set()
        lines: list[str] = []
        for cmd in self._commands:
            if cmd.name in seen or cmd.name == self.name:
                continue
            seen.add(cmd.name)
            lines.append(f"- {cmd.description}")
        return CommandResult("Main ye kar sakta hoon:\n" + "\n".join(lines))


def build_builtin_commands() -> list[Command]:
    return [GreetCommand(), ThanksCommand(), IdentityCommand(), ExitCommand()]
