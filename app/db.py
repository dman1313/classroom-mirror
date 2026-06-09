"""SQLite storage. The schema IS the privacy architecture:

- no name column anywhere (guardrail 4)
- no embedding/template column (guardrail 2)
- nowhere to store emotion/attention/character (guardrail 3)
- mode2 tables have no per-child column at all (guardrail 7)

The schema-lock test asserts this file's EXPECTED_SCHEMA against the live
database, so any column added later fails the guardrails loudly.
"""
import os
import sqlite3
import time
from typing import Optional

from .validate import validate_lims, validate_class_code

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_NAME = "mirror.sqlite"

EXPECTED_SCHEMA = {
    "sessions": ["id", "mode", "phase", "class_code", "started_at", "ended_at"],
    "designations": [
        "session_id", "lims_code",
        "zone_x", "zone_y", "zone_w", "zone_h",
        "consent_confirmed_at",
    ],
    "mode1_minutes": ["session_id", "lims_code", "minute", "at_spot_pct", "movement_bucket"],
    "mode1_events": ["session_id", "lims_code", "ts", "kind"],
    "mode2_minutes": ["session_id", "minute", "bodies_detected", "hand_raises", "movement_bucket"],
}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('mode1', 'mode2')),
    phase TEXT NOT NULL CHECK (phase IN ('baseline', 'strategy', 'none')),
    class_code TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS designations (
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lims_code TEXT NOT NULL CHECK (length(lims_code) <= 12),
    zone_x REAL NOT NULL, zone_y REAL NOT NULL,
    zone_w REAL NOT NULL, zone_h REAL NOT NULL,
    consent_confirmed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mode1_minutes (
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lims_code TEXT NOT NULL,
    minute INTEGER NOT NULL,
    at_spot_pct REAL NOT NULL,
    movement_bucket TEXT NOT NULL CHECK (movement_bucket IN ('low', 'medium', 'high'))
);
CREATE TABLE IF NOT EXISTS mode1_events (
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    lims_code TEXT NOT NULL,
    ts REAL NOT NULL,
    kind TEXT NOT NULL CHECK (kind = 'hand_raise')
);
CREATE TABLE IF NOT EXISTS mode2_minutes (
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    minute INTEGER NOT NULL,
    bodies_detected INTEGER NOT NULL,
    hand_raises INTEGER NOT NULL,
    movement_bucket TEXT NOT NULL CHECK (movement_bucket IN ('low', 'medium', 'high'))
);
"""


class Database:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.path = os.path.join(self.data_dir, DB_NAME)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.executescript(_SCHEMA_SQL)
        self.conn.commit()

    # -- sessions ---------------------------------------------------------

    def start_session(self, mode: str, phase: str, class_code: str,
                      designations: Optional[list] = None) -> int:
        """designations: list of dicts {lims, zone:(x,y,w,h), consent: bool}.
        Mode 1 refuses to start without at least one designated child whose
        consent is confirmed (guardrail 6)."""
        class_code = validate_class_code(class_code)
        designations = designations or []
        if mode == "mode1":
            if not designations:
                raise PermissionError(
                    "An individual session needs at least one designated child "
                    "(a LIMS code and a zone)."
                )
            for d in designations:
                if not d.get("consent"):
                    raise PermissionError(
                        "Consent has not been confirmed for LIMS "
                        f"{d.get('lims', '?')} — the session will not start. "
                        "Tick the consent box only once consent is really recorded."
                    )
        elif mode == "mode2":
            if phase not in ("baseline", "strategy", "none"):
                phase = "none"
        else:
            raise ValueError("Unknown mode.")

        cur = self.conn.execute(
            "INSERT INTO sessions (mode, phase, class_code, started_at) VALUES (?,?,?,?)",
            (mode, phase, class_code, _now()),
        )
        session_id = cur.lastrowid
        for d in designations:
            lims = validate_lims(d["lims"])
            x, y, w, h = d["zone"]
            self.conn.execute(
                "INSERT INTO designations VALUES (?,?,?,?,?,?,?)",
                (session_id, lims, x, y, w, h, _now()),
            )
        self.conn.commit()
        return session_id

    def end_session(self, session_id: int):
        self.conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (_now(), session_id))
        self.conn.commit()

    def get_session(self, session_id: int):
        cur = self.conn.execute(
            "SELECT id, mode, phase, class_code, started_at, ended_at FROM sessions WHERE id=?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        keys = ["id", "mode", "phase", "class_code", "started_at", "ended_at"]
        return dict(zip(keys, row))

    def list_sessions(self):
        cur = self.conn.execute(
            "SELECT id, mode, phase, class_code, started_at, ended_at "
            "FROM sessions ORDER BY id DESC"
        )
        keys = ["id", "mode", "phase", "class_code", "started_at", "ended_at"]
        return [dict(zip(keys, r)) for r in cur.fetchall()]

    # -- mode 1 -----------------------------------------------------------

    def add_mode1_minute(self, session_id, lims_code, minute, at_spot_pct, movement_bucket):
        self.conn.execute(
            "INSERT INTO mode1_minutes VALUES (?,?,?,?,?)",
            (session_id, lims_code, minute, at_spot_pct, movement_bucket),
        )
        self.conn.commit()

    def add_mode1_event(self, session_id, lims_code, ts, kind="hand_raise"):
        self.conn.execute(
            "INSERT INTO mode1_events VALUES (?,?,?,?)",
            (session_id, lims_code, ts, kind),
        )
        self.conn.commit()

    def mode1_data(self, lims_code: str):
        """All sessions that designated this LIMS code, with per-session
        totals — grouped by phase for the before/after report."""
        lims_code = validate_lims(lims_code)
        cur = self.conn.execute(
            "SELECT DISTINCT s.id, s.phase, s.class_code, s.started_at "
            "FROM sessions s JOIN designations d ON d.session_id = s.id "
            "WHERE d.lims_code=? ORDER BY s.id",
            (lims_code,),
        )
        sessions = []
        for sid, phase, class_code, started in cur.fetchall():
            minutes = self.conn.execute(
                "SELECT minute, at_spot_pct, movement_bucket FROM mode1_minutes "
                "WHERE session_id=? AND lims_code=? ORDER BY minute",
                (sid, lims_code),
            ).fetchall()
            raises = self.conn.execute(
                "SELECT COUNT(*) FROM mode1_events WHERE session_id=? AND lims_code=?",
                (sid, lims_code),
            ).fetchone()[0]
            sessions.append({
                "id": sid, "phase": phase, "class_code": class_code,
                "started_at": started,
                "minutes": [
                    {"minute": m, "at_spot_pct": p, "movement_bucket": b}
                    for m, p, b in minutes
                ],
                "hand_raises": raises,
            })
        return sessions

    def list_mode1_lims(self):
        cur = self.conn.execute("SELECT DISTINCT lims_code FROM designations ORDER BY lims_code")
        return [r[0] for r in cur.fetchall()]

    # -- mode 2 -----------------------------------------------------------

    def add_mode2_minute(self, session_id, minute, bodies_detected, hand_raises, movement_bucket):
        self.conn.execute(
            "INSERT INTO mode2_minutes VALUES (?,?,?,?,?)",
            (session_id, minute, bodies_detected, hand_raises, movement_bucket),
        )
        self.conn.commit()

    def mode2_data(self, session_id: int):
        rows = self.conn.execute(
            "SELECT minute, bodies_detected, hand_raises, movement_bucket "
            "FROM mode2_minutes WHERE session_id=? ORDER BY minute",
            (session_id,),
        ).fetchall()
        return [
            {"minute": m, "bodies_detected": b, "hand_raises": h, "movement_bucket": mv}
            for m, b, h, mv in rows
        ]

    # -- erasure (guardrail 8) ---------------------------------------------

    def delete_lims(self, lims_code: str) -> int:
        """Remove every trace of a LIMS code. Returns rows removed."""
        lims_code = validate_lims(lims_code)
        n = 0
        for table in ("designations", "mode1_minutes", "mode1_events"):
            cur = self.conn.execute(f"DELETE FROM {table} WHERE lims_code=?", (lims_code,))
            n += cur.rowcount
        self.conn.commit()
        return n

    def delete_session(self, session_id: int) -> int:
        n = 0
        for table in ("designations", "mode1_minutes", "mode1_events", "mode2_minutes"):
            cur = self.conn.execute(f"DELETE FROM {table} WHERE session_id=?", (session_id,))
            n += cur.rowcount
        cur = self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        n += cur.rowcount
        self.conn.commit()
        return n

    def find_text_anywhere(self, needle: str) -> bool:
        """Used by erasure and no-names tests: scan every cell of every table."""
        for table, cols in EXPECTED_SCHEMA.items():
            for row in self.conn.execute(f"SELECT * FROM {table}").fetchall():
                if any(needle == str(v) for v in row):
                    return True
        return False

    def live_schema(self):
        out = {}
        tables = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (name,) in tables:
            cols = self.conn.execute(f"PRAGMA table_info({name})").fetchall()
            out[name] = [c[1] for c in cols]
        return out

    def close(self):
        self.conn.close()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
