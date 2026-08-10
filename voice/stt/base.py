"""Abstract speech-to-text engine."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class STTEngine(ABC):
    @abstractmethod
    def initialize(self) -> None:
        ...

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        ...

    def shutdown(self) -> None:
        return None
