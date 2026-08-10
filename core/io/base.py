"""Abstract I/O channel: one interface for console, voice and GUI modes."""
from __future__ import annotations

from abc import ABC, abstractmethod


class IOChannel(ABC):
    """A bidirectional user channel used by the session and confirmer."""

    @abstractmethod
    def get_command(self) -> str | None:
        """Return the next user command, or None to end the session."""

    @abstractmethod
    def send(self, text: str) -> None:
        """Deliver a response to the user."""

    @abstractmethod
    def ask(self, prompt: str) -> str:
        """Prompt the user (e.g. a confirmation) and return their reply."""

    def close(self) -> None:  # optional hook
        return None
