"""Safe file management confined to a whitelist of user folders (Day 13).

Every operation resolves paths and refuses to touch anything outside the
configured search roots, blocking directory-traversal. Deletes go to the
Recycle Bin (recoverable) via the Windows shell, not os.remove.
"""
from __future__ import annotations

import ctypes
import difflib
import os
import shutil
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from automation.base import ActionResult, Controller
from config.settings import FileSettings

# Friendly names that map to a known root folder.
_ROOT_ALIASES: dict[str, str] = {
    "desktop": "Desktop",
    "documents": "Documents", "docs": "Documents", "document": "Documents",
    "downloads": "Downloads", "download": "Downloads",
    "pictures": "Pictures", "photos": "Pictures", "images": "Pictures",
    "music": "Music", "songs": "Music",
    "videos": "Videos", "video": "Videos", "movies": "Videos",
}


@dataclass(frozen=True)
class Match:
    path: Path
    is_dir: bool


def _recycle(path: Path) -> bool:
    """Send a file/folder to the Windows Recycle Bin via SHFileOperationW."""
    fo_delete = 0x0003
    fof_allowundo = 0x0040
    fof_noconfirmation = 0x0010
    fof_silent = 0x0004

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = fo_delete
    op.pFrom = f"{path}\0"  # ctypes appends one more NUL -> double-null terminated
    op.pTo = None
    op.fFlags = fof_allowundo | fof_noconfirmation | fof_silent
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0 and not op.fAnyOperationsAborted


