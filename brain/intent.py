"""LLM-backed intent resolution with a strict confidence gate."""
from __future__ import annotations

import json
from dataclasses import dataclass

from brain.commands.base import Command
from brain.llm.base import LLMEngine, Message
from brain.llm.prompts import INTENT_USER, build_intent_system
from config.settings import BrainSettings
from utils.logger import get_logger


@dataclass
class Intent:
    command: Command | None
    target: str
    confidence: float

    @property
    def is_chat(self) -> bool:
        return self.command is None


class IntentResolver:
    def __init__(self, llm: LLMEngine, cfg: BrainSettings) -> None:
        self.llm = llm
        self.cfg = cfg
        self.log = get_logger("jarvis.brain.intent")

    @staticmethod
    def _catalog(commands: list[Command]) -> str:
        lines = []
        for cmd in commands:
            hint = f" (target: {cmd.target_hint})" if cmd.target_hint else ""
            lines.append(f"- {cmd.name}: {cmd.description}{hint}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            return None

    def resolve(self, utterance: str, commands: list[Command]) -> Intent:
        if not self.llm.available:
            return Intent(None, "", 0.0)

        by_name = {c.name: c for c in commands}
        messages: list[Message] = [
            {"role": "system", "content": build_intent_system(self._catalog(commands))},
            {"role": "user", "content": INTENT_USER.format(utterance=utterance)},
        ]

        raw = self.llm.complete(
            messages,
            temperature=self.cfg.intent_temperature,
            max_tokens=120,
            json_mode=True,
        )
        if not raw:
            return Intent(None, "", 0.0)

        data = self._extract_json(raw)
        if not data:
            self.log.warning("Intent JSON parse failed: %r", raw)
            return Intent(None, "", 0.0)

        name = str(data.get("command", "chat")).strip()
        target = str(data.get("target", "")).strip()
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        if name == "chat" or name not in by_name:
            return Intent(None, target, confidence)
        if confidence < self.cfg.min_confidence:
            self.log.info("Intent '%s' below gate (%.2f), routing to chat.", name, confidence)
            return Intent(None, target, confidence)

        return Intent(by_name[name], target, confidence)
