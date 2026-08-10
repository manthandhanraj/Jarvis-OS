"""Typed records used by the memory subsystem."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fact:
    """A durable key/value the user asked JARVIS to remember."""
    key: str
    value: str
    category: str = "general"
    updated_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ActionRecord:
    """One executed command, kept for context and reference resolution."""
    command: str        # command.name, e.g. "open_app"
    target: str         # resolved argument, e.g. "chrome"
    phrase: str         # what the user actually said
    success: bool
    created_at: float = field(default_factory=time.time)
