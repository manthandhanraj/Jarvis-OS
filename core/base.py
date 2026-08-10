"""Base abstractions shared by every JARVIS OS module."""
from __future__ import annotations

from abc import ABC, abstractmethod

from utils.logger import get_logger


class BaseModule(ABC):
    """Uniform lifecycle contract for every subsystem (voice, brain, ...)."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._ready = False
        self.log = get_logger(f"jarvis.{name}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_ready(self) -> bool:
        return self._ready

    @abstractmethod
    def initialize(self) -> None:
        """Prepare the module for use; call mark_ready() on success."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release any resources held by the module."""

    def mark_ready(self) -> None:
        self._ready = True

    def mark_stopped(self) -> None:
        self._ready = False
