"""SQLite + encrypted identity book. Schema has no name column."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .crypto import load_or_create_key, uses_dpapi
from .identity import IdentityBook
from .paths import ensure_layout

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    sensitivity TEXT NOT NULL,
    recap_json TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    anon_number INTEGER,
    kind TEXT NOT NULL,
    t REAL NOT NULL
);
"""

FORBIDDEN_COLUMNS = ("name", "lims", "email", "full_name")


class Store:
    def __init__(self, root: Path | None = None):
        self.root = ensure_layout(root)
        self.db_path = self.root / "state" / "classroom-mirror.sqlite3"
        self.key_path = self.root / "config" / "template.key"
        self.book_path = self.root / "state" / "identities.bin"
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._assert_schema()
        # Windows DPAPI is current-user scoped, so the wrap key is not stored
        # beside the database. Other hosts keep a 600 HMAC key in config/.
        self.key = None if uses_dpapi() else load_or_create_key(self.key_path)
        self.book = IdentityBook.load_wrapped(self.book_path, self.key)

    def _assert_schema(self) -> None:
        rows = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for (table,) in rows:
            if str(table).startswith("sqlite_"):
                continue
            cols = [
                r[1].lower()
                for r in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            ]
            for forbidden in FORBIDDEN_COLUMNS:
                if forbidden in cols:
                    raise RuntimeError(f"forbidden column {forbidden} on {table}")

    def persist_book(self) -> None:
        self.book.save_wrapped(self.book_path, self.key)

    def delete_one(self, number: int) -> bool:
        ok = self.book.delete_one(number)
        self.persist_book()
        return ok

    def delete_all(self) -> int:
        n = self.book.delete_all()
        self.persist_book()
        if self.book_path.is_file():
            self.book_path.unlink()
        return n

    def record_session(self, started_at: str, sensitivity: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions(started_at, sensitivity) VALUES (?, ?)",
            (started_at, sensitivity),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def finish_session(self, session_id: int, ended_at: str, recap_json: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET ended_at=?, recap_json=? WHERE id=?",
            (ended_at, recap_json, session_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self.persist_book()
        self._conn.close()
