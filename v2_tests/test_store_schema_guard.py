"""Regression: the privacy schema guard must ignore SQLite internal tables."""

import tempfile
import unittest
from pathlib import Path

from v2_app.store import Store


class StoreSchemaGuardTests(unittest.TestCase):
    def test_init_survives_sqlite_sequence_from_autoincrement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(root)
            # Inserting into an AUTOINCREMENT table materializes the internal
            # sqlite_sequence table, whose schema has a column named "name".
            store.record_session("2026-01-01T00:00:00Z", "low")
            seq = store._conn.execute(
                "SELECT name FROM sqlite_master WHERE name='sqlite_sequence'"
            ).fetchall()
            self.assertEqual(seq, [("sqlite_sequence",)])
            store.close()

            # Re-opening runs _assert_schema against a DB that now contains
            # sqlite_sequence; this used to raise RuntimeError.
            reopened = Store(root)
            reopened.close()

    def test_forbidden_column_guard_still_rejects_app_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store._conn.execute("CREATE TABLE roster (name TEXT)")
            with self.assertRaises(RuntimeError):
                store._assert_schema()
            store.close()


if __name__ == "__main__":
    unittest.main()
