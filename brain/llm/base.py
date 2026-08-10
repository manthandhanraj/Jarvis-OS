"""Abstract local-LLM engine contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class Message(TypedDict):
    role: str      # "system" | "user" | "assistant"
    content: str


class LLMEngine(ABC):
    @abstractmethod
    def initialize(self) -> None:
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Return the assistant's text reply, or '' on failure."""

    def shutdown(self) -> None:
        return None
