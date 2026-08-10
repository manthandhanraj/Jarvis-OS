"""Discovers local code projects and classifies them by ecosystem."""
from __future__ import annotations

import difflib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from config.settings import DevSettings
from utils.logger import get_logger

_MARKERS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "python"),
    ("requirements.txt", "python"),
    ("manage.py", "django"),
    ("package.json", "node"),
    ("Cargo.toml", "rust"),
    ("go.mod", "go"),
    ("pom.xml", "java"),
    ("build.gradle", "java"),
    ("CMakeLists.txt", "cpp"),
    (".git", "generic"),
)
_VENV_DIRS = (".venv", "venv", "env")


@dataclass(frozen=True)
class Project:
    name: str
    path: str
    kind: str
    venv: str | None = None


class ProjectScanner:
    def __init__(self, cfg: DevSettings, data_dir: Path) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.dev.scanner")
        self._cache_path = data_dir / cfg.cache_file
        self._projects: list[Project] = []

    @property
    def projects(self) -> list[Project]:
        return list(self._projects)

    def _roots(self) -> list[Path]:
        roots: list[Path] = []
        for raw in self.cfg.workspace_roots:
            path = Path(os.path.expandvars(raw))
            if path.is_dir() and path not in roots:
                roots.append(path)
        return roots

    @staticmethod
    def _classify(folder: Path) -> str | None:
        for marker, kind in _MARKERS:
            if (folder / marker).exists():
                return kind
        return None

    @staticmethod
    def _find_venv(folder: Path) -> str | None:
        for name in _VENV_DIRS:
            candidate = folder / name / "Scripts" / "python.exe"
            if candidate.is_file():
                return str(folder / name)
        return None

    def _walk(self, root: Path, depth: int, found: list[Project]) -> None:
        if depth > self.cfg.scan_depth:
            return
        try:
            entries = list(os.scandir(root))
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.startswith(".") or entry.name in self.cfg.ignored_dirs:
                continue
            folder = Path(entry.path)
            kind = self._classify(folder)
            if kind is not None:
                found.append(
                    Project(
                        name=folder.name,
                        path=str(folder),
                        kind=kind,
                        venv=self._find_venv(folder),
                    )
                )
                continue
            self._walk(folder, depth + 1, found)

    def _load_cache(self) -> bool:
        try:
            if not self._cache_path.is_file():
                return False
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("timestamp", 0)) > self.cfg.cache_ttl_s:
                return False
            self._projects = [Project(**item) for item in payload.get("projects", [])]
            return bool(self._projects)
        except (OSError, ValueError, TypeError) as exc:
            self.log.debug("Project cache unusable: %s", exc)
            return False

    def _save_cache(self) -> None:
        payload = {
            "timestamp": time.time(),
            "projects": [asdict(p) for p in self._projects],
        }
        try:
            self._cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self.log.warning("Could not write project cache: %s", exc)

    def refresh(self, force: bool = False) -> list[Project]:
        if not force and self._load_cache():
            self.log.info("Loaded %d projects from cache.", len(self._projects))
            return self.projects

        found: list[Project] = []
        for root in self._roots():
            self._walk(root, depth=1, found=found)

        unique: dict[str, Project] = {}
        for project in found:
            unique.setdefault(project.path.lower(), project)
        self._projects = sorted(unique.values(), key=lambda p: p.name.lower())

        self.log.info("Scanned %d projects.", len(self._projects))
        self._save_cache()
        return self.projects

    def find(self, name: str) -> Project | None:
        query = name.strip().lower()
        if not query:
            return None
        if not self._projects:
            self.refresh()

        for project in self._projects:
            if project.name.lower() == query:
                return project
        for project in self._projects:
            if query in project.name.lower():
                return project

        names = [p.name.lower() for p in self._projects]
        close = difflib.get_close_matches(query, names, n=1, cutoff=self.cfg.match_cutoff)
        if close:
            index = names.index(close[0])
            return self._projects[index]
        return None
