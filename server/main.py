from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import drive
from .db import BASE_DIR, connect, init_db, row_to_dict, utc_now

load_dotenv(BASE_DIR / ".env")
init_db()

APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:8000").rstrip("/")
APP_FRONTEND_URL = os.getenv("APP_FRONTEND_URL", APP_PUBLIC_URL).rstrip("/")
ACADEMIC_YEAR = os.getenv("ACADEMIC_YEAR", "2026/2027")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOADS_DIR = Path(os.getenv("APP_UPLOADS_DIR", BASE_DIR / "uploads" / "inbox"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
EVENT_UPLOADS_DIR = Path(os.getenv("APP_EVENT_UPLOADS_DIR", BASE_DIR / "uploads" / "events"))
EVENT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="مرصد الإنجازات API", version="0.4.0")


class CreateRequestPayload(BaseModel):
    teacherId: int
    requestType: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=2, max_length=80)
    grade: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=3, max_length=160)
    deadline: str | None = None
    notes: str = Field(default="", max_length=1200)
    allowedFiles: str = Field(default="PDF / Word / Excel", max_length=100)


class RequestStatusPayload(BaseModel):
    status: Literal["waiting_upload", "received", "review", "approved", "needs_revision", "late", "cancelled"]


class TeacherPayload(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    subject: str = Field(min_length=2, max_length=80)
    specialization: str = Field(default="", max_length=120)
    qualification: str = Field(default="", max_length=160)
    experienceYears: int = Field(default=0, ge=0, le=60)
    workload: int = Field(default=0, ge=0, le=40)
    email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)


class TeacherProfilePayload(TeacherPayload):
    employeeNumber: str = Field(default="", max_length=80)
    schoolJoinYear: int | None = Field(default=None, ge=1950, le=2100)
    grades: str = Field(default="", max_length=220)
    responsibilities: str = Field(default="", max_length=2000)
    professionalSummary: str = Field(default="", max_length=2500)


class TeacherCvItemPayload(BaseModel):
    itemType: Literal["qualification", "course", "achievement", "experience"]
    title: str = Field(min_length=2, max_length=220)
    organization: str = Field(default="", max_length=220)
    startYear: int | None = Field(default=None, ge=1950, le=2100)
    endYear: int | None = Field(default=None, ge=1950, le=2100)
    description: str = Field(default="", max_length=2000)


