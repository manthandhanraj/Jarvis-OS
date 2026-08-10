"""Per-platform installed-game scanners (Steam, Epic, Riot, Microsoft Store)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import winreg
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from config.settings import GameSettings
from utils.logger import get_logger

_NO_WINDOW = 0x08000000
_VDF_PATH = re.compile(r'"path"\s+"([^"]+)"')
_ACF_APPID = re.compile(r'"appid"\s+"(\d+)"', re.IGNORECASE)
_ACF_NAME = re.compile(r'"name"\s+"([^"]+)"', re.IGNORECASE)
_STEAM_SKIP = ("steamworks", "proton", "steam linux runtime", "redistributable")


@dataclass(frozen=True)
class Game:
    name: str
    source: str
    launch: str
    args: tuple[str, ...] = ()


class GameScanner(ABC):
    source: str = "unknown"

    def __init__(self, cfg: GameSettings) -> None:
        self.cfg = cfg
        self.log = get_logger(f"jarvis.games.{self.source}")

    @abstractmethod
    def scan(self) -> list[Game]:
        ...


class SteamScanner(GameScanner):
    source = "steam"

    @staticmethod
    def _steam_root() -> Path | None:
        for root, key in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        ):
            for value_name in ("SteamPath", "InstallPath"):
                try:
                    with winreg.OpenKey(root, key) as handle:
                        value, _ = winreg.QueryValueEx(handle, value_name)
                        path = Path(str(value))
                        if path.is_dir():
                            return path
                except OSError:
                    continue
        return None

    def _libraries(self, steam_root: Path) -> list[Path]:
        libraries = [steam_root]
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        try:
            content = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return libraries
        for raw in _VDF_PATH.findall(content):
            path = Path(raw.replace("\\\\", "\\"))
            if path.is_dir() and path not in libraries:
                libraries.append(path)
        return libraries

    def scan(self) -> list[Game]:
        steam_root = self._steam_root()
        if steam_root is None:
            return []

        games: list[Game] = []
        for library in self._libraries(steam_root):
            apps_dir = library / "steamapps"
            if not apps_dir.is_dir():
                continue
            for manifest in apps_dir.glob("appmanifest_*.acf"):
                try:
                    content = manifest.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                app_id = _ACF_APPID.search(content)
                name = _ACF_NAME.search(content)
                if not app_id or not name:
                    continue
                title = name.group(1).strip()
                if any(skip in title.lower() for skip in _STEAM_SKIP):
                    continue
                games.append(
                    Game(name=title, source=self.source,
                         launch=f"steam://rungameid/{app_id.group(1)}")
                )
        self.log.info("Found %d Steam games.", len(games))
        return games


class EpicScanner(GameScanner):
    source = "epic"

    def scan(self) -> list[Game]:
        base = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        manifests = base / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
        if not manifests.is_dir():
            return []

        games: list[Game] = []
        for item in manifests.glob("*.item"):
            try:
                data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, ValueError):
                continue
            title = str(data.get("DisplayName", "")).strip()
            app_name = data.get("AppName")
            namespace = data.get("CatalogNamespace")
            catalog_id = data.get("CatalogItemId")
            if not (title and app_name and namespace and catalog_id):
                continue
            uri = (
                f"com.epicgames.launcher://apps/{namespace}%3A{catalog_id}%3A{app_name}"
                "?action=launch&silent=true"
            )
            games.append(Game(name=title, source=self.source, launch=uri))
        self.log.info("Found %d Epic games.", len(games))
        return games


class RiotScanner(GameScanner):
    source = "riot"

    def _client(self) -> str | None:
        for raw in self.cfg.riot_client_paths:
            path = Path(os.path.expandvars(raw))
            if path.is_file():
                return str(path)
        return None

    def scan(self) -> list[Game]:
        client = self._client()
        if client is None:
            return []

        metadata = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Riot Games" / "Metadata"
        installed = {p.name.split(".")[0].lower() for p in metadata.glob("*")} if metadata.is_dir() else set()

        games: list[Game] = []
        seen: set[str] = set()
        for title, product in self.cfg.riot_products.items():
            if product in seen:
                continue
            if installed and product not in installed:
                continue
            seen.add(product)
            games.append(
                Game(
                    name=title.title(),
                    source=self.source,
                    launch=client,
                    args=(f"--launch-product={product}", "--launch-patchline=live"),
                )
            )
        self.log.info("Found %d Riot games.", len(games))
        return games


class StoreScanner(GameScanner):
    """Microsoft Store / Xbox packaged apps, resolved by name on demand."""

    source = "store"

    def scan(self) -> list[Game]:
        command = "Get-StartApps | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=self.cfg.scan_timeout_s,
                creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.warning("Get-StartApps failed: %s", exc)
            return []

        try:
            entries = json.loads(result.stdout or "[]")
        except ValueError:
            return []
        if isinstance(entries, dict):
            entries = [entries]

        games: list[Game] = []
        for entry in entries:
            name = str(entry.get("Name", "")).strip()
            app_id = str(entry.get("AppID", "")).strip()
            if not name or "!" not in app_id:
                continue
            games.append(
                Game(name=name, source=self.source,
                     launch=f"shell:AppsFolder\\{app_id}")
            )
        self.log.info("Found %d Store apps.", len(games))
        return games


def build_scanners(cfg: GameSettings) -> list[GameScanner]:
    return [SteamScanner(cfg), EpicScanner(cfg), RiotScanner(cfg), StoreScanner(cfg)]
