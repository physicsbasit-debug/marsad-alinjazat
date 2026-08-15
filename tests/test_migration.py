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
            {"meetings", "meeting_attendees", "meeting_decisions", "curriculum_plans", "curriculum_units"},
        )
        self.assertTrue({"idx_meetings_date", "idx_meeting_attendees_meeting", "idx_meeting_decisions_meeting", "idx_meeting_decisions_open"}.issubset(new_indexes))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meeting_attendees").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM meeting_decisions").fetchone()[0], 0)
        conn.close()

    def test_v05_schema_and_data_survive_v06_planning_migration_atomically(self):
        data_dir = Path(tempfile.mkdtemp(prefix="marsad-v05-to-v06-migration-"))
        db_path = data_dir / "marsad_alinjazat.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(r"""
-- table activities
CREATE TABLE activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                created_at TEXT NOT NULL
            );
-- table documents
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
-- table event_media
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
-- table event_media_meta
CREATE TABLE event_media_meta (
                media_id INTEGER PRIMARY KEY REFERENCES event_media(id) ON DELETE CASCADE,
                caption TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
                is_cover INTEGER NOT NULL DEFAULT 0 CHECK (is_cover IN (0, 1)),
                updated_at TEXT NOT NULL
            );
-- table event_teacher_links
CREATE TABLE event_teacher_links (
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'مشارك',
                created_at TEXT NOT NULL,
                PRIMARY KEY (event_id, teacher_id)
            );
-- table events
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
-- table meeting_attendees
CREATE TABLE meeting_attendees (
                meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                attendance_status TEXT NOT NULL DEFAULT 'present' CHECK (attendance_status IN ('present', 'absent', 'excused')),
                created_at TEXT NOT NULL,
                PRIMARY KEY (meeting_id, teacher_id)
            );
-- table meeting_decisions
CREATE TABLE meeting_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                responsible_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
                responsible_name TEXT,
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'in_progress', 'completed', 'cancelled')),
                notes TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
-- table meetings
CREATE TABLE meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                meeting_type TEXT NOT NULL DEFAULT 'اجتماع قسم',
                meeting_date TEXT NOT NULL,
                meeting_time TEXT,
                location TEXT,
                agenda TEXT,
                discussion_summary TEXT,
                notes TEXT,
                academic_year TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'held', 'cancelled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
-- table settings
CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
-- table teacher_cv_items
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
-- table teacher_profiles
CREATE TABLE teacher_profiles (
                teacher_id INTEGER PRIMARY KEY REFERENCES teachers(id) ON DELETE CASCADE,
                employee_number TEXT,
                school_join_year INTEGER CHECK (school_join_year IS NULL OR school_join_year BETWEEN 1950 AND 2100),
                grades TEXT,
                responsibilities TEXT,
                professional_summary TEXT,
                updated_at TEXT NOT NULL
            );
