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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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

app = FastAPI(title="مرصد الإنجازات API", version="0.2.0")


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


def _teacher_dict(row):
    item = dict(row)
    item["experienceYears"] = item.pop("experience_years")
    item["cvCompletion"] = item.pop("cv_completion")
    return item


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
        item[target] = item.pop(source)
    return item


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


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.2.0", "storageMode": os.getenv("STORAGE_MODE", "auto")}


@app.get("/api/bootstrap")
def bootstrap():
    with connect() as conn:
        teachers = [_teacher_dict(r) for r in conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()]
        request_items = [_request_dict(r) for r in _get_request_rows()]
        events = [_event_dict(r) for r in conn.execute("""SELECT e.*, COUNT(m.id) AS media_count FROM events e LEFT JOIN event_media m ON m.event_id = e.id GROUP BY e.id ORDER BY e.event_date DESC""").fetchall()]
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


@app.post("/api/events", status_code=201)
def create_event(payload: EventPayload):
    try:
        datetime.fromisoformat(payload.eventDate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="تاريخ الفعالية غير صالح.") from exc
    now = utc_now()
    tones = ["teal", "navy", "gold"]
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO events
            (title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.title, payload.eventType, payload.eventDate, payload.location, payload.audience, payload.participantCount, payload.goals, payload.summary, payload.outcomes, payload.recommendations, tones[count % len(tones)], now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("event", f"توثيق {payload.title}", payload.eventType, "event", cursor.lastrowid, now),
        )
    return {"id": cursor.lastrowid}


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
