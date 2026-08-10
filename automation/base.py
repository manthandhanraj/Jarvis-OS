"""Shared contract + result type for automation controllers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from utils.logger import get_logger


@dataclass
class ActionResult:
    ok: bool
    message: str


class Controller(ABC):
    """A hardware/OS controller. initialize() must never raise."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._available = False
        self.log = get_logger(f"jarvis.automation.{name}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    @abstractmethod
    def initialize(self) -> None:
        """Detect backends and set availability. Degrade, do not raise."""

    def shutdown(self) -> None:
        self._available = False