-- table teachers
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
-- table upload_requests
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
-- index idx_activities_created
CREATE INDEX idx_activities_created ON activities(created_at DESC);
-- index idx_documents_request
CREATE INDEX idx_documents_request ON documents(request_id);
-- index idx_event_media_event
CREATE INDEX idx_event_media_event ON event_media(event_id);
-- index idx_event_media_meta_position
CREATE INDEX idx_event_media_meta_position ON event_media_meta(position, media_id);
-- index idx_event_teacher_links_event
CREATE INDEX idx_event_teacher_links_event ON event_teacher_links(event_id, teacher_id);
-- index idx_meeting_attendees_meeting
CREATE INDEX idx_meeting_attendees_meeting ON meeting_attendees(meeting_id, teacher_id);
-- index idx_meeting_decisions_meeting
CREATE INDEX idx_meeting_decisions_meeting ON meeting_decisions(meeting_id, status, due_date);
-- index idx_meeting_decisions_open
CREATE INDEX idx_meeting_decisions_open ON meeting_decisions(status, due_date);
-- index idx_meetings_date
CREATE INDEX idx_meetings_date ON meetings(meeting_date DESC, id DESC);
-- index idx_requests_status
CREATE INDEX idx_requests_status ON upload_requests(status);
-- index idx_teacher_cv_items_teacher
CREATE INDEX idx_teacher_cv_items_teacher ON teacher_cv_items(teacher_id, item_type);

        """)
        now = "2026-08-15T07:40:00+00:00"
        conn.execute("INSERT INTO settings (key,value,updated_at) VALUES (?,?,?)", ("school_name", "مدرسة محفوظة", now))
        conn.execute("INSERT INTO teachers (id,name,subject,specialization,qualification,experience_years,workload,cv_completion,email,phone,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (41,"معلم محفوظ","الفيزياء","فيزياء","بكالوريوس",12,18,90,"keep@example.edu","99112233",now,now))
        conn.execute("INSERT INTO teacher_profiles (teacher_id,employee_number,school_join_year,grades,responsibilities,professional_summary,updated_at) VALUES (?,?,?,?,?,?,?)", (41,"EMP-41",2019,"العاشر","منسق","ملخص",now))
        conn.execute("INSERT INTO teacher_cv_items (id,teacher_id,item_type,title,organization,start_year,end_year,description,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (51,41,"course","دورة محفوظة","جهة",2025,2025,"وصف",now,now))
        conn.execute("INSERT INTO upload_requests (id,teacher_id,request_type,subject,grade,title,deadline,notes,allowed_files,token_hash,status,expires_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (61,41,"اختبار","الفيزياء","العاشر","طلب محفوظ","2026-09-01","ملاحظة","PDF فقط","hash-v05-61","approved","2026-09-30T00:00:00+00:00",now,now))
        conn.execute("INSERT INTO documents (id,request_id,teacher_id,title,category,subject,grade,academic_year,original_name,mime_type,size_bytes,storage_provider,storage_file_id,storage_path,web_view_link,status,uploaded_at,approved_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (71,61,41,"وثيقة محفوظة","اختبار","الفيزياء","العاشر","2026/2027","exam.pdf","application/pdf",1234,"local",None,"uploads/inbox/exam.pdf",None,"approved",now,now))
        conn.execute("INSERT INTO events (id,title,event_type,event_date,location,audience,participant_count,goals,summary,outcomes,recommendations,cover_tone,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (81,"فعالية محفوظة","فعالية","2026-10-01","المدرسة","العاشر",20,"هدف","تنفيذ","مخرج","توصية","teal",now,now))
        conn.execute("INSERT INTO event_media (id,event_id,original_name,mime_type,size_bytes,storage_provider,storage_file_id,storage_path,web_view_link,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (91,81,"photo.jpg","image/jpeg",2222,"local",None,"uploads/events/81/photo.jpg",None,now))
        conn.execute("INSERT INTO event_teacher_links (event_id,teacher_id,role,created_at) VALUES (?,?,?,?)", (81,41,"مشارك",now))
        conn.execute("INSERT INTO event_media_meta (media_id,caption,position,is_cover,updated_at) VALUES (?,?,?,?,?)", (91,"غلاف محفوظ",0,1,now))
        conn.execute("INSERT INTO meetings (id,title,meeting_type,meeting_date,meeting_time,location,agenda,discussion_summary,notes,academic_year,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (111,"اجتماع محفوظ","اجتماع قسم","2026-09-03","10:30","قاعة العلوم","محور","نقاش","ملاحظة","2026/2027","held",now,now))
        conn.execute("INSERT INTO meeting_attendees (meeting_id,teacher_id,attendance_status,created_at) VALUES (?,?,?,?)", (111,41,"present",now))
        conn.execute("INSERT INTO meeting_decisions (id,meeting_id,title,responsible_teacher_id,responsible_name,due_date,status,notes,completed_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (121,111,"قرار محفوظ",41,"معلم محفوظ","2026-09-10","in_progress","متابعة",None,now,now))
        conn.execute("INSERT INTO activities (id,activity_type,title,detail,entity_type,entity_id,created_at) VALUES (?,?,?,?,?,?,?)", (131,"meeting","نشاط محفوظ","تفصيل","meeting",111,now))
        conn.commit()

        old_tables = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")}
        old_indexes = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")}
        expected_old_names = {
            "settings", "teachers", "upload_requests", "documents", "events", "event_media", "activities",
            "teacher_profiles", "teacher_cv_items", "event_teacher_links", "event_media_meta",
            "meetings", "meeting_attendees", "meeting_decisions",
        }
        self.assertEqual(set(old_tables), expected_old_names)
        old_data = {name: conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in sorted(expected_old_names)}
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
        completed = subprocess.run([sys.executable, "-c", code], cwd=repo_root, env=env, capture_output=True, text=True, check=True)
        status = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(status["integrity"], "ok")
        self.assertEqual(status["fk"], [])

        conn = sqlite3.connect(db_path)
        new_tables = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")}
        new_indexes = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")}
        for name, sql in old_tables.items():
            self.assertEqual(new_tables[name], sql, f"old table definition changed: {name}")
        for name, sql in old_indexes.items():
            self.assertEqual(new_indexes[name], sql, f"old index definition changed: {name}")
        for name, rows in old_data.items():
            self.assertEqual(conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall(), rows, f"old data changed: {name}")
        self.assertEqual(set(new_tables) - expected_old_names, {"curriculum_plans", "curriculum_units"})
        self.assertTrue({"idx_curriculum_plans_scope", "idx_curriculum_units_plan", "idx_curriculum_units_due"}.issubset(new_indexes))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM curriculum_plans").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM curriculum_units").fetchone()[0], 0)
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        conn.close()


if __name__ == "__main__":
    unittest.main()
