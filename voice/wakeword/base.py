"""Abstract wake-word detector (Porcupine/openWakeWord can implement this later)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class WakeWordDetector(ABC):
    @abstractmethod
    def wait_for_wake(self) -> bool:
        """Block until the wake word is heard. Returns False if aborted."""
