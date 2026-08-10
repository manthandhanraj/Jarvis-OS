"""User-facing memory commands: remember, recall, forget, list (Day 12)."""
from __future__ import annotations

import re

from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from memory.memory_service import MemoryService
from utils.text import has_keyword, normalize

_KV_PATTERNS = (
    re.compile(
        r"(?:remember|yaad rakho|note|save)(?:\s+that|\s+ki|\s+ke)?\s+"
        r"(?:my\s+|mera\s+|meri\s+|mere\s+)?(?P<key>.+?)\s+(?:is|hai|=|:)\s+(?P<value>.+)$"
    ),
    re.compile(
        r"(?:mera|meri|mere|my)\s+(?P<key>.+?)\s+(?P<value>.+?)\s+"
        r"(?:hai|is)\s+(?:yaad rakho|remember|save karo|note karo)$"
    ),
)
_REMEMBER_TRIGGERS = ("remember", "yaad rakho", "yaad rakhna", "save this", "note this down")


class _MemoryCommand(Command):
    keywords: tuple[str, ...] = ()

    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    def matches(self, text: str) -> bool:
        return has_keyword(text, self.keywords)


class RememberCommand(_MemoryCommand):
    name = "remember"
    description = "Remember a fact about you"
    risk = RiskLevel.SAFE
    canonical = "remember {target}"
    target_hint = "a fact phrased as 'X is Y', e.g. 'my main project is jarvis_os'"
    keywords = _REMEMBER_TRIGGERS

    def _parse(self, text: str) -> tuple[str, str] | None:
        low = normalize(text)
        for pattern in _KV_PATTERNS:
            m = pattern.search(low)
            if m:
                key = m.group("key").strip(" :,-")
                value = m.group("value").strip(" :,-")
                if key and value:
                    return key, value
        return None

    def describe(self, text: str) -> str:
        parsed = self._parse(text)
        return f"Remember that {parsed[0]} = {parsed[1]}" if parsed else self.description

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        parsed = self._parse(text)
        if parsed is None:
            return CommandResult(
                "Kya yaad rakhun? Aise bolo: 'remember my main project is jarvis_os'."
            )
        key, value = parsed
        self.memory.remember(key, value)
        return CommandResult(f"Yaad rakh liya: {key} = {value}.")


class RecallCommand(_MemoryCommand):
    name = "recall"
    description = "Recall something you told me"
    risk = RiskLevel.SAFE
    canonical = "what is my {target}"
    target_hint = "the thing to recall, e.g. 'main project'"
    keywords = ("what is my", "what's my", "recall")

    def matches(self, text: str) -> bool:
        if has_keyword(text, self.keywords):
            return True
        possessive = has_keyword(text, ("mera", "meri", "mere", "my"))
        question = has_keyword(text, ("kya hai", "kya tha", "kaunsa hai", "kaun sa hai"))
        return possessive and question

    def _extract_key(self, text: str) -> str:
        low = normalize(text)
        low = re.sub(
            r"(what is my|what's my|whats my|mera|meri|mere|kya hai|kya tha|"
            r"recall|yaad hai|batao|my)\b",
            " ", low,
        )
        return " ".join(low.split()).strip(" ?.,-")

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        key = self._extract_key(text)
        if not key:
            return CommandResult("Kya yaad karun? Naam batao.")
        fact = self.memory.recall(key)
        if fact is None:
            hits = self.memory.search(key)
            if not hits:
                return CommandResult(f"Mujhe '{key}' ke baare mein kuch yaad nahi.")
            fact = hits[0]
        return CommandResult(f"Tumhara {fact.key} hai: {fact.value}.")


class ForgetCommand(_MemoryCommand):
    name = "forget"
    description = "Forget a stored fact"
    risk = RiskLevel.MEDIUM
    canonical = "forget {target}"
    target_hint = "the fact key to delete"
    keywords = ("forget", "bhool jao", "bhul jao", "delete memory", "remove fact")

    def _extract_key(self, text: str) -> str:
        low = normalize(text)
        low = re.sub(
            r"(forget|bhool jao|bhul jao|delete memory|remove fact|"
            r"about|mera|meri|my)\b",
            " ", low,
        )
        return " ".join(low.split()).strip(" ?.,-")

    def describe(self, text: str) -> str:
        key = self._extract_key(text)
        return f"Forget '{key}'" if key else self.description

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        key = self._extract_key(text)
        if not key:
            return CommandResult("Kya bhoolna hai? Naam batao.")
        if self.memory.forget(key):
            return CommandResult(f"Theek hai, '{key}' bhool gaya.")
        return CommandResult(f"'{key}' naam ka kuch yaad hi nahi tha.")


class ListMemoryCommand(_MemoryCommand):
    name = "list_memory"
    description = "List everything I remember about you"
    risk = RiskLevel.SAFE
    canonical = "what do you remember"
    keywords = ("what do you remember", "kya yaad hai tumhe", "show memory",
                "list memory", "sab kuch yaad", "memory dikhao")

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        facts = self.memory.facts()
        if not facts:
            return CommandResult("Abhi tak maine kuch yaad nahi rakha hai.")
        lines = [f"- {f.key}: {f.value}" for f in facts]
        return CommandResult("Ye sab yaad hai:\n" + "\n".join(lines))


def build_memory_commands(memory: MemoryService) -> list[Command]:
    """List/forget/recall are checked before the broad 'remember' keyword so
    'what do you remember' is not swallowed by RememberCommand."""
    return [
        ListMemoryCommand(memory),
        ForgetCommand(memory),
        RecallCommand(memory),
        RememberCommand(memory),
    ]
