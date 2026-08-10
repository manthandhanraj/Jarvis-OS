"""SQLite-backed persistence for facts and the action history."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from config.settings import MemorySettings
from memory.models import ActionRecord, Fact
from utils.logger import get_logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'general',
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT '',
    phrase      TEXT NOT NULL DEFAULT '',
    success     INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_created ON actions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts (category);
"""


class MemoryStore:
    def __init__(self, cfg: MemorySettings, data_dir: Path) -> None:
        self.cfg = cfg
        self.log = get_logger("jarvis.memory.store")
        self._db_path = data_dir / cfg.db_file
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self.log.info("Memory store ready at %s.", self._db_path.name)

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("MemoryStore.initialize() not called.")
        return self._conn

    # ---- facts -------------------------------------------------------------

    def set_fact(self, key: str, value: str, category: str = "general") -> None:
        key = key.strip().lower()
        if not key or not value.strip():
            return
        self._db.execute(
            "INSERT INTO facts (key, value, category, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "category=excluded.category, updated_at=excluded.updated_at",
            (key, value.strip(), category, time.time()),
        )
        self.log.info("Fact saved: %s = %r", key, value.strip())

    def get_fact(self, key: str) -> Fact | None:
        row = self._db.execute(
            "SELECT key, value, category, updated_at FROM facts WHERE key = ?",
            (key.strip().lower(),),
        ).fetchone()
        return self._row_to_fact(row) if row else None

    def search_facts(self, term: str, limit: int | None = None) -> list[Fact]:
        like = f"%{term.strip().lower()}%"
        rows = self._db.execute(
            "SELECT key, value, category, updated_at FROM facts "
            "WHERE key LIKE ? OR lower(value) LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (like, like, limit or self.cfg.recall_limit),
        ).fetchall()
        return [self._row_to_fact(r) for r in rows]

    def all_facts(self, limit: int | None = None) -> list[Fact]:
        rows = self._db.execute(
            "SELECT key, value, category, updated_at FROM facts "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit or self.cfg.recall_limit,),
        ).fetchall()
        return [self._row_to_fact(r) for r in rows]

    def delete_fact(self, key: str) -> bool:
        cur = self._db.execute("DELETE FROM facts WHERE key = ?", (key.strip().lower(),))
        return cur.rowcount > 0

    def clear_facts(self) -> int:
        cur = self._db.execute("DELETE FROM facts")
        return cur.rowcount

    # ---- actions -----------------------------------------------------------

    def add_action(self, record: ActionRecord) -> None:
        self._db.execute(
            "INSERT INTO actions (command, target, phrase, success, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (record.command, record.target, record.phrase,
             1 if record.success else 0, record.created_at),
        )

    def recent_actions(self, limit: int | None = None) -> list[ActionRecord]:
        rows = self._db.execute(
            "SELECT command, target, phrase, success, created_at FROM actions "
            "ORDER BY created_at DESC LIMIT ?",
            (limit or self.cfg.context_window,),
        ).fetchall()
        return [self._row_to_action(r) for r in rows]

    def prune_actions(self, keep: int = 500) -> None:
        self._db.execute(
            "DELETE FROM actions WHERE id NOT IN "
            "(SELECT id FROM actions ORDER BY created_at DESC LIMIT ?)",
            (keep,),
        )

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> Fact:
        return Fact(key=row["key"], value=row["value"],
                    category=row["category"], updated_at=row["updated_at"])

    @staticmethod
    def _row_to_action(row: sqlite3.Row) -> ActionRecord:
        return ActionRecord(command=row["command"], target=row["target"],
                            phrase=row["phrase"], success=bool(row["success"]),
                            created_at=row["created_at"])

    def shutdown(self) -> None:
        if self._conn is not None:
            try:
                self.prune_actions()
                self._conn.close()
            except sqlite3.Error as exc:
                self.log.error("Error closing memory DB: %s", exc)
        self._conn = None