class FileManager(Controller):
    def __init__(self, cfg: FileSettings) -> None:
        super().__init__("files")
        self.cfg = cfg
        self._roots: list[Path] = []

    def initialize(self) -> None:
        roots: list[Path] = []
        for raw in self.cfg.search_roots:
            path = Path(os.path.expandvars(raw))
            if path.is_dir() and path not in roots:
                roots.append(path.resolve())
        self._roots = roots
        self._available = True
        self.log.info("File manager ready (%d roots).", len(self._roots))

    # ---- safety ------------------------------------------------------------

    def _within_roots(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(resolved == r or resolved.is_relative_to(r) for r in self._roots)

    def _root_by_alias(self, name: str) -> Path | None:
        folder = _ROOT_ALIASES.get(name.strip().lower())
        if folder is None:
            return None
        for root in self._roots:
            if root.name.lower() == folder.lower():
                return root
        return None

    def _skip_dir(self, name: str) -> bool:
        low = name.lower()
        return low.startswith(".") or low in self.cfg.ignored_dirs

    # ---- search ------------------------------------------------------------

    def _walk_matches(self, query: str, want_dir: bool | None) -> list[Match]:
        query = query.strip().lower()
        exact: list[Match] = []
        partial: list[Match] = []
        for root in self._roots:
            for current, dirs, filenames in os.walk(root):
                depth = len(Path(current).relative_to(root).parts)
                if depth >= self.cfg.search_depth:
                    dirs[:] = []
                dirs[:] = [d for d in dirs if not self._skip_dir(d)]

                names = list(dirs) if want_dir else (
                    filenames if want_dir is False else filenames + dirs
                )
                for entry in names:
                    full = Path(current) / entry
                    is_dir = full.is_dir()
                    stem = entry.lower()
                    if stem == query or Path(entry).stem.lower() == query:
                        exact.append(Match(full, is_dir))
                    elif query in stem:
                        partial.append(Match(full, is_dir))
                if len(exact) + len(partial) >= self.cfg.max_results * 3:
                    break
        return exact + partial

    def find(self, query: str, want_dir: bool | None = None) -> list[Match]:
        if not query.strip():
            return []
        results = self._walk_matches(query, want_dir)
        seen: set[str] = set()
        unique: list[Match] = []
        for match in results:
            key = str(match.path).lower()
            if key not in seen:
                seen.add(key)
                unique.append(match)
        return unique[: self.cfg.max_results]

    def best_match(self, name: str, want_dir: bool | None = None) -> Match | None:
        matches = self.find(name, want_dir)
        if matches:
            return matches[0]
        # fuzzy over top-level names across roots
        pool: list[Match] = []
        for root in self._roots:
            try:
                for entry in os.scandir(root):
                    if self._skip_dir(entry.name):
                        continue
                    pool.append(Match(Path(entry.path), entry.is_dir()))
            except OSError:
                continue
        names = [m.path.name.lower() for m in pool]
        close = difflib.get_close_matches(name.strip().lower(), names, n=1, cutoff=0.6)
        return pool[names.index(close[0])] if close else None

    # ---- actions -----------------------------------------------------------

    def search_files(self, query: str) -> ActionResult:
        matches = self.find(query)
        if not matches:
            return ActionResult(False, f"'{query}' se milta koi file/folder nahi mila.")
        lines = [f"- {'[dir] ' if m.is_dir else ''}{m.path.name}  ({m.path.parent.name})"
                 for m in matches[:12]]
        extra = "" if len(matches) <= 12 else f"\n...aur {len(matches) - 12} aur."
        return ActionResult(True, f"{len(matches)} results '{query}':\n" + "\n".join(lines) + extra)

    def open_item(self, name: str) -> ActionResult:
        root = self._root_by_alias(name)
        target = root if root else (self.best_match(name).path if self.best_match(name) else None)
        if target is None:
            return ActionResult(False, f"'{name}' naam ka kuch mila nahi.")
        if not self._within_roots(target):
            return ActionResult(False, "Ye location allowed folders ke bahar hai.")
        try:
            os.startfile(str(target))  # noqa: S606 - path validated within roots
        except OSError as exc:
            return ActionResult(False, f"Khol nahi paaya: {exc}")
        return ActionResult(True, f"{target.name} khol diya.")

    def list_folder(self, name: str) -> ActionResult:
        root = self._root_by_alias(name)
        if root is not None:
            folder = root
        else:
            match = self.best_match(name, want_dir=True)
            folder = match.path if match else None
        if folder is None or not folder.is_dir():
            return ActionResult(False, f"'{name}' naam ka folder mila nahi.")
        if not self._within_roots(folder):
            return ActionResult(False, "Ye folder allowed area ke bahar hai.")
        try:
            entries = sorted(os.scandir(folder), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError as exc:
            return ActionResult(False, f"Folder padh nahi paaya: {exc}")
        if not entries:
            return ActionResult(True, f"{folder.name} khaali hai.")
        lines = [f"- {'[dir] ' if e.is_dir() else ''}{e.name}" for e in entries[:15]]
        extra = "" if len(entries) <= 15 else f"\n...aur {len(entries) - 15} aur."
        return ActionResult(True, f"{folder.name} mein {len(entries)} items:\n" + "\n".join(lines) + extra)

    def create_folder(self, name: str, parent_alias: str = "desktop") -> ActionResult:
        name = name.strip().strip("/\\")
        if not name:
            return ActionResult(False, "Folder ka naam batao.")
        parent = self._root_by_alias(parent_alias) or (self._roots[0] if self._roots else None)
        if parent is None:
            return ActionResult(False, "Koi allowed root folder configured nahi hai.")
        target = (parent / name)
        if not self._within_roots(target):
            return ActionResult(False, "Wahan folder banane ki permission nahi.")
        if target.exists():
            return ActionResult(False, f"'{name}' already {parent.name} mein hai.")
        try:
            target.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            return ActionResult(False, f"Folder bana nahi paaya: {exc}")
        return ActionResult(True, f"{parent.name} mein '{name}' folder bana diya.")

    def _resolve_dest(self, dest: str) -> Path | None:
        root = self._root_by_alias(dest)
        if root is not None:
            return root
        match = self.best_match(dest, want_dir=True)
        return match.path if match and match.is_dir else None

    def move_item(self, src_name: str, dest_name: str) -> ActionResult:
        return self._transfer(src_name, dest_name, copy=False)

    def copy_item(self, src_name: str, dest_name: str) -> ActionResult:
        return self._transfer(src_name, dest_name, copy=True)

    def _transfer(self, src_name: str, dest_name: str, copy: bool) -> ActionResult:
        verb = "copy" if copy else "move"
        src_match = self.best_match(src_name)
        if src_match is None:
            return ActionResult(False, f"'{src_name}' naam ka file/folder mila nahi.")
        dest_dir = self._resolve_dest(dest_name)
        if dest_dir is None:
            return ActionResult(False, f"'{dest_name}' naam ka destination folder mila nahi.")

        src, dest_dir = src_match.path, dest_dir
        if not (self._within_roots(src) and self._within_roots(dest_dir)):
            return ActionResult(False, "Source ya destination allowed area ke bahar hai.")
        target = dest_dir / src.name
        if target.exists():
            return ActionResult(False, f"'{src.name}' pehle se {dest_dir.name} mein hai.")

        try:
            if copy:
                if src.is_dir():
                    shutil.copytree(src, target)
                else:
                    shutil.copy2(src, target)
            else:
                shutil.move(str(src), str(target))
        except (OSError, shutil.Error) as exc:
            return ActionResult(False, f"{verb.title()} fail hua: {exc}")
        return ActionResult(True, f"{src.name} ko {dest_dir.name} mein {verb} kar diya.")

    def delete_item(self, name: str) -> ActionResult:
        match = self.best_match(name)
        if match is None:
            return ActionResult(False, f"'{name}' naam ka file/folder mila nahi.")
        path = match.path
        if not self._within_roots(path):
            return ActionResult(False, "Ye location allowed area ke bahar hai.")

        if self.cfg.use_recycle_bin:
            if _recycle(path):
                return ActionResult(True, f"{path.name} Recycle Bin mein daal diya.")
            self.log.warning("Recycle bin failed for %s, no hard delete performed.", path)
            return ActionResult(False, f"{path.name} delete nahi kar paaya.")

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            return ActionResult(False, f"Delete fail hua: {exc}")
        return ActionResult(True, f"{path.name} delete kar diya.")

    def organize(self, folder_alias: str = "downloads") -> ActionResult:
        folder = self._root_by_alias(folder_alias)
        if folder is None:
            match = self.best_match(folder_alias, want_dir=True)
            folder = match.path if match else None
        if folder is None or not folder.is_dir():
            return ActionResult(False, f"'{folder_alias}' naam ka folder mila nahi.")
        if not self._within_roots(folder):
            return ActionResult(False, "Ye folder allowed area ke bahar hai.")

        ext_to_cat: dict[str, str] = {}
        for category, extensions in self.cfg.categories.items():
            for ext in extensions:
                ext_to_cat[ext] = category

        moved = 0
        try:
            entries = [e for e in os.scandir(folder) if e.is_file()]
        except OSError as exc:
            return ActionResult(False, f"Folder padh nahi paaya: {exc}")

        for entry in entries:
            category = ext_to_cat.get(Path(entry.name).suffix.lower())
            if category is None:
                continue
            bucket = folder / category
            try:
                bucket.mkdir(exist_ok=True)
                target = bucket / entry.name
                if not target.exists():
                    shutil.move(entry.path, str(target))
                    moved += 1
            except (OSError, shutil.Error) as exc:
                self.log.warning("Could not organize %s: %s", entry.name, exc)

        if moved == 0:
            return ActionResult(True, f"{folder.name} mein organize karne ko kuch naya nahi mila.")
        return ActionResult(True, f"{folder.name} ke {moved} files category folders mein daal diye.")
