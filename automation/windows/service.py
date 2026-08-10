"""Facade module that owns every automation controller."""
from __future__ import annotations

from automation.base import Controller
from automation.browser.web_navigator import WebNavigator
from automation.dev.code_workspace import CodeWorkspace
from automation.dev.project_scanner import ProjectScanner
from automation.files.file_manager import FileManager
from automation.games.game_library import GameLibrary
from automation.windows.app_launcher import AppLauncher
from automation.windows.brightness_control import BrightnessController
from automation.windows.power_control import PowerController
from automation.windows.volume_control import VolumeController
from config.settings import Settings
from core.base import BaseModule


class WindowsAutomationService(BaseModule):
    def __init__(self, settings: Settings) -> None:
        super().__init__(name="automation")
        self.apps = AppLauncher(settings.automation)
        self.volume = VolumeController(settings.automation)
        self.brightness = BrightnessController(settings.automation)
        self.power = PowerController(settings.automation)
        self.web = WebNavigator(settings.browser)

        self.project_scanner = ProjectScanner(settings.dev, settings.data_dir)
        self.dev = CodeWorkspace(settings.dev, self.project_scanner)
        self.games = GameLibrary(settings.games, settings.data_dir)
        self.files = FileManager(settings.files)

    @property
    def _controllers(self) -> tuple[Controller, ...]:
        return (
            self.apps, self.volume, self.brightness, self.power,
            self.web, self.dev, self.games, self.files,
        )

    def initialize(self) -> None:
        for controller in self._controllers:
            try:
                controller.initialize()
            except Exception as exc:  # noqa: BLE001
                self.log.error("Controller '%s' init failed: %s", controller.name, exc)
        self.mark_ready()

    def shutdown(self) -> None:
        for controller in self._controllers:
            controller.shutdown()
        self.mark_stopped()
