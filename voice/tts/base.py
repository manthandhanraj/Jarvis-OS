"""Abstract text-to-speech engine."""
from __future__ import annotations

from abc import ABC, abstractmethod


class TTSEngine(ABC):
    @abstractmethod
    def initialize(self) -> None:
        ...

    @abstractmethod
    def speak(self, text: str) -> None:
        ...

    def shutdown(self) -> None:
        return None
