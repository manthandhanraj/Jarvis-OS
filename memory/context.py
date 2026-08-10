"""Rolling in-RAM view of recent actions, plus reference resolution."""
from __future__ import annotations

import re
import time
from collections import deque

from config.settings import MemorySettings
from memory.models import ActionRecord
from utils.logger import get_logger
from utils.text import normalize

_REFERENCE_WORDS = (
    "wahi", "wohi", "vahi", "same", "usko", "usi", "use", "isko", "isi",
    "ye wala", "wo wala", "that one", "phir se", "dobara", "again", "repeat",
    "pehle wala", "last wala", "wapas",
)
_TARGETED = {
    "open_app", "close_app", "open_site", "launch_game",
    "run_project", "coding_mode", "open_project", "open_terminal",
    "youtube_play", "web_search",
    "open_file", "list_folder", "organize_folder",
}
_RETARGET_VERBS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("band", "close", "kill", "quit", "bandh"), "close_app"),
    (("run", "chalao", "chala", "execute", "start"), "run_project"),
    (("open", "kholo", "khol"), "open_app"),
    (("play", "bajao", "sunao"), "youtube_play"),
)


class ContextTracker:
    def __init__(self, cfg: MemorySettings) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.memory.context")
        self._recent: deque[ActionRecord] = deque(maxlen=cfg.context_window)

    def prime(self, actions: list[ActionRecord]) -> None:
        """Load history (newest-first) at startup so references survive restarts."""
        for record in reversed(actions):
            self._recent.append(record)

    def record(self, action: ActionRecord) -> None:
        self._recent.append(action)

    @property
    def last(self) -> ActionRecord | None:
        return self._recent[-1] if self._recent else None

    def last_targeted(self) -> ActionRecord | None:
        for record in reversed(self._recent):
            if record.command in _TARGETED and record.target:
                return record
        return None

    @staticmethod
    def has_reference(text: str) -> bool:
        t = normalize(text)
        return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", t) for w in _REFERENCE_WORDS)

    def _fresh(self, record: ActionRecord) -> bool:
        return (time.time() - record.created_at) <= self.cfg.reference_max_age_s

    def resolve_reference(self, text: str) -> tuple[str, str] | None:
        """Map a back-reference to (command_name, target), or None.

        Deterministic, runs before the LLM. Reuses the most recent targeted
        action's argument.
        """
        if not self.has_reference(text):
            return None
        anchor = self.last_targeted()
        if anchor is None or not self._fresh(anchor):
            return None

        t = normalize(text)
        for verbs, command_name in _RETARGET_VERBS:
            if any(re.search(rf"(?<!\w){re.escape(v)}(?!\w)", t) for v in verbs):
                self.log.info("Reference '%s' retargeted to %s '%s'.",
                              text, command_name, anchor.target)
                return command_name, anchor.target

        self.log.info("Reference '%s' repeats %s '%s'.",
                      text, anchor.command, anchor.target)
        return anchor.command, anchor.target

    def prompt_snippet(self) -> str:
        """Compact recent-action list handed to the LLM for grounding."""
        n = self.cfg.context_prompt_actions
        rows = [r for r in list(self._recent)[-n:] if r.target]
        if not rows:
            return ""
        parts = [f"{r.command}:{r.target}" for r in rows]
        return "Recent actions (most recent last): " + ", ".join(parts)
