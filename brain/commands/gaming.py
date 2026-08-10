"""Gaming commands: launch a game, list installed games."""
from __future__ import annotations

from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import has_keyword, strip_triggers

_LAUNCH_TRIGGERS = ("play game", "launch game", "start game", "game khelo", "khelo",
                    "play", "launch", "start", "game chalu karo", "open game")
_GAME_FILLER = ("game", "the", "ko", "wala", "please", "named", "called")


class _GameCommand(Command):
    def __init__(self, service: WindowsAutomationService) -> None:
        self.service = service


class ListGamesCommand(_GameCommand):
    name = "list_games"
    description = "List your installed games"
    risk = RiskLevel.SAFE
    canonical = "list games"
    _phrases = ("list games", "show games", "my games", "games dikhao",
                "kitne games", "which games", "saare games", "installed games")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._phrases)

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        return CommandResult(self.service.games.list_games().message)


class LaunchGameCommand(_GameCommand):
    name = "launch_game"
    description = "Launch a game by name"
    risk = RiskLevel.SAFE
    canonical = "play {target}"
    target_hint = "game name, e.g. valorant, gta v, dota"

    def matches(self, text: str) -> bool:
        if has_keyword(text, ("list", "show", "dikhao", "kitne", "which", "saare")):
            return False
        return has_keyword(text, _LAUNCH_TRIGGERS)

    def _game(self, text: str) -> str:
        return strip_triggers(text, _LAUNCH_TRIGGERS, extra_filler=_GAME_FILLER)

    def describe(self, text: str) -> str:
        return f"Launch game '{self._game(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        game = self._game(text)
        if not game:
            return CommandResult("Kaunsa game khelna hai? Naam batao.")
        return CommandResult(self.service.games.launch(game).message)


def build_game_commands(service: WindowsAutomationService) -> list[Command]:
    return [ListGamesCommand(service), LaunchGameCommand(service)]
