"""Only aggregate recaps live on disk. Expire after 30 days."""

import json
from pathlib import Path
import sqlite3
import threading
import time


class Store:
    def __init__(self, root):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "recaps.sqlite3"
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS recaps (id INTEGER PRIMARY KEY, created REAL NOT NULL, summary TEXT NOT NULL)"
        )
        self._expire()

    def _expire(self):
        self.db.execute(
            "DELETE FROM recaps WHERE created < ?", (time.time() - 30 * 86400,)
        )
        self.db.commit()

    def save(self, summary):
        with self.lock:
            self._expire()
            cur = self.db.execute(
                "INSERT INTO recaps(created,summary) VALUES (?,?)",
                (time.time(), json.dumps(summary)),
            )
            self.db.commit()
            return cur.lastrowid

    def list(self):
        with self.lock:
            self._expire()
            return [
                {"id": n, "created": created, **json.loads(summary)}
                for n, created, summary in self.db.execute(
                    "SELECT id,created,summary FROM recaps ORDER BY id DESC LIMIT 100"
                )
            ]

    def delete(self, n=None):
        with self.lock:
            if n is None:
                self.db.execute("DELETE FROM recaps")
            else:
                self.db.execute("DELETE FROM recaps WHERE id=?", (n,))
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()
