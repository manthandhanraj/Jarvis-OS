"""Facade module wiring the store and context tracker into JARVIS."""
from __future__ import annotations

from config.settings import Settings
from core.base import BaseModule
from memory.context import ContextTracker
from memory.models import ActionRecord, Fact
from memory.store import MemoryStore


class MemoryService(BaseModule):
    def __init__(self, settings: Settings) -> None:
        super().__init__(name="memory")
        self.cfg = settings.memory
        self.store = MemoryStore(settings.memory, settings.data_dir)
        self.context = ContextTracker(settings.memory)

    def initialize(self) -> None:
        if not self.cfg.enabled:
            self.log.info("Memory disabled in settings.")
            return
        self.store.initialize()
        self.context.prime(self.store.recent_actions())
        self.mark_ready()
        self.log.info("Memory service online.")

    # ---- write paths -------------------------------------------------------

    def log_action(self, command: str, target: str, phrase: str, success: bool) -> None:
        if not self.is_ready:
            return
        record = ActionRecord(command=command, target=target, phrase=phrase, success=success)
        self.context.record(record)
        try:
            self.store.add_action(record)
        except Exception as exc:  # noqa: BLE001
            self.log.error("Failed to persist action: %s", exc)

    def remember(self, key: str, value: str, category: str = "general") -> None:
        if self.is_ready:
            self.store.set_fact(key, value, category)

    def forget(self, key: str) -> bool:
        return self.store.delete_fact(key) if self.is_ready else False

    # ---- read paths --------------------------------------------------------

    def recall(self, key: str) -> Fact | None:
        return self.store.get_fact(key) if self.is_ready else None

    def search(self, term: str) -> list[Fact]:
        return self.store.search_facts(term) if self.is_ready else []

    def facts(self) -> list[Fact]:
        return self.store.all_facts() if self.is_ready else []

    def resolve_reference(self, text: str) -> tuple[str, str] | None:
        return self.context.resolve_reference(text) if self.is_ready else None

    def context_snippet(self) -> str:
        return self.context.prompt_snippet() if self.is_ready else ""

    def shutdown(self) -> None:
        self.store.shutdown()
        self.mark_stopped()
