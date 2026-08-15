from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')
DATA_DIR = Path(os.getenv("APP_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "marsad_alinjazat.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teachers (
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

            CREATE TABLE IF NOT EXISTS upload_requests (
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

            CREATE TABLE IF NOT EXISTS documents (
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

            CREATE TABLE IF NOT EXISTS events (
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

            CREATE TABLE IF NOT EXISTS event_media (
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

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teacher_profiles (
                teacher_id INTEGER PRIMARY KEY REFERENCES teachers(id) ON DELETE CASCADE,
                employee_number TEXT,
                school_join_year INTEGER CHECK (school_join_year IS NULL OR school_join_year BETWEEN 1950 AND 2100),
                grades TEXT,
                responsibilities TEXT,
                professional_summary TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teacher_cv_items (
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

            CREATE INDEX IF NOT EXISTS idx_requests_status ON upload_requests(status);
            CREATE INDEX IF NOT EXISTS idx_documents_request ON documents(request_id);
            CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_teacher_cv_items_teacher ON teacher_cv_items(teacher_id, item_type);
            """
        )
        _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    teacher_count = conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
    if teacher_count == 0:
        now = utc_now()
        teachers = [
            ("أحمد السالمي", "الفيزياء", "فيزياء", "بكالوريوس تربية", 12, 18, 100, "ahmed@example.edu", None),
            ("خالد الهنائي", "الكيمياء", "كيمياء", "بكالوريوس تربية", 8, 20, 78, "khalid@example.edu", None),
            ("محمد المعمري", "العلوم", "علوم عامة", "بكالوريوس تربية", 15, 16, 92, "mohammed@example.edu", None),
            ("سالم الرواحي", "الأحياء", "أحياء", "بكالوريوس تربية", 10, 19, 84, "salim@example.edu", None),
            ("يوسف البلوشي", "العلوم", "علوم عامة", "بكالوريوس تربية", 6, 21, 65, "yousuf@example.edu", None),
            ("ناصر الحوسني", "الفيزياء", "فيزياء", "ماجستير مناهج", 13, 17, 95, "nasser@example.edu", None),
        ]
        conn.executemany(
            """
            INSERT INTO teachers
            (name, subject, specialization, qualification, experience_years, workload, cv_completion, email, phone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(*teacher, now, now) for teacher in teachers],
        )

    request_count = conn.execute("SELECT COUNT(*) FROM upload_requests").fetchone()[0]
    if request_count == 0:
        now = utc_now()
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0).isoformat()
        seed_requests = [
            (1, "اختبار", "الفيزياء", "العاشر", "الاختبار القصير الأول", "2026-08-15", "", "PDF / Word / Excel", "review"),
            (2, "خطة فصلية", "الكيمياء", "العاشر", "الخطة الفصلية", "2026-08-16", "", "PDF / Word / Excel", "received"),
            (3, "نشاط", "العلوم", "الثامن", "نموذج نشاط علمي", "2026-08-13", "", "PDF / Word / Excel", "late"),
            (4, "تحليل نتائج", "الأحياء", "التاسع", "تحليل النتائج", "2026-08-20", "", "PDF / Word / Excel", "approved"),
        ]
        for teacher_id, request_type, subject, grade, title, deadline, notes, allowed, status in seed_requests:
            token_hash = hashlib.sha256(secrets.token_urlsafe(24).encode()).hexdigest()
            conn.execute(
                """
                INSERT INTO upload_requests
                (teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, token_hash, status, expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (teacher_id, request_type, subject, grade, title, deadline, notes, allowed, token_hash, status, expires, now, now),
            )

    event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if event_count == 0:
        now = utc_now()
        events = [
            ("أسبوع العلوم", "فعالية", "2026-10-12", "المدرسة", "طلبة الصفوف 8-10", 42, "تعزيز الثقافة العلمية", "فعاليات وتجارب تعليمية ومسابقات", "مشاركة واسعة", "توسيع مشاركة الطلبة", "teal"),
            ("مسابقة الفيزياء", "مسابقة", "2026-11-27", "قاعة متعددة الأغراض", "الصف العاشر", 18, "تنمية حل المشكلات", "مسابقة تطبيقية", "تحسن التفاعل", "تكرارها فصليًا", "navy"),
            ("مبادرة اقرأ علمًا", "مبادرة", "2026-09-30", "مركز مصادر التعلم", "الصف التاسع", 31, "تعزيز القراءة العلمية", "قراءات قصيرة ونقاشات", "منتجات طلابية", "ربطها بالمنهج", "gold"),
        ]
        conn.executemany(
            """
            INSERT INTO events
            (title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(*event, now, now) for event in events],
        )

    activity_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if activity_count == 0:
        now = utc_now()
        activities = [
            ("document", "خالد رفع الخطة الفصلية", "الكيمياء • الصف العاشر", "request", 2, now),
            ("request", "طلب اختبار جديد", "الفيزياء • الصف العاشر", "request", 1, now),
            ("event", "توثيق مبادرة اقرأ علمًا", "31 مشاركًا", "event", 3, now),
        ]
        conn.executemany(
            """INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            activities,
        )


def get_setting(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
