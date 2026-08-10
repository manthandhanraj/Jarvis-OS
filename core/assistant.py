"""Core orchestrator: owns the lifecycle of every registered module."""
from __future__ import annotations

from config.settings import Settings
from core.base import BaseModule
from utils.exceptions import ModuleInitializationError
from utils.logger import get_logger


class Assistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = get_logger("jarvis.core")
        self._modules: dict[str, BaseModule] = {}

    def register(self, module: BaseModule) -> None:
        if module.name in self._modules:
            raise ModuleInitializationError(f"Module '{module.name}' already registered.")
        self._modules[module.name] = module
        self.log.debug("Registered module: %s", module.name)

    def get(self, name: str) -> BaseModule | None:
        return self._modules.get(name)

    def initialize(self) -> None:
        for module in self._modules.values():
            try:
                module.initialize()
                self.log.info("Initialized module: %s", module.name)
            except Exception as exc:  # noqa: BLE001
                raise ModuleInitializationError(
                    f"Failed to initialize '{module.name}': {exc}"
                ) from exc

    def shutdown(self) -> None:
        for module in reversed(list(self._modules.values())):
            try:
                module.shutdown()
                self.log.info("Shut down module: %s", module.name)
            except Exception as exc:  # noqa: BLE001
                self.log.error("Error shutting down '%s': %s", module.name, exc)
