import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MarsadMigrationTests(unittest.TestCase):
    def test_v03_event_media_is_preserved_and_metadata_is_backfilled(self):
        data_dir = Path(tempfile.mkdtemp(prefix="marsad-v03-migration-"))
        db_path = data_dir / "marsad_alinjazat.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,
                location TEXT,
                audience TEXT,
                participant_count INTEGER NOT NULL DEFAULT 0,
                goals TEXT,
                summary TEXT,
                outcomes TEXT,
                recommendations TEXT,
                cover_tone TEXT NOT NULL DEFAULT 'teal',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE event_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                original_name TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                storage_provider TEXT NOT NULL,
                storage_file_id TEXT,
                storage_path TEXT,
                web_view_link TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        event_row = (
            71, "فعالية قديمة", "فعالية", "2026-05-10", "المدرسة", "الصف العاشر", 24,
            "هدف قديم", "تنفيذ قديم", "مخرج قديم", "توصية قديمة", "teal",
            "2026-05-01T08:00:00+00:00", "2026-05-10T12:00:00+00:00",
        )
        media_row = (
            91, 71, "legacy.jpg", "image/jpeg", 12345, "local", None,
            "uploads/events/71/legacy.jpg", None, "2026-05-10T12:30:00+00:00",
        )
        conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", event_row)
        conn.execute("INSERT INTO event_media VALUES (?,?,?,?,?,?,?,?,?,?)", media_row)
        conn.commit()
        before_event = conn.execute("SELECT * FROM events WHERE id=71").fetchone()
        before_media = conn.execute("SELECT * FROM event_media WHERE id=91").fetchone()
        conn.close()

        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["APP_DATA_DIR"] = str(data_dir)
        env["APP_UPLOADS_DIR"] = str(data_dir / "inbox")
        env["APP_EVENT_UPLOADS_DIR"] = str(data_dir / "events")
        code = (
            "from server.db import init_db; init_db(); "
            "import sqlite3, os, json; "
            "db=os.path.join(os.environ['APP_DATA_DIR'],'marsad_alinjazat.sqlite3'); "
            "c=sqlite3.connect(db); "
            "print(json.dumps({'integrity':c.execute('pragma integrity_check').fetchone()[0],"
            "'fk':c.execute('pragma foreign_key_check').fetchall()}))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        status = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(status["integrity"], "ok")
        self.assertEqual(status["fk"], [])

        conn = sqlite3.connect(db_path)
        after_event = conn.execute("SELECT * FROM events WHERE id=71").fetchone()
        after_media = conn.execute("SELECT * FROM event_media WHERE id=91").fetchone()
        meta = conn.execute("SELECT caption, position, is_cover FROM event_media_meta WHERE media_id=91").fetchone()
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()

        self.assertEqual(before_event, after_event)
        self.assertEqual(before_media, after_media)
        self.assertEqual(meta, ("", 0, 1))
        self.assertIn("event_media_meta", tables)
        self.assertIn("event_teacher_links", tables)


if __name__ == "__main__":
    unittest.main()
