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


    def test_v04_schema_and_data_survive_v05_meeting_migration_atomically(self):
        data_dir = Path(tempfile.mkdtemp(prefix="marsad-v04-to-v05-migration-"))
        db_path = data_dir / "marsad_alinjazat.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                specialization TEXT,
                qualification TEXT,
                experience_years INTEGER NOT NULL DEFAULT 0,
                workload INTEGER NOT NULL DEFAULT 0,
                cv_completion INTEGER NOT NULL DEFAULT 0 CHECK (cv_completion BETWEEN 0 AND 100),
                email TEXT,
                phone TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE upload_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE RESTRICT,
                request_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT NOT NULL,
                title TEXT NOT NULL,
                deadline TEXT,
                notes TEXT,
                allowed_files TEXT NOT NULL DEFAULT 'PDF / Word / Excel',
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'waiting_upload',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER REFERENCES upload_requests(id) ON DELETE SET NULL,
                teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT,
                grade TEXT,
                academic_year TEXT,
                original_name TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                storage_provider TEXT NOT NULL,
                storage_file_id TEXT,
                storage_path TEXT,
                web_view_link TEXT,
                status TEXT NOT NULL DEFAULT 'inbox',
                uploaded_at TEXT NOT NULL,
                approved_at TEXT
            );
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
            CREATE TABLE activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE teacher_profiles (
                teacher_id INTEGER PRIMARY KEY REFERENCES teachers(id) ON DELETE CASCADE,
                employee_number TEXT,
                school_join_year INTEGER CHECK (school_join_year IS NULL OR school_join_year BETWEEN 1950 AND 2100),
                grades TEXT,
                responsibilities TEXT,
                professional_summary TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE teacher_cv_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                item_type TEXT NOT NULL CHECK (item_type IN ('qualification', 'course', 'achievement', 'experience')),
                title TEXT NOT NULL,
                organization TEXT,
                start_year INTEGER CHECK (start_year IS NULL OR start_year BETWEEN 1950 AND 2100),
                end_year INTEGER CHECK (end_year IS NULL OR end_year BETWEEN 1950 AND 2100),
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE event_teacher_links (
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'مشارك',
                created_at TEXT NOT NULL,
                PRIMARY KEY (event_id, teacher_id)
            );
            CREATE TABLE event_media_meta (
                media_id INTEGER PRIMARY KEY REFERENCES event_media(id) ON DELETE CASCADE,
                caption TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
                is_cover INTEGER NOT NULL DEFAULT 0 CHECK (is_cover IN (0, 1)),
                updated_at TEXT NOT NULL
            );
            CREATE INDEX idx_requests_status ON upload_requests(status);
            CREATE INDEX idx_documents_request ON documents(request_id);
            CREATE INDEX idx_activities_created ON activities(created_at DESC);
            CREATE INDEX idx_teacher_cv_items_teacher ON teacher_cv_items(teacher_id, item_type);
            CREATE INDEX idx_event_teacher_links_event ON event_teacher_links(event_id, teacher_id);
            CREATE INDEX idx_event_media_event ON event_media(event_id);
            CREATE INDEX idx_event_media_meta_position ON event_media_meta(position, media_id);
            """
        )
        now = "2026-08-14T10:00:00+00:00"
        conn.execute("INSERT INTO settings VALUES (?,?,?)", ("school_name", "مدرسة اختبار", now))
        conn.execute(
            "INSERT INTO teachers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (41, "معلم محفوظ", "الفيزياء", "فيزياء", "بكالوريوس تربية", 11, 18, 88, "keep@example.edu", "99110000", now, now),
        )
        conn.execute(
            "INSERT INTO teacher_profiles VALUES (?,?,?,?,?,?,?)",
            (41, "EMP-41", 2019, "العاشر", "منسق مادة", "ملخص مهني محفوظ", now),
        )
        conn.execute(
            "INSERT INTO teacher_cv_items VALUES (?,?,?,?,?,?,?,?,?,?)",
            (51, 41, "course", "دورة محفوظة", "جهة تدريب", 2025, 2025, "وصف محفوظ", now, now),
        )
        conn.execute(
            "INSERT INTO upload_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (61, 41, "اختبار", "الفيزياء", "العاشر", "طلب محفوظ", "2026-09-01", "ملاحظة", "PDF فقط", "hash-v04-61", "approved", "2026-09-30T00:00:00+00:00", now, now),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (71, 61, 41, "وثيقة محفوظة", "اختبار", "الفيزياء", "العاشر", "2026/2027", "exam.pdf", "application/pdf", 1234, "local", None, "uploads/inbox/exam.pdf", None, "approved", now, now),
        )
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (81, "فعالية محفوظة", "فعالية", "2026-10-01", "المدرسة", "العاشر", 20, "هدف", "تنفيذ", "مخرج", "توصية", "teal", now, now),
        )
        conn.execute(
            "INSERT INTO event_media VALUES (?,?,?,?,?,?,?,?,?,?)",
            (91, 81, "photo.jpg", "image/jpeg", 2222, "local", None, "uploads/events/81/photo.jpg", None, now),
        )
        conn.execute("INSERT INTO event_teacher_links VALUES (?,?,?,?)", (81, 41, "مشارك", now))
        conn.execute("INSERT INTO event_media_meta VALUES (?,?,?,?,?)", (91, "غلاف محفوظ", 0, 1, now))
        conn.execute("INSERT INTO activities VALUES (?,?,?,?,?,?,?)", (101, "event", "نشاط محفوظ", "تفصيل", "event", 81, now))
        conn.commit()

        old_tables = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        }
        old_indexes = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
            )
        }
        expected_old_names = {
            "settings", "teachers", "upload_requests", "documents", "events", "event_media", "activities",
            "teacher_profiles", "teacher_cv_items", "event_teacher_links", "event_media_meta",
        }
        self.assertEqual(set(old_tables), expected_old_names)
        old_data = {
            name: conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
            for name in sorted(expected_old_names)
        }
        conn.close()

        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["APP_DATA_DIR"] = str(data_dir)
        env["APP_UPLOADS_DIR"] = str(data_dir / "inbox")
        env["APP_EVENT_UPLOADS_DIR"] = str(data_dir / "events")
        env["STORAGE_MODE"] = "local"
        code = (
            "from server.db import init_db; init_db(); "
            "import sqlite3, os, json; "
            "db=os.path.join(os.environ['APP_DATA_DIR'],'marsad_alinjazat.sqlite3'); "
            "c=sqlite3.connect(db); "
            "print(json.dumps({'integrity':c.execute('pragma integrity_check').fetchone()[0],"
            "'fk':c.execute('pragma foreign_key_check').fetchall()}))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code], cwd=repo_root, env=env,
            capture_output=True, text=True, check=True,
        )
        status = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(status["integrity"], "ok")
        self.assertEqual(status["fk"], [])

        conn = sqlite3.connect(db_path)
        new_tables = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        }
        new_indexes = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
            )
        }
        for name, sql in old_tables.items():
            self.assertEqual(new_tables[name], sql, f"old table definition changed: {name}")
        for name, sql in old_indexes.items():
            self.assertEqual(new_indexes[name], sql, f"old index definition changed: {name}")
        for name, rows in old_data.items():
            self.assertEqual(conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall(), rows, f"old data changed: {name}")

        self.assertEqual(
            set(new_tables) - expected_old_names,
            {"meetings", "meeting_attendees", "meeting_decisions"},
        )
        self.assertTrue({"idx_meetings_date", "idx_meeting_attendees_meeting", "idx_meeting_decisions_meeting", "idx_meeting_decisions_open"}.issubset(new_indexes))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meeting_attendees").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meeting_decisions").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
