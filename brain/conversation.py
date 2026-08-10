"""Short-memory conversational replies in the user's language mix."""
from __future__ import annotations

from collections import deque

from brain.llm.base import LLMEngine, Message
from config.settings import BrainSettings
from utils.logger import get_logger


class ConversationEngine:
    def __init__(self, llm: LLMEngine, cfg: BrainSettings) -> None:
        self.llm = llm
        self.cfg = cfg
        self.log = get_logger("jarvis.brain.chat")
        self._history: deque[Message] = deque(maxlen=max(2, cfg.history_turns * 2))

    def clear(self) -> None:
        self._history.clear()

    def reply(self, text: str, grounding: str = "") -> str:
        if not self.llm.available:
            return ""

        system = self.cfg.persona
        if grounding:
            system = f"{system}\n\n{grounding}"

        messages: list[Message] = [{"role": "system", "content": system}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": text})

        answer = self.llm.complete(
            messages,
            temperature=self.cfg.chat_temperature,
            max_tokens=self.cfg.max_tokens,
        )
        if not answer:
            return ""

        self._history.append({"role": "user", "content": text})
        self._history.append({"role": "assistant", "content": answer})
        return answer
