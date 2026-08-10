"""Keyboard/console implementation of IOChannel (text mode)."""
from __future__ import annotations

from core.io.base import IOChannel
from utils.logger import get_logger


class ConsoleIO(IOChannel):
    def __init__(self, you: str = "You", name: str = "JARVIS") -> None:
        self._you = you
        self._name = name
        self.log = get_logger("jarvis.io.console")

    def get_command(self) -> str | None:
        try:
            return input(f"{self._you}> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    def send(self, text: str) -> None:
        print(f"{self._name}> {text}")

    def ask(self, prompt: str) -> str:
        try:
            return input(f"{self._name}? {prompt} ")
        except (EOFError, KeyboardInterrupt):
            print()
            return ""