class EventPayload(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    eventType: str = Field(min_length=2, max_length=80)
    eventDate: str
    location: str = Field(default="", max_length=160)
    audience: str = Field(default="", max_length=180)
    participantCount: int = Field(default=0, ge=0, le=100000)
    goals: str = Field(default="", max_length=2000)
    summary: str = Field(default="", max_length=4000)
    outcomes: str = Field(default="", max_length=3000)
    recommendations: str = Field(default="", max_length=3000)
    teacherIds: list[int] = Field(default_factory=list, max_length=100)


class EventMediaMetaPayload(BaseModel):
    caption: str = Field(default="", max_length=500)
    position: int = Field(default=0, ge=0, le=10000)
    isCover: bool = False


class EventMediaOrderPayload(BaseModel):
    mediaIds: list[int] = Field(min_length=1, max_length=500)


def _teacher_dict(row):
    item = dict(row)
    item["experienceYears"] = item.pop("experience_years")
    item["cvCompletion"] = item.pop("cv_completion")
    return item


def _cv_item_dict(row):
    item = dict(row)
    for source, target in [
        ("teacher_id", "teacherId"),
        ("item_type", "itemType"),
        ("start_year", "startYear"),
        ("end_year", "endYear"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        item[target] = item.pop(source)
    return item


def _profile_dict(row):
    if row is None:
        return {
            "employeeNumber": "",
            "schoolJoinYear": None,
            "grades": "",
            "responsibilities": "",
            "professionalSummary": "",
        }
    item = dict(row)
    item.pop("teacher_id", None)
    item.pop("updated_at", None)
    return {
        "employeeNumber": item.get("employee_number") or "",
        "schoolJoinYear": item.get("school_join_year"),
        "grades": item.get("grades") or "",
        "responsibilities": item.get("responsibilities") or "",
        "professionalSummary": item.get("professional_summary") or "",
    }


def _teacher_profile_details(conn, teacher_id: int):
    teacher_row = conn.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
    if not teacher_row:
        raise HTTPException(status_code=404, detail="المعلم غير موجود.")
    profile_row = conn.execute("SELECT * FROM teacher_profiles WHERE teacher_id = ?", (teacher_id,)).fetchone()
    cv_items = [
        _cv_item_dict(row)
        for row in conn.execute(
            "SELECT * FROM teacher_cv_items WHERE teacher_id = ? ORDER BY COALESCE(end_year, start_year, 0) DESC, id DESC",
            (teacher_id,),
        ).fetchall()
    ]
    request_count = conn.execute("SELECT COUNT(*) FROM upload_requests WHERE teacher_id = ?", (teacher_id,)).fetchone()[0]
    document_count = conn.execute("SELECT COUNT(*) FROM documents WHERE teacher_id = ?", (teacher_id,)).fetchone()[0]
    approved_document_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE teacher_id = ? AND status = 'approved'",
        (teacher_id,),
    ).fetchone()[0]
    return {
        "teacher": _teacher_dict(teacher_row),
        "profile": _profile_dict(profile_row),
        "cvItems": cv_items,
        "stats": {
            "requestCount": request_count,
            "documentCount": document_count,
            "approvedDocumentCount": approved_document_count,
        },
    }


def _raise_cv_completion_floor(conn, teacher_id: int) -> None:
    teacher = conn.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
    if not teacher:
        return
    profile = conn.execute("SELECT * FROM teacher_profiles WHERE teacher_id = ?", (teacher_id,)).fetchone()
    item_count = conn.execute("SELECT COUNT(*) FROM teacher_cv_items WHERE teacher_id = ?", (teacher_id,)).fetchone()[0]
    score = 20
    score += 10 if (teacher["specialization"] or "").strip() else 0
    score += 15 if (teacher["qualification"] or "").strip() else 0
    score += 10 if (teacher["email"] or "").strip() else 0
    score += 5 if (teacher["phone"] or "").strip() else 0
    if profile:
        score += 10 if (profile["professional_summary"] or "").strip() else 0
        score += 10 if (profile["responsibilities"] or "").strip() else 0
        score += 5 if (profile["grades"] or "").strip() else 0
        score += 5 if (profile["employee_number"] or "").strip() else 0
    score += 10 if item_count else 0
    score = min(100, score)
    if score > teacher["cv_completion"]:
        conn.execute("UPDATE teachers SET cv_completion = ?, updated_at = ? WHERE id = ?", (score, utc_now(), teacher_id))


def _request_dict(row, include_token: bool = False):
    item = dict(row)
    item["teacherId"] = item.pop("teacher_id")
    item["teacherName"] = item.pop("teacher_name")
    item["requestType"] = item.pop("request_type")
    item["allowedFiles"] = item.pop("allowed_files")
    item["expiresAt"] = item.pop("expires_at")
    item["createdAt"] = item.pop("created_at")
    item["updatedAt"] = item.pop("updated_at")
    if not include_token:
        item.pop("token_hash", None)
    return item


def _document_dict(row):
    item = dict(row)
    for source, target in [
        ("request_id", "requestId"),
        ("teacher_id", "teacherId"),
        ("academic_year", "academicYear"),
        ("original_name", "originalName"),
        ("mime_type", "mimeType"),
        ("size_bytes", "sizeBytes"),
        ("storage_provider", "storageProvider"),
        ("storage_file_id", "storageFileId"),
        ("storage_path", "storagePath"),
        ("web_view_link", "webViewLink"),
        ("uploaded_at", "uploadedAt"),
        ("approved_at", "approvedAt"),
    ]:
        item[target] = item.pop(source)
    return item


def _event_dict(row):
    item = dict(row)
    for source, target in [
        ("event_type", "eventType"),
        ("event_date", "eventDate"),
        ("participant_count", "participantCount"),
        ("cover_tone", "coverTone"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
        ("media_count", "mediaCount"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    return item


def _event_media_dict(row):
    item = dict(row)
    for source, target in [
        ("event_id", "eventId"),
        ("original_name", "originalName"),
        ("mime_type", "mimeType"),
        ("size_bytes", "sizeBytes"),
        ("storage_provider", "storageProvider"),
        ("storage_file_id", "storageFileId"),
        ("storage_path", "storagePath"),
        ("web_view_link", "webViewLink"),
        ("created_at", "createdAt"),
        ("is_cover", "isCover"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    item["isCover"] = bool(item.get("isCover", False))
    item["contentUrl"] = f"/api/events/{item['eventId']}/media/{item['id']}/content"
    return item


def _event_detail(event_id: int):
    with connect() as conn:
        row = conn.execute(
            """SELECT e.*, COUNT(m.id) AS media_count
               FROM events e LEFT JOIN event_media m ON m.event_id = e.id
               WHERE e.id = ? GROUP BY e.id""",
            (event_id,),
        ).fetchone()
        if not row:
            return None
        media_rows = conn.execute(
            """SELECT m.*, COALESCE(meta.caption, '') AS caption, COALESCE(meta.position, 0) AS position,
                      COALESCE(meta.is_cover, 0) AS is_cover
               FROM event_media m
               LEFT JOIN event_media_meta meta ON meta.media_id = m.id
               WHERE m.event_id = ?
               ORDER BY COALESCE(meta.position, 0), m.id""",
            (event_id,),
        ).fetchall()
        teacher_rows = conn.execute(
            """SELECT t.*, l.role AS event_role
               FROM event_teacher_links l JOIN teachers t ON t.id = l.teacher_id
               WHERE l.event_id = ? ORDER BY t.name""",
            (event_id,),
        ).fetchall()
    event = _event_dict(row)
    media = [_event_media_dict(item) for item in media_rows]
    event["media"] = media
    event["teachers"] = [_teacher_dict(teacher_row) for teacher_row in teacher_rows]
    cover = next((item for item in media if item["isCover"]), None)
    event["coverMediaId"] = cover["id"] if cover else None
    event["coverMediaUrl"] = cover["contentUrl"] if cover else None
    return event


def _get_request_rows():
    with connect() as conn:
        return conn.execute(
            """
            SELECT r.*, t.name AS teacher_name
            FROM upload_requests r JOIN teachers t ON t.id = r.teacher_id
            ORDER BY r.created_at DESC, r.id DESC
            """
        ).fetchall()


def _status_counts(requests: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in requests:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


def _request_from_token(token: str):
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connect() as conn:
        return conn.execute(
            """
            SELECT r.*, t.name AS teacher_name
            FROM upload_requests r JOIN teachers t ON t.id = r.teacher_id
            WHERE r.token_hash = ?
            """,
            (digest,),
        ).fetchone()


def _safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^\w.()\-\u0600-\u06FF ]+", "_", name, flags=re.UNICODE)
    return name[:180] or "file"


def _resolve_event_local_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    resolved = path.resolve()
    root = EVENT_UPLOADS_DIR.resolve()
    if resolved != root and root not in resolved.parents:
        raise HTTPException(status_code=400, detail="مسار ملف الفعالية غير صالح.")
    return resolved


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.4.0", "storageMode": os.getenv("STORAGE_MODE", "auto")}


@app.get("/api/bootstrap")
def bootstrap():
    with connect() as conn:
        teachers = [_teacher_dict(r) for r in conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()]
        request_items = [_request_dict(r) for r in _get_request_rows()]
        events = [_event_dict(r) for r in conn.execute("""SELECT e.*, COUNT(m.id) AS media_count FROM events e LEFT JOIN event_media m ON m.event_id = e.id GROUP BY e.id ORDER BY e.event_date DESC""").fetchall()]
        cover_rows = conn.execute(
            """SELECT m.event_id, m.id AS media_id
               FROM event_media m JOIN event_media_meta meta ON meta.media_id = m.id
               WHERE meta.is_cover = 1"""
        ).fetchall()
        cover_by_event = {row["event_id"]: row["media_id"] for row in cover_rows}
        for event in events:
            cover_id = cover_by_event.get(event["id"])
            event["coverMediaId"] = cover_id
            event["coverMediaUrl"] = f"/api/events/{event['id']}/media/{cover_id}/content" if cover_id else None
        documents = [_document_dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC LIMIT 30").fetchall()]
        activities = [dict(r) for r in conn.execute("SELECT * FROM activities ORDER BY created_at DESC LIMIT 8").fetchall()]

    counts = _status_counts(request_items)
    dashboard = {
        "teacherCount": len(teachers),
        "openRequests": sum(counts.get(k, 0) for k in ["waiting_upload", "received", "review", "needs_revision", "late"]),
        "needsReview": counts.get("review", 0) + counts.get("received", 0),
        "lateRequests": counts.get("late", 0),
        "openDecisions": 4,
        "upcomingVisits": 2,
        "planProgress": 82,
        "visitProgress": 70,
        "requestCompletion": 91,
    }
    return {
        "academicYear": ACADEMIC_YEAR,
        "term": "الفصل الأول",
        "dashboard": dashboard,
        "teachers": teachers,
        "requests": request_items,
        "events": events,
        "documents": documents,
        "activities": activities,
        "drive": drive.status(),
    }


@app.post("/api/teachers", status_code=201)
def create_teacher(payload: TeacherPayload):
    now = utc_now()
    cv_fields = [payload.specialization, payload.qualification, payload.email]
    cv_completion = min(100, 40 + sum(20 for value in cv_fields if value.strip()))
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO teachers
            (name, subject, specialization, qualification, experience_years, workload, cv_completion, email, phone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.name, payload.subject, payload.specialization, payload.qualification, payload.experienceYears, payload.workload, cv_completion, payload.email, payload.phone, now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("teacher", f"إضافة {payload.name}", payload.subject, "teacher", cursor.lastrowid, now),
        )
    return {"id": cursor.lastrowid}


@app.get("/api/teachers/{teacher_id}/profile")
def get_teacher_profile(teacher_id: int):
    with connect() as conn:
        return _teacher_profile_details(conn, teacher_id)


@app.patch("/api/teachers/{teacher_id}/profile")
def update_teacher_profile(teacher_id: int, payload: TeacherProfilePayload):
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT id FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="المعلم غير موجود.")
        conn.execute(
            """UPDATE teachers
               SET name = ?, subject = ?, specialization = ?, qualification = ?, experience_years = ?, workload = ?, email = ?, phone = ?, updated_at = ?
               WHERE id = ?""",
            (
                payload.name, payload.subject, payload.specialization, payload.qualification,
                payload.experienceYears, payload.workload, payload.email, payload.phone, now, teacher_id,
            ),
        )
        conn.execute(
            """INSERT INTO teacher_profiles
               (teacher_id, employee_number, school_join_year, grades, responsibilities, professional_summary, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(teacher_id) DO UPDATE SET
                 employee_number = excluded.employee_number,
                 school_join_year = excluded.school_join_year,
                 grades = excluded.grades,
                 responsibilities = excluded.responsibilities,
                 professional_summary = excluded.professional_summary,
                 updated_at = excluded.updated_at""",
            (
                teacher_id, payload.employeeNumber, payload.schoolJoinYear, payload.grades,
                payload.responsibilities, payload.professionalSummary, now,
            ),
        )
        _raise_cv_completion_floor(conn, teacher_id)
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("teacher", f"تحديث الملف المهني: {payload.name}", payload.subject, "teacher", teacher_id, now),
        )
        return _teacher_profile_details(conn, teacher_id)


@app.post("/api/teachers/{teacher_id}/cv-items", status_code=201)
def create_teacher_cv_item(teacher_id: int, payload: TeacherCvItemPayload):
    if payload.startYear and payload.endYear and payload.endYear < payload.startYear:
        raise HTTPException(status_code=422, detail="سنة النهاية لا يمكن أن تسبق سنة البداية.")
    now = utc_now()
    with connect() as conn:
        teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود.")
        cursor = conn.execute(
            """INSERT INTO teacher_cv_items
               (teacher_id, item_type, title, organization, start_year, end_year, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (teacher_id, payload.itemType, payload.title, payload.organization, payload.startYear, payload.endYear, payload.description, now, now),
        )
        _raise_cv_completion_floor(conn, teacher_id)
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("teacher", f"إضافة بند إلى سيرة {teacher['name']}", payload.title, "teacher_cv_item", cursor.lastrowid, now),
        )
    return {"id": cursor.lastrowid}


@app.delete("/api/teachers/{teacher_id}/cv-items/{item_id}")
def delete_teacher_cv_item(teacher_id: int, item_id: int):
    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT id, title FROM teacher_cv_items WHERE id = ? AND teacher_id = ?",
            (item_id, teacher_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="بند السيرة غير موجود.")
        conn.execute("DELETE FROM teacher_cv_items WHERE id = ?", (item_id,))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("teacher", "حذف بند من السيرة المهنية", row["title"], "teacher", teacher_id, now),
        )
    return {"ok": True}


@app.post("/api/events", status_code=201)
def create_event(payload: EventPayload):
    try:
        datetime.fromisoformat(payload.eventDate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="تاريخ الفعالية غير صالح.") from exc
    teacher_ids = list(dict.fromkeys(payload.teacherIds))
    now = utc_now()
    tones = ["teal", "navy", "gold"]
    with connect() as conn:
        if teacher_ids:
            found = conn.execute(
                f"SELECT id FROM teachers WHERE id IN ({','.join('?' for _ in teacher_ids)})",
                teacher_ids,
            ).fetchall()
            if len(found) != len(teacher_ids):
                raise HTTPException(status_code=422, detail="تتضمن قائمة المشاركين معلمًا غير موجود.")
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO events
            (title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.title, payload.eventType, payload.eventDate, payload.location, payload.audience, payload.participantCount, payload.goals, payload.summary, payload.outcomes, payload.recommendations, tones[count % len(tones)], now, now),
        )
        event_id = cursor.lastrowid
        if teacher_ids:
            conn.executemany(
                "INSERT INTO event_teacher_links (event_id, teacher_id, role, created_at) VALUES (?, ?, 'مشارك', ?)",
                [(event_id, teacher_id, now) for teacher_id in teacher_ids],
            )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("event", f"توثيق {payload.title}", payload.eventType, "event", event_id, now),
        )
    return {"id": event_id}


@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    detail = _event_detail(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الفعالية غير موجودة.")
    return detail


@app.patch("/api/events/{event_id}")
def update_event(event_id: int, payload: EventPayload):
    try:
        datetime.fromisoformat(payload.eventDate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="تاريخ الفعالية غير صالح.") from exc
    teacher_ids = list(dict.fromkeys(payload.teacherIds))
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="الفعالية غير موجودة.")
        if teacher_ids:
            found = conn.execute(
                f"SELECT id FROM teachers WHERE id IN ({','.join('?' for _ in teacher_ids)})",
                teacher_ids,
            ).fetchall()
            if len(found) != len(teacher_ids):
                raise HTTPException(status_code=422, detail="تتضمن قائمة المشاركين معلمًا غير موجود.")
        conn.execute(
            """UPDATE events SET title = ?, event_type = ?, event_date = ?, location = ?, audience = ?,
               participant_count = ?, goals = ?, summary = ?, outcomes = ?, recommendations = ?, updated_at = ?
               WHERE id = ?""",
            (payload.title, payload.eventType, payload.eventDate, payload.location, payload.audience,
             payload.participantCount, payload.goals, payload.summary, payload.outcomes, payload.recommendations,
             now, event_id),
        )
        conn.execute("DELETE FROM event_teacher_links WHERE event_id = ?", (event_id,))
        if teacher_ids:
            conn.executemany(
                "INSERT INTO event_teacher_links (event_id, teacher_id, role, created_at) VALUES (?, ?, 'مشارك', ?)",
                [(event_id, teacher_id, now) for teacher_id in teacher_ids],
            )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("event", f"تحديث توثيق {payload.title}", f"{len(teacher_ids)} معلمًا مشاركًا", "event", event_id, now),
        )
    return _event_detail(event_id)


@app.post("/api/events/{event_id}/media", status_code=201)
async def upload_event_media(event_id: int, file: UploadFile = File(...), caption: str = Form(default="")):
    detail = _event_detail(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الفعالية غير موجودة.")
    if len(caption) > 500:
        raise HTTPException(status_code=422, detail="وصف الدليل طويل جدًا.")

    safe_name = _safe_filename(file.filename or "file")
    suffix = Path(safe_name).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="نوع ملف التوثيق غير مسموح به.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp_path = Path(temp.name)
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"الحد الأقصى للملف {MAX_UPLOAD_MB} MB.")
            temp.write(chunk)

    mime_type = mimetypes.guess_type(safe_name)[0] or file.content_type or "application/octet-stream"
    storage_mode = os.getenv("STORAGE_MODE", "auto")
    storage_provider = "local"
    storage_file_id = None
    storage_path = None
    web_view_link = None

    try:
        use_drive = storage_mode == "google_drive" or (storage_mode == "auto" and drive.is_connected())
        if use_drive:
            if not drive.is_connected():
                raise HTTPException(status_code=503, detail="Google Drive غير مربوط بعد.")
            try:
                result = drive.upload_event_file(temp_path, safe_name, mime_type, ACADEMIC_YEAR, event_id, detail["title"])
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"فشل رفع دليل الفعالية إلى Google Drive: {exc}") from exc
            storage_provider = "google_drive"
            storage_file_id = result.get("id")
            web_view_link = result.get("webViewLink")
        else:
            event_dir = EVENT_UPLOADS_DIR / str(event_id)
            event_dir.mkdir(parents=True, exist_ok=True)
            target = event_dir / f"{secrets.token_hex(4)}-{safe_name}"
            shutil.move(str(temp_path), target)
            try:
                storage_path = str(target.relative_to(BASE_DIR))
            except ValueError:
                storage_path = str(target)
    finally:
        temp_path.unlink(missing_ok=True)

    now = utc_now()
    with connect() as conn:
        max_position = conn.execute(
            """SELECT COALESCE(MAX(meta.position), -1) FROM event_media m
               LEFT JOIN event_media_meta meta ON meta.media_id = m.id WHERE m.event_id = ?""",
            (event_id,),
        ).fetchone()[0]
        has_cover = conn.execute(
            """SELECT 1 FROM event_media m JOIN event_media_meta meta ON meta.media_id = m.id
               WHERE m.event_id = ? AND meta.is_cover = 1 LIMIT 1""",
            (event_id,),
        ).fetchone()
        cursor = conn.execute(
            """INSERT INTO event_media
               (event_id, original_name, mime_type, size_bytes, storage_provider, storage_file_id, storage_path, web_view_link, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, safe_name, mime_type, total, storage_provider, storage_file_id, storage_path, web_view_link, now),
        )
        media_id = cursor.lastrowid
        is_cover = 1 if mime_type.startswith("image/") and not has_cover else 0
        conn.execute(
            "INSERT INTO event_media_meta (media_id, caption, position, is_cover, updated_at) VALUES (?, ?, ?, ?, ?)",
            (media_id, caption.strip(), max_position + 1, is_cover, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("event", f"إضافة دليل إلى {detail['title']}", safe_name, "event", event_id, now),
        )
    return _event_media_dict({
        "id": media_id, "event_id": event_id, "original_name": safe_name, "mime_type": mime_type,
        "size_bytes": total, "storage_provider": storage_provider, "storage_file_id": storage_file_id,
        "storage_path": storage_path, "web_view_link": web_view_link, "created_at": now,
        "caption": caption.strip(), "position": max_position + 1, "is_cover": is_cover,
    })


@app.patch("/api/events/{event_id}/media-order")
def reorder_event_media(event_id: int, payload: EventMediaOrderPayload):
    now = utc_now()
    ordered_ids = payload.mediaIds
    if len(set(ordered_ids)) != len(ordered_ids):
        raise HTTPException(status_code=422, detail="ترتيب الأدلة يحتوي عناصر مكررة.")
    with connect() as conn:
        event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="الفعالية غير موجودة.")
        existing = [row["id"] for row in conn.execute("SELECT id FROM event_media WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()]
        if set(existing) != set(ordered_ids) or len(existing) != len(ordered_ids):
            raise HTTPException(status_code=422, detail="قائمة ترتيب الأدلة لا تطابق أدلة الفعالية الحالية.")
        for position, media_id in enumerate(ordered_ids):
            conn.execute(
                "INSERT OR IGNORE INTO event_media_meta (media_id, caption, position, is_cover, updated_at) VALUES (?, '', ?, 0, ?)",
                (media_id, position, now),
            )
            conn.execute("UPDATE event_media_meta SET position = ?, updated_at = ? WHERE media_id = ?", (position, now, media_id))
    return _event_detail(event_id)


@app.patch("/api/events/{event_id}/media/{media_id}")
def update_event_media(event_id: int, media_id: int, payload: EventMediaMetaPayload):
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT id, mime_type FROM event_media WHERE id = ? AND event_id = ?", (media_id, event_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="دليل الفعالية غير موجود.")
        if payload.isCover and not (row["mime_type"] or "").startswith("image/"):
            raise HTTPException(status_code=422, detail="يمكن استخدام الصور فقط كغلاف للفعالية.")
        conn.execute(
            "INSERT OR IGNORE INTO event_media_meta (media_id, caption, position, is_cover, updated_at) VALUES (?, '', 0, 0, ?)",
            (media_id, now),
        )
        if payload.isCover:
            conn.execute(
                "UPDATE event_media_meta SET is_cover = 0, updated_at = ? WHERE media_id IN (SELECT id FROM event_media WHERE event_id = ?)",
                (now, event_id),
            )
        conn.execute(
            "UPDATE event_media_meta SET caption = ?, position = ?, is_cover = ?, updated_at = ? WHERE media_id = ?",
            (payload.caption.strip(), payload.position, int(payload.isCover), now, media_id),
        )
    return _event_detail(event_id)


@app.delete("/api/events/{event_id}/media/{media_id}")
def delete_event_media(event_id: int, media_id: int):
    detail = _event_detail(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الفعالية غير موجودة.")
    with connect() as conn:
        row = conn.execute(
            """SELECT m.*, COALESCE(meta.is_cover, 0) AS is_cover
               FROM event_media m LEFT JOIN event_media_meta meta ON meta.media_id = m.id
               WHERE m.id = ? AND m.event_id = ?""",
            (media_id, event_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="دليل الفعالية غير موجود.")

    if row["storage_provider"] == "google_drive" and row["storage_file_id"]:
        try:
            drive.delete_file(row["storage_file_id"])
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"تعذر حذف الملف من Google Drive: {exc}") from exc
    elif row["storage_provider"] == "local" and row["storage_path"]:
        path = _resolve_event_local_path(row["storage_path"])
        path.unlink(missing_ok=True)

    now = utc_now()
    with connect() as conn:
        was_cover = bool(row["is_cover"])
        conn.execute("DELETE FROM event_media WHERE id = ? AND event_id = ?", (media_id, event_id))
        if was_cover:
            fallback = conn.execute(
                """SELECT m.id FROM event_media m
                   LEFT JOIN event_media_meta meta ON meta.media_id = m.id
                   WHERE m.event_id = ? AND m.mime_type LIKE 'image/%'
                   ORDER BY COALESCE(meta.position, 0), m.id LIMIT 1""",
                (event_id,),
            ).fetchone()
            if fallback:
                conn.execute(
                    "INSERT OR IGNORE INTO event_media_meta (media_id, caption, position, is_cover, updated_at) VALUES (?, '', 0, 0, ?)",
                    (fallback["id"], now),
                )
                conn.execute("UPDATE event_media_meta SET is_cover = 1, updated_at = ? WHERE media_id = ?", (now, fallback["id"]))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("event", f"حذف دليل من {detail['title']}", row["original_name"], "event", event_id, now),
        )
    return {"ok": True}


@app.get("/api/events/{event_id}/media/{media_id}/content")
def event_media_content(event_id: int, media_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM event_media WHERE id = ? AND event_id = ?", (media_id, event_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="دليل الفعالية غير موجود.")
    if row["storage_provider"] == "local" and row["storage_path"]:
        path = _resolve_event_local_path(row["storage_path"])
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="ملف التوثيق غير موجود على الخادم.")
        return FileResponse(path, media_type=row["mime_type"] or None)
    if row["storage_provider"] == "google_drive" and row["storage_file_id"]:
        try:
            content, mime_type = drive.download_file(row["storage_file_id"])
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"تعذر قراءة الملف من Google Drive: {exc}") from exc
        return Response(content=content, media_type=mime_type)
    if row["web_view_link"]:
        return RedirectResponse(row["web_view_link"], status_code=302)
    raise HTTPException(status_code=404, detail="لا يوجد مصدر متاح لهذا الدليل.")


@app.post("/api/requests", status_code=201)
def create_request(payload: CreateRequestPayload):
    with connect() as conn:
        teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود.")

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = utc_now()
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        if payload.deadline:
            try:
                deadline_dt = datetime.fromisoformat(payload.deadline).replace(tzinfo=timezone.utc) + timedelta(days=2)
                if deadline_dt > datetime.now(timezone.utc):
                    expiry = max(expiry, deadline_dt)
            except ValueError:
                raise HTTPException(status_code=422, detail="تاريخ التسليم غير صالح.")

        cursor = conn.execute(
            """
            INSERT INTO upload_requests
            (teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, token_hash, status, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting_upload', ?, ?, ?)
            """,
            (
                payload.teacherId,
                payload.requestType,
                payload.subject,
                payload.grade,
                payload.title,
                payload.deadline,
                payload.notes,
                payload.allowedFiles,
                token_hash,
                expiry.replace(microsecond=0).isoformat(),
                now,
                now,
            ),
        )
        request_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("request", f"طلب ملف من {teacher['name']}", payload.title, "request", request_id, now),
        )

    return {
        "id": request_id,
        "uploadUrl": f"{APP_PUBLIC_URL}/upload/{token}",
        "expiresAt": expiry.replace(microsecond=0).isoformat(),
    }


@app.patch("/api/requests/{request_id}/status")
def update_request_status(request_id: int, payload: RequestStatusPayload):
    now = utc_now()
    with connect() as conn:
        request_row = conn.execute("SELECT id, title FROM upload_requests WHERE id = ?", (request_id,)).fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="الطلب غير موجود.")
        conn.execute("UPDATE upload_requests SET status = ?, updated_at = ? WHERE id = ?", (payload.status, now, request_id))
        if payload.status == "approved":
            conn.execute("UPDATE documents SET status = 'approved', approved_at = ? WHERE request_id = ?", (now, request_id))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("request", "تحديث حالة طلب", f"{request_row['title']} ← {payload.status}", "request", request_id, now),
        )
    return {"ok": True}


@app.get("/api/public/upload/{token}")
def public_upload_request(token: str):
    row = _request_from_token(token)
    if not row:
        raise HTTPException(status_code=404, detail="رابط الرفع غير صالح.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="انتهت صلاحية رابط الرفع.")
    if row["status"] in {"approved", "cancelled"}:
        raise HTTPException(status_code=409, detail="هذا الطلب مغلق ولا يستقبل ملفات جديدة.")
    item = _request_dict(row)
    return {
        "id": item["id"],
        "teacherName": item["teacherName"],
        "title": item["title"],
        "requestType": item["requestType"],
        "subject": item["subject"],
        "grade": item["grade"],
        "deadline": item["deadline"],
        "notes": item["notes"],
        "allowedFiles": item["allowedFiles"],
        "maxUploadMb": MAX_UPLOAD_MB,
    }


@app.post("/api/public/upload/{token}", status_code=201)
async def public_upload_file(token: str, file: UploadFile = File(...)):
    row = _request_from_token(token)
    if not row:
        raise HTTPException(status_code=404, detail="رابط الرفع غير صالح.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="انتهت صلاحية رابط الرفع.")
    if row["status"] in {"approved", "cancelled"}:
        raise HTTPException(status_code=409, detail="هذا الطلب مغلق.")

    safe_name = _safe_filename(file.filename or "file")
    suffix = Path(safe_name).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png"}
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="نوع الملف غير مسموح به.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp_path = Path(temp.name)
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"الحد الأقصى للملف {MAX_UPLOAD_MB} MB.")
            temp.write(chunk)

    mime_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    storage_mode = os.getenv("STORAGE_MODE", "auto")
    storage_provider = "local"
    storage_file_id = None
    storage_path = None
    web_view_link = None

    try:
        use_drive = storage_mode == "google_drive" or (storage_mode == "auto" and drive.is_connected())
        if use_drive:
            if not drive.is_connected():
                raise HTTPException(status_code=503, detail="Google Drive غير مربوط بعد.")
            result = drive.upload_file(temp_path, safe_name, mime_type, ACADEMIC_YEAR, row["id"])
            storage_provider = "google_drive"
            storage_file_id = result.get("id")
            web_view_link = result.get("webViewLink")
        else:
            request_dir = UPLOADS_DIR / str(row["id"])
            request_dir.mkdir(parents=True, exist_ok=True)
            target = request_dir / f"{secrets.token_hex(4)}-{safe_name}"
            shutil.move(str(temp_path), target)
            try:
                storage_path = str(target.relative_to(BASE_DIR))
            except ValueError:
                storage_path = str(target)
    finally:
        temp_path.unlink(missing_ok=True)

    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents
            (request_id, teacher_id, title, category, subject, grade, academic_year, original_name, mime_type, size_bytes,
             storage_provider, storage_file_id, storage_path, web_view_link, status, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbox', ?)
            """,
            (
                row["id"], row["teacher_id"], row["title"], row["request_type"], row["subject"], row["grade"],
                ACADEMIC_YEAR, safe_name, mime_type, total, storage_provider, storage_file_id, storage_path, web_view_link, now,
            ),
        )
        conn.execute("UPDATE upload_requests SET status = 'review', updated_at = ? WHERE id = ?", (now, row["id"]))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("document", f"استلام {safe_name}", f"من {row['teacher_name']} للمراجعة", "document", cursor.lastrowid, now),
        )

    return {"ok": True, "documentId": cursor.lastrowid, "storageProvider": storage_provider}


@app.get("/api/integrations/google-drive/status")
def google_drive_status():
    return drive.status()


@app.get("/api/integrations/google-drive/auth-url")
def google_drive_auth_url():
    try:
        return {"url": drive.build_auth_url()}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/integrations/google-drive/oauth/callback")
def google_drive_callback(code: str, state: str):
    if not drive.verify_oauth_state(state):
        raise HTTPException(status_code=400, detail="حالة OAuth غير صالحة.")
    try:
        drive.exchange_code(code)
        drive.ensure_root_folder()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"فشل ربط Google Drive: {exc}") from exc
    return RedirectResponse(url=f"{APP_FRONTEND_URL}/?drive=connected", status_code=302)


@app.post("/api/integrations/google-drive/disconnect")
def google_drive_disconnect():
    from .db import set_setting
    set_setting("google_refresh_token", "")
    set_setting("google_drive_root_folder_id", "")
    return {"ok": True}


DIST_DIR = BASE_DIR / "dist"
if DIST_DIR.exists():
    assets = DIST_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = DIST_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/", response_class=HTMLResponse)
    def no_build():
        return "<h1>واجهة React لم تُبنَ بعد.</h1><p>شغّل npm install ثم npm run build.</p>"
