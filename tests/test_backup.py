import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.backup import create_database_backup, restore_database_backup, validate_database_file


REQUIRED_SCHEMA = """
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE teachers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE meetings (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE achievement_assessments (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
"""


class MarsadBackupTests(unittest.TestCase):
    def make_db(self, path: Path, marker: str) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(REQUIRED_SCHEMA)
        conn.execute("INSERT INTO settings VALUES ('marker', ?, '2026-08-16T00:00:00+00:00')", (marker,))
        conn.execute("INSERT INTO teachers VALUES (1, 'معلم النسخة')")
        conn.commit()
        conn.close()

    def marker(self, path: Path) -> str:
        conn = sqlite3.connect(path)
        try:
            return conn.execute("SELECT value FROM settings WHERE key='marker'").fetchone()[0]
        finally:
            conn.close()

    def test_create_validate_and_restore_backup(self):
        root = Path(tempfile.mkdtemp(prefix="marsad-backup-test-"))
        active = root / "marsad.sqlite3"
        backup_dir = root / "backups"
        self.make_db(active, "before")

        backup = create_database_backup(label="manual-test", db_path=active, backup_dir=backup_dir)
        self.assertIsNotNone(backup)
        assert backup is not None
        verified = validate_database_file(backup)
        self.assertTrue(verified["ok"])
        self.assertEqual(len(verified["sha256"]), 64)

        conn = sqlite3.connect(active)
        conn.execute("UPDATE settings SET value='after' WHERE key='marker'")
        conn.commit()
        conn.close()
        self.assertEqual(self.marker(active), "after")

        restored = restore_database_backup(
            backup,
            confirmation="RESTORE",
            db_path=active,
            backup_dir=backup_dir,
        )
        self.assertTrue(restored["ok"])
        self.assertEqual(self.marker(active), "before")
        self.assertIsNotNone(restored["safetyBackup"])
        self.assertTrue(Path(restored["safetyBackup"]).exists())

    def test_backup_accepts_legacy_marsad_schema_before_migration(self):
        root = Path(tempfile.mkdtemp(prefix="marsad-backup-legacy-"))
        legacy = root / "legacy.sqlite3"
        backup_dir = root / "backups"
        conn = sqlite3.connect(legacy)
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO events VALUES (1, 'فعالية قديمة')")
        conn.commit()
        conn.close()

        backup = create_database_backup(label="startup", db_path=legacy, backup_dir=backup_dir)
        self.assertIsNotNone(backup)
        assert backup is not None
        verified = validate_database_file(backup)
        self.assertTrue(verified["ok"])

    def test_restore_requires_explicit_confirmation_and_valid_database(self):
        root = Path(tempfile.mkdtemp(prefix="marsad-backup-guard-"))
        active = root / "marsad.sqlite3"
        backup_dir = root / "backups"
        self.make_db(active, "safe")
        invalid = root / "not-a-db.sqlite3"
        invalid.write_text("not sqlite", encoding="utf-8")

        with self.assertRaises(ValueError):
            restore_database_backup(active, confirmation="NO", db_path=active, backup_dir=backup_dir)
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            validate_database_file(invalid)
        self.assertEqual(self.marker(active), "safe")


if __name__ == "__main__":
    unittest.main()
