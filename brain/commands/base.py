"""Command abstraction shared by keyword matching and AI routing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from config.settings import Settings
from core.risk import RiskLevel


@dataclass
class CommandContext:
    """Everything a command may need at execution time."""
    settings: Settings


@dataclass
class CommandResult:
    reply: str
    should_exit: bool = False


class Command(ABC):
    """A single skill. Subclasses set name/description/risk and metadata.

    canonical: a template with an optional '{target}' slot. The router renders
    it (via to_text) when the AI or a reference supplies the argument, so every
    execution path produces the same phrasing the keyword parsers understand.
    target_hint: guidance shown to the LLM about what the argument means.
    """

    name: str = "command"
    description: str = ""
    risk: RiskLevel = RiskLevel.SAFE
    canonical: str = ""
    target_hint: str = ""

    @abstractmethod
    def matches(self, text: str) -> bool:
        ...

    @abstractmethod
    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        ...

    def describe(self, text: str) -> str:
        """Human-readable summary used in confirmation prompts."""
        return self.description or self.name

    def to_text(self, target: str) -> str:
        """Render an AI/reference-supplied target into a keyword-parseable phrase."""
        target = (target or "").strip()
        if self.canonical:
            if "{target}" in self.canonical:
                return self.canonical.format(target=target).strip()
            return f"{self.canonical} {target}".strip()
        return f"{self.name} {target}".strip()
