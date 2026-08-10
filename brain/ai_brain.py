"""Facade module that owns the LLM, intent resolver and conversation engine."""
from __future__ import annotations

from brain.commands.base import Command
from brain.conversation import ConversationEngine
from brain.intent import Intent, IntentResolver
from brain.llm.base import LLMEngine
from brain.llm.ollama_engine import OllamaEngine
from config.settings import Settings
from core.base import BaseModule


def _build_engine(settings: Settings) -> LLMEngine:
    provider = settings.brain.provider.lower()
    if provider == "ollama":
        return OllamaEngine(settings.brain)
    raise ValueError(f"Unknown LLM provider: {settings.brain.provider}")


class AIBrain(BaseModule):
    def __init__(self, settings: Settings) -> None:
        super().__init__(name="brain")
        self.cfg = settings.brain
        self.llm = _build_engine(settings)
        self.intent = IntentResolver(self.llm, settings.brain)
        self.conversation = ConversationEngine(self.llm, settings.brain)

    def initialize(self) -> None:
        if not self.cfg.enabled:
            self.log.info("AI brain disabled in settings.")
            return
        self.llm.initialize()
        if self.llm.available:
            self.mark_ready()
            self.log.info("AI brain online.")
        else:
            self.log.warning("AI brain offline. Keyword commands still work.")

    def resolve(self, text: str, commands: list[Command]) -> Intent:
        return self.intent.resolve(text, commands)

    def chat(self, text: str, grounding: str = "") -> str:
        return self.conversation.reply(text, grounding=grounding)

    def shutdown(self) -> None:
        self.conversation.clear()
        self.llm.shutdown()
        self.mark_stopped()
