"""Ollama chat backend over its local HTTP API (stdlib only, no SDK)."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from brain.llm.base import LLMEngine, Message
from config.settings import BrainSettings
from utils.logger import get_logger


class OllamaEngine(LLMEngine):
    def __init__(self, cfg: BrainSettings) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.brain.ollama")
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _post(self, path: str, payload: dict, timeout: float) -> dict:
        request = Request(
            f"{self.cfg.host}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, path: str, timeout: float) -> dict:
        with urlopen(f"{self.cfg.host}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def initialize(self) -> None:
        try:
            data = self._get("/api/tags", self.cfg.health_timeout_s)
        except (URLError, HTTPError, OSError, ValueError) as exc:
            self.log.warning("Ollama not reachable at %s (%s).", self.cfg.host, exc)
            self._available = False
            return

        models = {m.get("name", "") for m in data.get("models", [])}
        base = self.cfg.model.split(":")[0]
        if self.cfg.model in models or any(m.split(":")[0] == base for m in models):
            self._available = True
            self.log.info("Ollama online with model '%s'.", self.cfg.model)
        else:
            self._available = True
            self.log.warning(
                "Model '%s' not pulled. Run: ollama pull %s", self.cfg.model, self.cfg.model
            )

    def complete(
        self,
        messages: list[Message],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        if not self._available:
            return ""
        options = {"temperature": temperature, "num_ctx": self.cfg.num_ctx}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"

        try:
            data = self._post("/api/chat", payload, self.cfg.request_timeout_s)
        except (URLError, HTTPError, OSError, ValueError) as exc:
            self.log.error("Ollama request failed: %s", exc)
            return ""
        return data.get("message", {}).get("content", "").strip()
