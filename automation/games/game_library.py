"""Aggregates installed games from every platform and launches them."""
from __future__ import annotations

import difflib
import json
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from automation.base import ActionResult, Controller
from automation.games.scanners import Game, build_scanners
from config.settings import GameSettings

_NO_WINDOW = 0x08000000
_LIBRARY_SOURCES = ("steam", "epic", "riot")


class GameLibrary(Controller):
    def __init__(self, cfg: GameSettings, data_dir: Path) -> None:
        super().__init__("games")
        self.cfg = cfg
        self._cache_path = data_dir / cfg.cache_file
        self._scanners = build_scanners(cfg)
        self._games: list[Game] = []

    def initialize(self) -> None:
        self._load_cache()
        self._available = True
        self.log.info("Game library ready (%d cached entries).", len(self._games))

    def _load_cache(self) -> bool:
        try:
            if not self._cache_path.is_file():
                return False
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("timestamp", 0)) > self.cfg.cache_ttl_s:
                return False
            self._games = [
                Game(name=i["name"], source=i["source"],
                     launch=i["launch"], args=tuple(i.get("args", ())))
                for i in payload.get("games", [])
            ]
            return bool(self._games)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.log.debug("Game cache unusable: %s", exc)
            return False

    def _save_cache(self) -> None:
        payload = {"timestamp": time.time(), "games": [asdict(g) for g in self._games]}
        try:
            self._cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self.log.warning("Could not write game cache: %s", exc)

    def refresh(self, force: bool = False) -> list[Game]:
        if not force and self._games:
            return list(self._games)
        if not force and self._load_cache():
            return list(self._games)

        collected: list[Game] = []
        for scanner in self._scanners:
            try:
                collected.extend(scanner.scan())
            except Exception as exc:  # noqa: BLE001
                self.log.error("Scanner '%s' failed: %s", scanner.source, exc)

        unique: dict[tuple[str, str], Game] = {}
        for game in collected:
            unique.setdefault((game.source, game.name.lower()), game)
        self._games = sorted(unique.values(), key=lambda g: g.name.lower())
        self._save_cache()
        return list(self._games)

    def find(self, name: str) -> Game | None:
        query = name.strip().lower()
        if not query:
            return None
        games = self.refresh()

        ranked = sorted(
            games,
            key=lambda g: (_LIBRARY_SOURCES.index(g.source)
                           if g.source in _LIBRARY_SOURCES else len(_LIBRARY_SOURCES)),
        )
        for game in ranked:
            if game.name.lower() == query:
                return game
        for game in ranked:
            if query in game.name.lower():
                return game

        names = [g.name.lower() for g in ranked]
        close = difflib.get_close_matches(query, names, n=1, cutoff=self.cfg.match_cutoff)
        if close:
            return ranked[names.index(close[0])]
        return None

    def list_games(self, limit: int = 15) -> ActionResult:
        games = [g for g in self.refresh() if g.source in _LIBRARY_SOURCES]
        if not games:
            return ActionResult(False, "Koi installed game detect nahi hua.")
        shown = games[:limit]
        lines = [f"- {g.name} ({g.source})" for g in shown]
        extra = "" if len(games) <= limit else f"\n...aur {len(games) - limit} aur."
        return ActionResult(True, f"{len(games)} games mile:\n" + "\n".join(lines) + extra)

    def launch(self, name: str) -> ActionResult:
        game = self.find(name)
        if game is None:
            return ActionResult(False, f"'{name}' naam ka game mila nahi.")

        try:
            if game.launch.startswith("shell:AppsFolder\\"):
                subprocess.Popen(["explorer.exe", game.launch], shell=False,
                                 creationflags=_NO_WINDOW)
            elif "://" in game.launch:
                os.startfile(game.launch)  # noqa: S606 - platform launcher URI
            else:
                subprocess.Popen([game.launch, *game.args], shell=False, close_fds=True)
        except OSError as exc:
            self.log.error("Launch failed for %s: %s", game.name, exc)
            return ActionResult(False, f"{game.name} launch nahi hua: {exc}")

        self.log.info("Launched game %s via %s.", game.name, game.source)
        return ActionResult(True, f"{game.name} launch kar diya. Enjoy karo!")
