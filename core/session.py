"""Interaction loop. Source-agnostic: works with any IOChannel."""
from __future__ import annotations

from core.io.base import IOChannel
from core.router import CommandRouter
from utils.logger import get_logger


class InteractionSession:
    def __init__(self, channel: IOChannel, router: CommandRouter, greeting: str | None = None) -> None:
        self._ch = channel
        self._router = router
        self._greeting = greeting
        self.log = get_logger("jarvis.session")

    def run(self) -> None:
        if self._greeting:
            self._ch.send(self._greeting)
        while True:
            try:
                text = self._ch.get_command()
            except KeyboardInterrupt:
                break
            if text is None:
                break
            if not text.strip():
                continue
            result = self._router.route(text)
            if result.reply:
                self._ch.send(result.reply)
            if result.should_exit:
                break
        self.log.info("Session ended.")
