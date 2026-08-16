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
from .achievement_metrics import evaluate_impact
from .search import run_search

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

app = FastAPI(title="مرصد الإنجازات API", version="0.13.1")


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
    academicYear: str = Field(default=ACADEMIC_YEAR, min_length=4, max_length=20)
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
    academicYear: str | None = Field(default=None, max_length=20)
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


class MeetingPayload(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    meetingType: str = Field(default="اجتماع قسم", min_length=2, max_length=80)
    meetingDate: str
    academicYear: str = Field(default=ACADEMIC_YEAR, min_length=4, max_length=20)
    meetingTime: str = Field(default="", max_length=5)
    location: str = Field(default="", max_length=160)
    agenda: str = Field(default="", max_length=5000)
    discussionSummary: str = Field(default="", max_length=7000)
    notes: str = Field(default="", max_length=3000)
    status: Literal["planned", "held", "cancelled"] = "planned"
    attendeeIds: list[int] = Field(default_factory=list, max_length=100)


class MeetingDecisionPayload(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    responsibleTeacherId: int | None = None
    responsibleName: str = Field(default="", max_length=160)
    dueDate: str | None = None
    status: Literal["new", "in_progress", "completed", "cancelled"] = "new"
    notes: str = Field(default="", max_length=2000)


class CurriculumPlanPayload(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    subject: str = Field(min_length=2, max_length=80)
    grade: str = Field(min_length=1, max_length=40)
    term: str = Field(min_length=2, max_length=80)
    academicYear: str = Field(default=ACADEMIC_YEAR, min_length=4, max_length=20)
    ownerTeacherId: int | None = None
    startDate: str | None = None
    endDate: str | None = None
    notes: str = Field(default="", max_length=3000)
    status: Literal["active", "completed", "archived"] = "active"


class CurriculumUnitPayload(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    sequence: int = Field(default=0, ge=0, le=1000)
    plannedStart: str | None = None
    plannedEnd: str | None = None
    progressPercent: int = Field(default=0, ge=0, le=100)
    status: Literal["not_started", "in_progress", "completed"] = "not_started"
    delayReason: str = Field(default="", max_length=1500)
    notes: str = Field(default="", max_length=2500)
    responsibleTeacherId: int | None = None

class SupervisionVisitPayload(BaseModel):
    teacherId: int
    visitType: str = Field(default="زيارة صفية", min_length=2, max_length=100)
    visitDate: str
    academicYear: str = Field(default=ACADEMIC_YEAR, min_length=4, max_length=20)
    periodLabel: str = Field(default="", max_length=80)
    grade: str = Field(default="", max_length=80)
    lessonTitle: str = Field(default="", max_length=240)
    objectives: str = Field(default="", max_length=4000)
    strengths: str = Field(default="", max_length=5000)
    developmentAreas: str = Field(default="", max_length=5000)
    recommendations: str = Field(default="", max_length=5000)
    followupDate: str | None = None
    followupNotes: str = Field(default="", max_length=4000)
    status: Literal["planned", "completed", "needs_followup", "closed"] = "planned"


class SupervisionActionPayload(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    responsibleTeacherId: int | None = None
    dueDate: str | None = None
    status: Literal["new", "in_progress", "completed", "cancelled"] = "new"
    notes: str = Field(default="", max_length=2500)


class AchievementAssessmentPayload(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    assessmentType: str = Field(default="اختبار", min_length=2, max_length=80)
    subject: str = Field(min_length=2, max_length=80)
    grade: str = Field(min_length=1, max_length=40)
    assessmentDate: str
    term: str = Field(min_length=2, max_length=80)
    academicYear: str = Field(min_length=4, max_length=20)
    teacherId: int | None = None
    maxScore: float = Field(gt=0, le=10000)
    studentCount: int = Field(default=0, ge=0, le=10000)
    averageScore: float | None = Field(default=None, ge=0)
    highestScore: float | None = Field(default=None, ge=0)
    lowestScore: float | None = Field(default=None, ge=0)
    masteryThresholdPct: float = Field(ge=0, le=100)
    masteryReferenceSource: str = Field(min_length=3, max_length=500)
    masteryReferenceYear: str = Field(default="", max_length=100)
    masteryReferenceNote: str = Field(default="", max_length=1200)
    masteredCount: int = Field(default=0, ge=0, le=10000)
    nearMasteryCount: int = Field(default=0, ge=0, le=10000)
    interventionCount: int = Field(default=0, ge=0, le=10000)
    notes: str = Field(default="", max_length=4000)
    status: Literal["draft", "recorded", "reviewed"] = "recorded"


class AchievementActionPayload(BaseModel):
    actionType: Literal["remedial", "enrichment", "followup"] = "remedial"
    title: str = Field(min_length=3, max_length=500)
    targetGroup: str = Field(default="", max_length=500)
    responsibleTeacherId: int | None = None
    startDate: str | None = None
    dueDate: str | None = None
    status: Literal["new", "in_progress", "completed", "cancelled"] = "new"
    baselineIndicator: str = Field(default="", max_length=1000)
    targetIndicator: str = Field(default="", max_length=1000)
    outcomeIndicator: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2500)


class AchievementMetricPayload(BaseModel):
    metricName: str = Field(min_length=2, max_length=300)
    unit: str = Field(default="", max_length=80)
    direction: Literal["higher_better", "lower_better"] = "higher_better"
    baselineValue: float
    targetValue: float
    outcomeValue: float | None = None
    measuredAt: str | None = None
    referenceSource: str = Field(min_length=3, max_length=500)
    referenceYear: str = Field(default="", max_length=100)
    referenceNote: str = Field(default="", max_length=1200)
    notes: str = Field(default="", max_length=2000)


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
    visit_count = conn.execute("SELECT COUNT(*) FROM supervision_visits WHERE teacher_id = ?", (teacher_id,)).fetchone()[0]
    open_followup_count = conn.execute(
        """SELECT COUNT(*) FROM supervision_visits v
           WHERE v.teacher_id = ? AND v.status != 'closed'
             AND (v.status = 'needs_followup'
                  OR EXISTS (
                      SELECT 1 FROM supervision_actions a
                      WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')
                  ))""",
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
            "visitCount": visit_count,
            "openFollowupCount": open_followup_count,
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
    explicit_year = item.pop("academic_year", None)
    item["academicYear"] = explicit_year or _academic_year_from_date(item["createdAt"])
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
        ("academic_year", "academicYear"),
        ("participant_count", "participantCount"),
        ("cover_tone", "coverTone"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
        ("media_count", "mediaCount"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    item["academicYear"] = item.get("academicYear") or _academic_year_from_date(item.get("eventDate"))
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
            """SELECT e.*, ey.academic_year, COUNT(m.id) AS media_count
               FROM events e LEFT JOIN event_media m ON m.event_id = e.id
               LEFT JOIN event_record_years ey ON ey.event_id = e.id
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


def _oman_today_iso() -> str:
    return datetime.now(timezone(timedelta(hours=4))).date().isoformat()


def _validate_iso_date(value: str, label: str) -> str:
    try:
        parsed = datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label} غير صالح.") from exc
    return parsed.isoformat()


def _validate_academic_year(value: str) -> str:
    match = re.fullmatch(r"\s*(\d{4})\s*/\s*(\d{4})\s*", value or "")
    if not match:
        raise HTTPException(status_code=422, detail="صيغة العام الدراسي يجب أن تكون مثل 2025/2026.")
    first, second = int(match.group(1)), int(match.group(2))
    if second != first + 1:
        raise HTTPException(status_code=422, detail="العام الدراسي يجب أن يتكون من عامين متتاليين.")
    return f"{first:04d}/{second:04d}"


def _ensure_teacher_year_links(conn, teacher_ids: list[int] | tuple[int, ...] | set[int], academic_year: str) -> None:
    year = _validate_academic_year(academic_year)
    ids = [int(value) for value in dict.fromkeys(teacher_ids) if value]
    if not ids:
        return
    now = utc_now()
    conn.executemany(
        "INSERT OR IGNORE INTO teacher_record_years (teacher_id, academic_year, created_at, updated_at) VALUES (?, ?, ?, ?)",
        [(teacher_id, year, now, now) for teacher_id in ids],
    )


def _teacher_ids_for_year(conn, academic_year: str) -> set[int]:
    year = _validate_academic_year(academic_year)
    ids = {row["teacher_id"] for row in conn.execute("SELECT teacher_id FROM teacher_record_years WHERE academic_year = ?", (year,)).fetchall()}
    queries = [
        ("SELECT teacher_id FROM documents WHERE academic_year = ? AND teacher_id IS NOT NULL",),
        ("SELECT owner_teacher_id AS teacher_id FROM curriculum_plans WHERE academic_year = ? AND owner_teacher_id IS NOT NULL",),
        ("SELECT u.responsible_teacher_id AS teacher_id FROM curriculum_units u JOIN curriculum_plans p ON p.id=u.plan_id WHERE p.academic_year=? AND u.responsible_teacher_id IS NOT NULL",),
        ("SELECT teacher_id FROM supervision_visits WHERE academic_year = ?",),
        ("SELECT a.responsible_teacher_id AS teacher_id FROM supervision_actions a JOIN supervision_visits v ON v.id=a.visit_id WHERE v.academic_year=? AND a.responsible_teacher_id IS NOT NULL",),
        ("SELECT teacher_id FROM achievement_assessments WHERE academic_year = ? AND teacher_id IS NOT NULL",),
        ("SELECT a.responsible_teacher_id AS teacher_id FROM achievement_actions a JOIN achievement_assessments x ON x.id=a.assessment_id WHERE x.academic_year=? AND a.responsible_teacher_id IS NOT NULL",),
        ("SELECT ma.teacher_id FROM meeting_attendees ma JOIN meetings m ON m.id=ma.meeting_id WHERE m.academic_year=?",),
        ("SELECT d.responsible_teacher_id AS teacher_id FROM meeting_decisions d JOIN meetings m ON m.id=d.meeting_id WHERE m.academic_year=? AND d.responsible_teacher_id IS NOT NULL",),
    ]
    for (query,) in queries:
        ids.update(row["teacher_id"] for row in conn.execute(query, (year,)).fetchall())
    ids.update(row["teacher_id"] for row in conn.execute(
        """SELECT l.teacher_id FROM event_teacher_links l JOIN event_record_years ey ON ey.event_id=l.event_id WHERE ey.academic_year=?""",
        (year,),
    ).fetchall())
    ids.update(row["teacher_id"] for row in conn.execute(
        """SELECT r.teacher_id FROM upload_requests r JOIN request_record_years ry ON ry.request_id=r.id WHERE ry.academic_year=?""",
        (year,),
    ).fetchall())
    return ids


def _teachers_for_year(conn, academic_year: str) -> list[dict]:
    ids = _teacher_ids_for_year(conn, academic_year)
    if not ids:
        return []
    rows = conn.execute(
        f"SELECT * FROM teachers WHERE id IN ({','.join('?' for _ in ids)}) ORDER BY name",
        tuple(sorted(ids)),
    ).fetchall()
    return [_teacher_dict(row) for row in rows]


def _validate_date_in_academic_year(value: str, academic_year: str, label: str) -> str:
    normalized_year = _validate_academic_year(academic_year)
    normalized_date = _validate_iso_date(value, label)
    start_year, end_year = (int(part) for part in normalized_year.split("/"))
    if int(normalized_date[:4]) not in {start_year, end_year}:
        raise HTTPException(
            status_code=422,
            detail=f"{label} لا ينسجم مع العام الدراسي {normalized_year}. تحقق من سنة السجل أو التاريخ.",
        )
    return normalized_date


def _validate_meeting_time(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise HTTPException(status_code=422, detail="وقت الاجتماع غير صالح.")
    return value


def _validate_teacher_ids(conn, teacher_ids: list[int], message: str) -> list[int]:
    unique_ids = list(dict.fromkeys(teacher_ids))
    if not unique_ids:
        return []
    rows = conn.execute(
        f"SELECT id FROM teachers WHERE id IN ({','.join('?' for _ in unique_ids)})",
        unique_ids,
    ).fetchall()
    if len(rows) != len(unique_ids):
        raise HTTPException(status_code=422, detail=message)
    return unique_ids


def _decision_dict(row):
    item = dict(row)
    for source, target in [
        ("meeting_id", "meetingId"),
        ("responsible_teacher_id", "responsibleTeacherId"),
        ("responsible_name", "responsibleName"),
        ("due_date", "dueDate"),
        ("completed_at", "completedAt"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
        ("meeting_title", "meetingTitle"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    base_status = item.get("status", "new")
    item["baseStatus"] = base_status
    due_date = item.get("dueDate")
    if base_status not in {"completed", "cancelled"} and due_date and due_date < _oman_today_iso():
        item["status"] = "overdue"
    return item


def _meeting_dict(row):
    item = dict(row)
    for source, target in [
        ("meeting_type", "meetingType"),
        ("meeting_date", "meetingDate"),
        ("meeting_time", "meetingTime"),
        ("academic_year", "academicYear"),
        ("discussion_summary", "discussionSummary"),
        ("attendee_count", "attendeeCount"),
        ("decision_count", "decisionCount"),
        ("open_decision_count", "openDecisionCount"),
        ("overdue_decision_count", "overdueDecisionCount"),
        ("completed_decision_count", "completedDecisionCount"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    return item


def _meeting_summary_rows(conn, meeting_id: int | None = None):
    where = "WHERE m.id = ?" if meeting_id is not None else ""
    params: tuple = (meeting_id,) if meeting_id is not None else ()
    today = _oman_today_iso()
    return conn.execute(
        f"""SELECT m.*,
               (SELECT COUNT(*) FROM meeting_attendees a WHERE a.meeting_id = m.id) AS attendee_count,
               (SELECT COUNT(*) FROM meeting_decisions d WHERE d.meeting_id = m.id) AS decision_count,
               (SELECT COUNT(*) FROM meeting_decisions d WHERE d.meeting_id = m.id AND d.status NOT IN ('completed','cancelled')) AS open_decision_count,
               (SELECT COUNT(*) FROM meeting_decisions d WHERE d.meeting_id = m.id AND d.status NOT IN ('completed','cancelled') AND d.due_date IS NOT NULL AND d.due_date < ?) AS overdue_decision_count,
               (SELECT COUNT(*) FROM meeting_decisions d WHERE d.meeting_id = m.id AND d.status = 'completed') AS completed_decision_count
           FROM meetings m {where}
           ORDER BY m.meeting_date DESC, m.id DESC""",
        (today, *params),
    ).fetchall()


def _meeting_detail(meeting_id: int):
    with connect() as conn:
        rows = _meeting_summary_rows(conn, meeting_id)
        if not rows:
            return None
        meeting = _meeting_dict(rows[0])
        attendee_rows = conn.execute(
            """SELECT t.*, a.attendance_status
               FROM meeting_attendees a JOIN teachers t ON t.id = a.teacher_id
               WHERE a.meeting_id = ? ORDER BY t.name""",
            (meeting_id,),
        ).fetchall()
        decision_rows = conn.execute(
            """SELECT d.* FROM meeting_decisions d
               WHERE d.meeting_id = ?
               ORDER BY CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END,
                        CASE WHEN d.due_date IS NULL THEN 1 ELSE 0 END,
                        d.due_date, d.id""",
            (meeting_id,),
        ).fetchall()
        timeline_rows = conn.execute(
            """SELECT id, activity_type, title, detail, created_at
               FROM activities WHERE entity_type = 'meeting' AND entity_id = ?
               ORDER BY created_at DESC, id DESC LIMIT 30""",
            (meeting_id,),
        ).fetchall()
    attendees = []
    for row in attendee_rows:
        attendee = _teacher_dict(row)
        attendee["attendanceStatus"] = attendee.pop("attendance_status")
        attendees.append(attendee)
    decisions = [_decision_dict(row) for row in decision_rows]
    meeting["attendees"] = attendees
    meeting["decisions"] = decisions
    meeting["timeline"] = [dict(row) for row in timeline_rows]
    meeting["minutesReady"] = bool(
        (meeting.get("agenda") or "").strip()
        and (meeting.get("discussionSummary") or "").strip()
        and attendees
        and decisions
    )
    return meeting


def _decision_attention(conn, academic_year: str, limit: int = 6):
    rows = conn.execute(
        """SELECT d.*, m.title AS meeting_title
           FROM meeting_decisions d JOIN meetings m ON m.id = d.meeting_id
           WHERE m.academic_year = ? AND d.status NOT IN ('completed','cancelled')
           ORDER BY CASE WHEN d.due_date IS NOT NULL AND d.due_date < ? THEN 0 ELSE 1 END,
                    CASE WHEN d.due_date IS NULL THEN 1 ELSE 0 END,
                    d.due_date, d.id DESC LIMIT ?""",
        (academic_year, _oman_today_iso(), limit),
    ).fetchall()
    return [_decision_dict(row) for row in rows]


def _plan_unit_dict(row):
    item = dict(row)
    for source, target in [
        ("plan_id", "planId"),
        ("planned_start", "plannedStart"),
        ("planned_end", "plannedEnd"),
        ("progress_percent", "progressPercent"),
        ("delay_reason", "delayReason"),
        ("responsible_teacher_id", "responsibleTeacherId"),
        ("responsible_name", "responsibleName"),
        ("plan_title", "planTitle"),
        ("plan_subject", "planSubject"),
        ("plan_grade", "planGrade"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    status = item.get("status", "not_started")
    end_date = item.get("plannedEnd")
    if status != "completed" and item.get("progressPercent", 0) < 100 and end_date and end_date < _oman_today_iso():
        item["effectiveStatus"] = "overdue"
    else:
        item["effectiveStatus"] = status
    return item


def _plan_dict(row):
    item = dict(row)
    for source, target in [
        ("academic_year", "academicYear"),
        ("owner_teacher_id", "ownerTeacherId"),
        ("owner_name", "ownerName"),
        ("start_date", "startDate"),
        ("end_date", "endDate"),
        ("unit_count", "unitCount"),
        ("completed_unit_count", "completedUnitCount"),
        ("overdue_unit_count", "overdueUnitCount"),
        ("progress_percent", "progressPercent"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    item["progressPercent"] = int(round(float(item.get("progressPercent") or 0)))
    return item


def _plan_summary_rows(conn, plan_id: int | None = None):
    where = "WHERE p.id = ?" if plan_id is not None else ""
    params: tuple = (plan_id,) if plan_id is not None else ()
    today = _oman_today_iso()
    return conn.execute(
        f"""SELECT p.*, t.name AS owner_name,
               (SELECT COUNT(*) FROM curriculum_units u WHERE u.plan_id = p.id) AS unit_count,
               (SELECT COUNT(*) FROM curriculum_units u WHERE u.plan_id = p.id AND (u.status = 'completed' OR u.progress_percent = 100)) AS completed_unit_count,
               (SELECT COUNT(*) FROM curriculum_units u WHERE u.plan_id = p.id AND u.status != 'completed' AND u.progress_percent < 100 AND u.planned_end IS NOT NULL AND u.planned_end < ?) AS overdue_unit_count,
               COALESCE((SELECT AVG(u.progress_percent) FROM curriculum_units u WHERE u.plan_id = p.id), 0) AS progress_percent
           FROM curriculum_plans p
           LEFT JOIN teachers t ON t.id = p.owner_teacher_id
           {where}
           ORDER BY CASE p.status WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, p.subject, p.grade, p.id DESC""",
        (today, *params),
    ).fetchall()


def _plan_detail(plan_id: int):
    with connect() as conn:
        rows = _plan_summary_rows(conn, plan_id)
        if not rows:
            return None
        plan = _plan_dict(rows[0])
        unit_rows = conn.execute(
            """SELECT u.*, t.name AS responsible_name
               FROM curriculum_units u
               LEFT JOIN teachers t ON t.id = u.responsible_teacher_id
               WHERE u.plan_id = ? ORDER BY u.sequence, u.id""",
            (plan_id,),
        ).fetchall()
        timeline_rows = conn.execute(
            """SELECT id, activity_type, title, detail, created_at
               FROM activities WHERE entity_type = 'curriculum_plan' AND entity_id = ?
               ORDER BY created_at DESC, id DESC LIMIT 40""",
            (plan_id,),
        ).fetchall()
    plan["units"] = [_plan_unit_dict(row) for row in unit_rows]
    plan["timeline"] = [dict(row) for row in timeline_rows]
    return plan


def _planning_attention(conn, academic_year: str, limit: int = 6):
    rows = conn.execute(
        """SELECT u.*, t.name AS responsible_name, p.title AS plan_title, p.subject AS plan_subject, p.grade AS plan_grade
           FROM curriculum_units u
           JOIN curriculum_plans p ON p.id = u.plan_id
           LEFT JOIN teachers t ON t.id = u.responsible_teacher_id
           WHERE p.academic_year = ? AND p.status = 'active' AND u.status != 'completed' AND u.progress_percent < 100
             AND u.planned_end IS NOT NULL AND u.planned_end < ?
           ORDER BY u.planned_end, u.sequence, u.id LIMIT ?""",
        (academic_year, _oman_today_iso(), limit),
    ).fetchall()
    return [_plan_unit_dict(row) for row in rows]


def _normalize_plan_dates(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    start = _validate_iso_date(start_date, "تاريخ بداية الخطة") if start_date else None
    end = _validate_iso_date(end_date, "تاريخ نهاية الخطة") if end_date else None
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="تاريخ نهاية الخطة يجب ألا يسبق تاريخ البداية.")
    return start, end


def _normalize_unit_payload(payload: CurriculumUnitPayload) -> tuple[str | None, str | None, int, str]:
    start = _validate_iso_date(payload.plannedStart, "بداية الوحدة") if payload.plannedStart else None
    end = _validate_iso_date(payload.plannedEnd, "نهاية الوحدة") if payload.plannedEnd else None
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="نهاية الوحدة يجب ألا تسبق بدايتها.")
    progress = payload.progressPercent
    status = payload.status
    if status == "completed" or progress == 100:
        progress, status = 100, "completed"
    elif progress > 0 and status == "not_started":
        status = "in_progress"
    return start, end, progress, status


def _supervision_action_dict(row):
    item = dict(row)
    for source, target in [
        ("visit_id", "visitId"),
        ("responsible_teacher_id", "responsibleTeacherId"),
        ("responsible_name", "responsibleName"),
        ("due_date", "dueDate"),
        ("completed_at", "completedAt"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    base_status = item.get("status", "new")
    item["baseStatus"] = base_status
    due_date = item.get("dueDate")
    if base_status not in {"completed", "cancelled"} and due_date and due_date < _oman_today_iso():
        item["status"] = "overdue"
    return item


def _supervision_visit_dict(row):
    item = dict(row)
    for source, target in [
        ("teacher_id", "teacherId"),
        ("teacher_name", "teacherName"),
        ("teacher_subject", "teacherSubject"),
        ("visit_type", "visitType"),
        ("visit_date", "visitDate"),
        ("period_label", "periodLabel"),
        ("lesson_title", "lessonTitle"),
        ("development_areas", "developmentAreas"),
        ("followup_date", "followupDate"),
        ("followup_notes", "followupNotes"),
        ("academic_year", "academicYear"),
        ("action_count", "actionCount"),
        ("open_action_count", "openActionCount"),
        ("completed_action_count", "completedActionCount"),
        ("overdue_action_count", "overdueActionCount"),
        ("closed_at", "closedAt"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    status = item.get("status", "planned")
    today = _oman_today_iso()
    if status != "closed" and item.get("overdueActionCount", 0) > 0:
        item["effectiveStatus"] = "overdue"
    elif status == "planned" and item.get("visitDate") and item["visitDate"] < today:
        item["effectiveStatus"] = "overdue"
    elif status == "needs_followup" and item.get("followupDate") and item["followupDate"] < today:
        item["effectiveStatus"] = "overdue"
    else:
        item["effectiveStatus"] = status
    return item


def _supervision_summary_rows(conn, visit_id: int | None = None):
    where = "WHERE v.id = ?" if visit_id is not None else ""
    today = _oman_today_iso()
    params: tuple = (today, visit_id) if visit_id is not None else (today,)
    return conn.execute(
        f"""SELECT v.*, t.name AS teacher_name, t.subject AS teacher_subject,
               (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id) AS action_count,
               (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')) AS open_action_count,
               (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id AND a.status = 'completed') AS completed_action_count,
               (SELECT COUNT(*) FROM supervision_actions a
                WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')
                  AND a.due_date IS NOT NULL AND a.due_date < ?) AS overdue_action_count
           FROM supervision_visits v
           JOIN teachers t ON t.id = v.teacher_id
           {where}
           ORDER BY v.visit_date DESC, v.id DESC""",
        params,
    ).fetchall()


def _supervision_detail(visit_id: int):
    with connect() as conn:
        rows = _supervision_summary_rows(conn, visit_id)
        if not rows:
            return None
        visit = _supervision_visit_dict(rows[0])
        action_rows = conn.execute(
            """SELECT a.*, t.name AS responsible_name
               FROM supervision_actions a
               LEFT JOIN teachers t ON t.id = a.responsible_teacher_id
               WHERE a.visit_id = ?
               ORDER BY CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END,
                        CASE WHEN a.due_date IS NULL THEN 1 ELSE 0 END, a.due_date, a.id""",
            (visit_id,),
        ).fetchall()
        timeline_rows = conn.execute(
            """SELECT id, activity_type, title, detail, created_at
               FROM activities WHERE entity_type = 'supervision_visit' AND entity_id = ?
               ORDER BY created_at DESC, id DESC LIMIT 40""",
            (visit_id,),
        ).fetchall()
    visit["actions"] = [_supervision_action_dict(row) for row in action_rows]
    visit["timeline"] = [dict(row) for row in timeline_rows]
    visit["reportReady"] = bool(
        visit.get("status") != "planned"
        and (visit.get("lessonTitle") or "").strip()
        and ((visit.get("strengths") or "").strip() or (visit.get("developmentAreas") or "").strip())
        and (visit.get("recommendations") or "").strip()
    )
    return visit


def _supervision_attention(conn, academic_year: str, limit: int = 6):
    today = _oman_today_iso()
    rows = conn.execute(
        """SELECT v.*, t.name AS teacher_name, t.subject AS teacher_subject,
                  (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id) AS action_count,
                  (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')) AS open_action_count,
                  (SELECT COUNT(*) FROM supervision_actions a WHERE a.visit_id = v.id AND a.status = 'completed') AS completed_action_count,
                  (SELECT COUNT(*) FROM supervision_actions a
                   WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')
                     AND a.due_date IS NOT NULL AND a.due_date < ?) AS overdue_action_count
           FROM supervision_visits v JOIN teachers t ON t.id = v.teacher_id
           WHERE v.academic_year = ? AND v.status != 'closed'
             AND (
                  (v.status = 'planned' AND v.visit_date < ?)
                  OR (v.status = 'needs_followup' AND v.followup_date IS NOT NULL AND v.followup_date < ?)
                  OR EXISTS (
                      SELECT 1 FROM supervision_actions a
                      WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')
                        AND a.due_date IS NOT NULL AND a.due_date < ?
                  )
             )
           ORDER BY CASE
                        WHEN EXISTS (
                            SELECT 1 FROM supervision_actions a
                            WHERE a.visit_id = v.id AND a.status NOT IN ('completed','cancelled')
                              AND a.due_date IS NOT NULL AND a.due_date < ?
                        ) THEN 0
                        ELSE 1
                    END,
                    CASE WHEN v.status = 'needs_followup' THEN COALESCE(v.followup_date, v.visit_date) ELSE v.visit_date END,
                    v.id
           LIMIT ?""",
        (today, academic_year, today, today, today, today, limit),
    ).fetchall()
    return [_supervision_visit_dict(row) for row in rows]


def _normalize_supervision_visit(payload: SupervisionVisitPayload) -> tuple[str, str | None]:
    visit_date = _validate_iso_date(payload.visitDate, "تاريخ الزيارة")
    followup_date = _validate_iso_date(payload.followupDate, "موعد المتابعة") if payload.followupDate else None
    if followup_date and followup_date < visit_date:
        raise HTTPException(status_code=422, detail="موعد المتابعة يجب ألا يسبق تاريخ الزيارة.")
    return visit_date, followup_date


def _get_request_rows():
    with connect() as conn:
        return conn.execute(
            """
            SELECT r.*, ry.academic_year, t.name AS teacher_name
            FROM upload_requests r JOIN teachers t ON t.id = r.teacher_id
            LEFT JOIN request_record_years ry ON ry.request_id = r.id
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
            SELECT r.*, ry.academic_year, t.name AS teacher_name
            FROM upload_requests r JOIN teachers t ON t.id = r.teacher_id
            LEFT JOIN request_record_years ry ON ry.request_id = r.id
            WHERE r.token_hash = ?
            """,
            (digest,),
        ).fetchone()


def _achievement_action_dict(row):
    item = dict(row)
    for source, target in [
        ("assessment_id", "assessmentId"),
        ("action_type", "actionType"),
        ("target_group", "targetGroup"),
        ("responsible_teacher_id", "responsibleTeacherId"),
        ("responsible_name", "responsibleName"),
        ("start_date", "startDate"),
        ("due_date", "dueDate"),
        ("baseline_indicator", "baselineIndicator"),
        ("target_indicator", "targetIndicator"),
        ("outcome_indicator", "outcomeIndicator"),
        ("completed_at", "completedAt"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    base_status = item.get("status", "new")
    item["baseStatus"] = base_status
    due_date = item.get("dueDate")
    if base_status not in {"completed", "cancelled"} and due_date and due_date < _oman_today_iso():
        item["status"] = "overdue"
    return item


def _achievement_metric_dict(row):
    if row is None:
        return None
    item = dict(row)
    for source, target in [
        ("action_id", "actionId"),
        ("metric_name", "metricName"),
        ("baseline_value", "baselineValue"),
        ("target_value", "targetValue"),
        ("outcome_value", "outcomeValue"),
        ("measured_at", "measuredAt"),
        ("reference_source", "referenceSource"),
        ("reference_year", "referenceYear"),
        ("reference_note", "referenceNote"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    item.update(evaluate_impact(
        direction=item["direction"],
        baseline_value=item["baselineValue"],
        target_value=item["targetValue"],
        outcome_value=item.get("outcomeValue"),
    ))
    return item


def _achievement_action_with_metric(conn, action_id: int):
    row = conn.execute(
        """SELECT x.*, t.name AS responsible_name FROM achievement_actions x
           LEFT JOIN teachers t ON t.id = x.responsible_teacher_id WHERE x.id = ?""",
        (action_id,),
    ).fetchone()
    if row is None:
        return None
    item = _achievement_action_dict(row)
    metric_row = conn.execute("SELECT * FROM achievement_action_metrics WHERE action_id = ?", (action_id,)).fetchone()
    item["metric"] = _achievement_metric_dict(metric_row)
    return item


def _achievement_assessment_dict(row):
    item = dict(row)
    for source, target in [
        ("assessment_type", "assessmentType"),
        ("assessment_date", "assessmentDate"),
        ("academic_year", "academicYear"),
        ("teacher_id", "teacherId"),
        ("teacher_name", "teacherName"),
        ("max_score", "maxScore"),
        ("student_count", "studentCount"),
        ("average_score", "averageScore"),
        ("highest_score", "highestScore"),
        ("lowest_score", "lowestScore"),
        ("mastery_threshold_pct", "masteryThresholdPct"),
        ("mastery_reference_source", "masteryReferenceSource"),
        ("mastery_reference_year", "masteryReferenceYear"),
        ("mastery_reference_note", "masteryReferenceNote"),
        ("mastered_count", "masteredCount"),
        ("near_mastery_count", "nearMasteryCount"),
        ("intervention_count", "interventionCount"),
        ("action_count", "actionCount"),
        ("remedial_action_count", "remedialActionCount"),
        ("enrichment_action_count", "enrichmentActionCount"),
        ("open_action_count", "openActionCount"),
        ("overdue_action_count", "overdueActionCount"),
        ("measured_action_count", "measuredActionCount"),
        ("target_met_action_count", "targetMetActionCount"),
        ("unmeasured_completed_action_count", "unmeasuredCompletedActionCount"),
        ("impact_review_action_count", "impactReviewActionCount"),
        ("created_at", "createdAt"),
        ("updated_at", "updatedAt"),
    ]:
        if source in item:
            item[target] = item.pop(source)
    item["masteryReferenceSource"] = item.get("masteryReferenceSource") or ""
    item["masteryReferenceYear"] = item.get("masteryReferenceYear") or ""
    item["masteryReferenceNote"] = item.get("masteryReferenceNote") or ""
    student_count = int(item.get("studentCount") or 0)
    mastered = int(item.get("masteredCount") or 0)
    max_score = float(item.get("maxScore") or 0)
    avg = item.get("averageScore")
    item["masteryPercent"] = int(round(100 * mastered / student_count)) if student_count else 0
    item["averagePercent"] = int(round(100 * float(avg) / max_score)) if avg is not None and max_score > 0 else 0
    return item


def _achievement_summary_rows(conn, assessment_id: int | None = None):
    where = "WHERE a.id = ?" if assessment_id is not None else ""
    today = _oman_today_iso()
    params: tuple = (today, assessment_id) if assessment_id is not None else (today,)
    return conn.execute(
        f"""SELECT a.*, t.name AS teacher_name,
               s.mastery_reference_source, s.mastery_reference_year, s.mastery_reference_note,
               (SELECT COUNT(*) FROM achievement_actions x WHERE x.assessment_id = a.id) AS action_count,
               (SELECT COUNT(*) FROM achievement_actions x WHERE x.assessment_id = a.id AND x.action_type = 'remedial') AS remedial_action_count,
               (SELECT COUNT(*) FROM achievement_actions x WHERE x.assessment_id = a.id AND x.action_type = 'enrichment') AS enrichment_action_count,
               (SELECT COUNT(*) FROM achievement_actions x WHERE x.assessment_id = a.id AND x.status NOT IN ('completed','cancelled')) AS open_action_count,
               (SELECT COUNT(*) FROM achievement_actions x WHERE x.assessment_id = a.id AND x.status NOT IN ('completed','cancelled') AND x.due_date IS NOT NULL AND x.due_date < ?) AS overdue_action_count,
               (SELECT COUNT(*) FROM achievement_actions x JOIN achievement_action_metrics m ON m.action_id = x.id WHERE x.assessment_id = a.id AND m.outcome_value IS NOT NULL) AS measured_action_count,
               (SELECT COUNT(*) FROM achievement_actions x JOIN achievement_action_metrics m ON m.action_id = x.id WHERE x.assessment_id = a.id AND m.outcome_value IS NOT NULL AND ((m.direction = 'higher_better' AND m.outcome_value >= m.target_value) OR (m.direction = 'lower_better' AND m.outcome_value <= m.target_value))) AS target_met_action_count,
               (SELECT COUNT(*) FROM achievement_actions x LEFT JOIN achievement_action_metrics m ON m.action_id = x.id WHERE x.assessment_id = a.id AND x.status = 'completed' AND (m.action_id IS NULL OR m.outcome_value IS NULL)) AS unmeasured_completed_action_count,
               (SELECT COUNT(*) FROM achievement_actions x JOIN achievement_action_metrics m ON m.action_id = x.id WHERE x.assessment_id = a.id AND x.status = 'completed' AND m.outcome_value IS NOT NULL AND ((m.direction = 'higher_better' AND m.outcome_value <= m.baseline_value) OR (m.direction = 'lower_better' AND m.outcome_value >= m.baseline_value))) AS impact_review_action_count
           FROM achievement_assessments a
           LEFT JOIN teachers t ON t.id = a.teacher_id
           LEFT JOIN achievement_assessment_standards s ON s.assessment_id = a.id
           {where}
           ORDER BY a.assessment_date DESC, a.id DESC""",
        params,
    ).fetchall()


def _achievement_detail(assessment_id: int):
    with connect() as conn:
        rows = _achievement_summary_rows(conn, assessment_id)
        if not rows:
            return None
        assessment = _achievement_assessment_dict(rows[0])
        action_rows = conn.execute(
            """SELECT x.*, t.name AS responsible_name
               FROM achievement_actions x
               LEFT JOIN teachers t ON t.id = x.responsible_teacher_id
               WHERE x.assessment_id = ?
               ORDER BY CASE WHEN x.status IN ('completed','cancelled') THEN 1 ELSE 0 END,
                        CASE WHEN x.due_date IS NULL THEN 1 ELSE 0 END, x.due_date, x.id""",
            (assessment_id,),
        ).fetchall()
        action_ids = [row["id"] for row in action_rows]
        metric_rows = conn.execute(
            f"SELECT * FROM achievement_action_metrics WHERE action_id IN ({','.join('?' for _ in action_ids)})",
            action_ids,
        ).fetchall() if action_ids else []
        metrics = {row["action_id"]: _achievement_metric_dict(row) for row in metric_rows}
        timeline_rows = conn.execute(
            """SELECT id, activity_type, title, detail, created_at
               FROM activities WHERE entity_type = 'achievement_assessment' AND entity_id = ?
               ORDER BY created_at DESC, id DESC LIMIT 40""",
            (assessment_id,),
        ).fetchall()
    assessment["actions"] = []
    for row in action_rows:
        action = _achievement_action_dict(row)
        action["metric"] = metrics.get(row["id"])
        assessment["actions"].append(action)
    assessment["timeline"] = [dict(row) for row in timeline_rows]
    assessment["analysisReady"] = bool(
        assessment["status"] != "draft"
        and assessment["studentCount"] > 0
        and assessment["masteredCount"] + assessment["nearMasteryCount"] + assessment["interventionCount"] == assessment["studentCount"]
    )
    return assessment


def _achievement_attention(conn, academic_year: str, limit: int = 6):
    rows = _achievement_summary_rows(conn)
    items = [_achievement_assessment_dict(row) for row in rows if row["academic_year"] == academic_year]
    needs = [
        item for item in items
        if item["status"] != "draft" and (
            item["overdueActionCount"] > 0
            or item.get("unmeasuredCompletedActionCount", 0) > 0
            or item.get("impactReviewActionCount", 0) > 0
            or item.get("interventionCount", 0) > 0
        )
    ]
    needs.sort(key=lambda item: (
        0 if item["overdueActionCount"] else 1 if item.get("impactReviewActionCount", 0) else 2 if item.get("unmeasuredCompletedActionCount", 0) else 3,
        -item.get("interventionCount", 0), item["assessmentDate"], item["id"]
    ))
    return needs[:limit]


def _validate_achievement_payload(payload: AchievementAssessmentPayload) -> None:
    academic_year = _validate_academic_year(payload.academicYear)
    _validate_date_in_academic_year(payload.assessmentDate, academic_year, "تاريخ التقويم")
    if not payload.masteryReferenceSource.strip():
        raise HTTPException(status_code=422, detail="وثّق مرجع حد الإتقان المستخدم. المرصد لا يعتمد حدًا تربويًا بلا مصدر عُماني معتمد.")
    if payload.teacherId is not None:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone():
                raise HTTPException(status_code=422, detail="المعلم المسؤول غير موجود.")
    for value, label in [
        (payload.averageScore, "المتوسط"),
        (payload.highestScore, "أعلى درجة"),
        (payload.lowestScore, "أدنى درجة"),
    ]:
        if value is not None and value > payload.maxScore:
            raise HTTPException(status_code=422, detail=f"{label} لا يمكن أن يتجاوز الدرجة الكلية.")
    if payload.lowestScore is not None and payload.highestScore is not None and payload.lowestScore > payload.highestScore:
        raise HTTPException(status_code=422, detail="أدنى درجة لا يمكن أن تتجاوز أعلى درجة.")
    if payload.averageScore is not None and payload.lowestScore is not None and payload.averageScore < payload.lowestScore:
        raise HTTPException(status_code=422, detail="المتوسط لا يمكن أن يكون أقل من أدنى درجة.")
    if payload.averageScore is not None and payload.highestScore is not None and payload.averageScore > payload.highestScore:
        raise HTTPException(status_code=422, detail="المتوسط لا يمكن أن يتجاوز أعلى درجة.")
    classified = payload.masteredCount + payload.nearMasteryCount + payload.interventionCount
    if classified > payload.studentCount:
        raise HTTPException(status_code=422, detail="مجموع فئات الأداء لا يمكن أن يتجاوز عدد الطلبة.")


def _validate_achievement_action(payload: AchievementActionPayload) -> tuple[str | None, str | None]:
    start = _validate_iso_date(payload.startDate, "بداية التدخل") if payload.startDate else None
    due = _validate_iso_date(payload.dueDate, "موعد المتابعة") if payload.dueDate else None
    if start and due and due < start:
        raise HTTPException(status_code=422, detail="موعد المتابعة يجب ألا يسبق بداية التدخل.")
    if payload.responsibleTeacherId is not None:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM teachers WHERE id = ?", (payload.responsibleTeacherId,)).fetchone():
                raise HTTPException(status_code=422, detail="المعلم المسؤول عن التدخل غير موجود.")
    return start, due


def _validate_achievement_metric(payload: AchievementMetricPayload) -> str | None:
    if not payload.referenceSource.strip():
        raise HTTPException(status_code=422, detail="وثّق مصدر الهدف أو المعيار المستخدم في قياس الأثر.")
    measured_at = _validate_iso_date(payload.measuredAt, "تاريخ القياس النهائي") if payload.measuredAt else None
    if payload.outcomeValue is not None and measured_at is None:
        raise HTTPException(status_code=422, detail="أدخل تاريخ القياس النهائي عند تسجيل النتيجة الفعلية.")
    if payload.outcomeValue is None and measured_at is not None:
        raise HTTPException(status_code=422, detail="لا يمكن تسجيل تاريخ قياس نهائي دون قيمة نتيجة فعلية.")
    return measured_at



REPORT_TYPES = {"department", "teacher", "planning", "achievement", "supervision", "meetings", "events"}


def _impact_status_label(value: str | None) -> str:
    labels = {
        "pending": "لم يُقَس بعد",
        "target_met": "حقق الهدف المسجل",
        "improved_not_met": "تحسن ولم يبلغ الهدف المسجل",
        "no_change": "لم يحدث تغير",
        "regressed": "تراجع المؤشر",
    }
    return labels.get(value or "", value or "—")


def _report_status_label(value: str | None) -> str:
    labels = {
        "active": "نشطة", "completed": "مكتملة", "archived": "مؤرشفة",
        "planned": "مخططة", "held": "منفذة", "cancelled": "ملغاة",
        "needs_followup": "تحتاج متابعة", "closed": "مغلقة", "overdue": "متأخرة",
        "draft": "مسودة", "recorded": "مسجلة", "reviewed": "مراجعة مكتملة",
        "new": "جديد", "in_progress": "قيد التنفيذ", "approved": "معتمد",
        "review": "قيد المراجعة", "received": "مستلم", "waiting_upload": "بانتظار الرفع",
        "needs_revision": "يحتاج تعديل", "late": "متأخر",
    }
    return labels.get(value or "", value or "—")


def _report_pct(numerator: float, denominator: float) -> int:
    return int(round(100 * numerator / denominator)) if denominator else 0


def _achievement_standard_aggregate(rows: list[dict]) -> dict:
    eligible = [row for row in rows if row.get("status") != "draft" and row.get("studentCount", 0) > 0]
    if not eligible:
        return {"comparable": False, "rate": 0, "students": 0, "mastered": 0, "detail": "لا توجد تقويمات مكتملة قابلة للحساب."}
    signatures = {
        (
            round(float(row.get("masteryThresholdPct", 0)), 6),
            str(row.get("masteryReferenceSource") or "").strip(),
            str(row.get("masteryReferenceYear") or "").strip(),
        )
        for row in eligible
    }
    documented = all(signature[1] for signature in signatures)
    students = sum(int(row.get("studentCount", 0)) for row in eligible)
    mastered = sum(int(row.get("masteredCount", 0)) for row in eligible)
    comparable = documented and len(signatures) == 1
    if not comparable:
        return {
            "comparable": False, "rate": 0, "students": students, "mastered": mastered,
            "detail": "تختلف حدود أو مراجع التصنيف بين التقويمات؛ لذلك لا تُجمع في نسبة معيارية واحدة.",
        }
    threshold, source, reference_year = next(iter(signatures))
    rate = _report_pct(mastered, students)
    ref = f"{source}{f' • {reference_year}' if reference_year else ''} • الحد {threshold:g}%"
    return {"comparable": True, "rate": rate, "students": students, "mastered": mastered, "detail": ref}


def _report_section(section_id: str, title: str, columns: list[tuple[str, str]], rows: list[dict], description: str = "") -> dict:
    return {
        "id": section_id,
        "title": title,
        "description": description,
        "columns": [{"key": key, "label": label} for key, label in columns],
        "rows": rows,
    }


def _report_metric(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _official_report(report_type: str, academic_year: str, term: str, teacher_id: int | None = None) -> dict:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=404, detail="نوع التقرير غير مدعوم.")

    with connect() as conn:
        teachers = _teachers_for_year(conn, academic_year)
        teacher = next((item for item in teachers if item["id"] == teacher_id), None) if teacher_id is not None else None
        if report_type == "teacher" and teacher is None:
            raise HTTPException(status_code=422, detail="اختر معلمًا موجودًا لإنشاء تقرير المعلم.")

        requests = [_request_dict(r) for r in conn.execute(
            """SELECT r.*, ry.academic_year, t.name AS teacher_name FROM upload_requests r JOIN teachers t ON t.id=r.teacher_id LEFT JOIN request_record_years ry ON ry.request_id=r.id ORDER BY r.created_at DESC"""
        ).fetchall()]
        documents = [_document_dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()]
        events = [_event_dict(r) for r in conn.execute(
            """SELECT e.*, ey.academic_year, COUNT(m.id) AS media_count FROM events e LEFT JOIN event_media m ON m.event_id=e.id LEFT JOIN event_record_years ey ON ey.event_id=e.id GROUP BY e.id ORDER BY e.event_date DESC"""
        ).fetchall()]
        meetings = [_meeting_dict(r) for r in _meeting_summary_rows(conn)]
        plans = [_plan_dict(r) for r in _plan_summary_rows(conn)]
        visits = [_supervision_visit_dict(r) for r in _supervision_summary_rows(conn)]
        assessments = [_achievement_assessment_dict(r) for r in _achievement_summary_rows(conn)]

        term_filter = "" if term == "العام كاملًا" else term
        meetings_scope = [x for x in meetings if x["academicYear"] == academic_year]
        plans_scope = [x for x in plans if x["academicYear"] == academic_year and (not term_filter or x["term"] == term_filter)]
        visits_scope = [x for x in visits if x["academicYear"] == academic_year]
        assessments_scope = [x for x in assessments if x["academicYear"] == academic_year and (not term_filter or x["term"] == term_filter)]
        events_scope = [x for x in events if x.get("academicYear") == academic_year]
        documents_scope = [x for x in documents if x.get("academicYear") == academic_year]
        requests_scope = [x for x in requests if x.get("academicYear") == academic_year]

        generated_at = utc_now()
        base = {
            "reportType": report_type,
            "academicYear": academic_year,
            "term": term,
            "generatedAt": generated_at,
            "teacher": teacher,
            "metrics": [],
            "sections": [],
            "sourceCounts": {},
        }

        if report_type == "department":
            active_plans = [x for x in plans_scope if x["status"] == "active"]
            achievement_aggregate = _achievement_standard_aggregate(assessments_scope)
            decisions_total = sum(x["decisionCount"] for x in meetings_scope)
            decisions_done = sum(x["completedDecisionCount"] for x in meetings_scope)
            request_den = sum(1 for x in requests_scope if x["status"] != "cancelled")
            request_done = sum(1 for x in requests_scope if x["status"] == "approved")
            base.update({
                "title": "التقرير الشامل لأعمال القسم",
                "subtitle": f"ملخص مؤسسي لأعمال القسم خلال {term} من العام الدراسي {academic_year}",
                "summary": "يجمع هذا التقرير مؤشرات المعلمين والتخطيط والتحصيل والإشراف والاجتماعات والفعاليات في وثيقة واحدة، مع إبقاء كل مؤشر مرتبطًا بسجلاته الأصلية.",
                "metrics": [
                    _report_metric("المعلمون", len(teachers), "إجمالي السجلات المهنية الحالية"),
                    _report_metric("تقدم الخطط", f"{int(round(sum(x['progressPercent'] for x in active_plans)/len(active_plans))) if active_plans else 0}%", "متوسط الخطط النشطة في النطاق"),
                    _report_metric(
                        "الفئة المحققة للحد عبر التقويمات",
                        f"{achievement_aggregate['rate']}%" if achievement_aggregate["comparable"] else "غير مجمعة",
                        achievement_aggregate["detail"],
                    ),
                    _report_metric("إغلاق الزيارات", f"{_report_pct(sum(1 for x in visits_scope if x['status']=='closed'), len(visits_scope))}%", "نسبة الزيارات المغلقة من إجمالي الزيارات"),
                    _report_metric("تنفيذ القرارات", f"{_report_pct(decisions_done, decisions_total)}%", f"{decisions_done} قرارًا مكتملًا من {decisions_total}"),
                    _report_metric("اكتمال الطلبات", f"{_report_pct(request_done, request_den)}%", f"{request_done} طلبات معتمدة من {request_den}"),
                ],
                "sections": [
                    _report_section("teachers", "المعلمون", [("name","المعلم"),("subject","المادة"),("workload","النصاب"),("cvCompletion","اكتمال الملف")], [
                        {"name":x["name"],"subject":x["subject"],"workload":x["workload"],"cvCompletion":f"{x['cvCompletion']}%"} for x in teachers
                    ]),
                    _report_section("planning", "التخطيط والمنهج", [("title","الخطة"),("scope","النطاق"),("owner","المسؤول"),("progress","الإنجاز"),("overdue","متأخر")], [
                        {"title":x["title"],"scope":f"{x['subject']} • {x['grade']}","owner":x.get("ownerName") or "—","progress":f"{x['progressPercent']}%","overdue":x["overdueUnitCount"]} for x in plans_scope
                    ]),
                    _report_section("achievement", "التحصيل والنتائج", [("title","التقويم"),("scope","النطاق"),("mastery","وفق الحد المسجل"),("average","المتوسط"),("actions","تدخلات مفتوحة")], [
                        {"title":x["title"],"scope":f"{x['subject']} • {x['grade']}","mastery":f"{x['masteryPercent']}%","average":f"{x['averagePercent']}%","actions":x["openActionCount"]} for x in assessments_scope if x["status"] != "draft"
                    ]),
                    _report_section("supervision", "الإشراف الفني", [("teacher","المعلم"),("date","التاريخ"),("type","الزيارة"),("status","الحالة"),("followup","متابعات مفتوحة")], [
                        {"teacher":x["teacherName"],"date":x["visitDate"],"type":x["visitType"],"status":_report_status_label(x["effectiveStatus"]),"followup":x["openActionCount"]} for x in visits_scope
                    ]),
                    _report_section("meetings", "الاجتماعات والقرارات", [("title","الاجتماع"),("date","التاريخ"),("status","الحالة"),("decisions","القرارات"),("open","مفتوحة")], [
                        {"title":x["title"],"date":x["meetingDate"],"status":_report_status_label(x["status"]),"decisions":x["decisionCount"],"open":x["openDecisionCount"]} for x in meetings_scope
                    ]),
                    _report_section("events", "الفعاليات والتوثيق", [("title","الفعالية"),("date","التاريخ"),("type","النوع"),("participants","المشاركون"),("evidence","الأدلة")], [
                        {"title":x["title"],"date":x["eventDate"],"type":x["eventType"],"participants":x["participantCount"],"evidence":x.get("mediaCount",0)} for x in events_scope
                    ]),
                ],
                "sourceCounts": {"teachers":len(teachers),"plans":len(plans_scope),"assessments":len(assessments_scope),"visits":len(visits_scope),"meetings":len(meetings_scope),"events":len(events_scope),"documents":len(documents_scope),"requests":len(requests_scope)},
            })
            return base

        if report_type == "teacher":
            assert teacher is not None
            tid = teacher["id"]
            teacher_requests = [x for x in requests_scope if x["teacherId"] == tid]
            teacher_documents = [x for x in documents_scope if x.get("teacherId") == tid]
            teacher_visits = [x for x in visits_scope if x["teacherId"] == tid]
            teacher_assessments = [x for x in assessments_scope if x.get("teacherId") == tid]
            scoped_event_ids = {item["id"] for item in events_scope}
            teacher_events = [dict(r) for r in conn.execute(
                """SELECT e.id,e.title,e.event_type,e.event_date,l.role FROM event_teacher_links l JOIN events e ON e.id=l.event_id WHERE l.teacher_id=? ORDER BY e.event_date DESC""",
                (tid,),
            ).fetchall() if r["id"] in scoped_event_ids]
            cv_count = conn.execute("SELECT COUNT(*) FROM teacher_cv_items WHERE teacher_id=?", (tid,)).fetchone()[0]
            open_followups = sum(x["openActionCount"] for x in teacher_visits)
            base.update({
                "title": f"التقرير المهني للمعلم: {teacher['name']}",
                "subtitle": f"سجل مهني وتشغيلي خلال {term} من العام الدراسي {academic_year}",
                "summary": "يعرض التقرير الأعمال المرتبطة مباشرة بالمعلم من الملفات والتحصيل والإشراف والمشاركات، دون تحويل المؤشرات الكمية إلى أحكام تقويمية غير موثقة.",
                "metrics": [
                    _report_metric("اكتمال الملف", f"{teacher['cvCompletion']}%"),
                    _report_metric("بنود السيرة", cv_count),
                    _report_metric("الوثائق", len(teacher_documents)),
                    _report_metric("الزيارات", len(teacher_visits), f"{open_followups} متابعة مفتوحة"),
                    _report_metric("التقويمات", len(teacher_assessments)),
                    _report_metric("المشاركات", len(teacher_events), "فعاليات مرتبطة بالمعلم"),
                ],
                "sections": [
                    _report_section("requests", "الطلبات والوثائق", [("title","الطلب"),("status","الحالة"),("documents","المستندات")], [
                        {"title":x["title"],"status":_report_status_label(x["status"]),"documents":sum(1 for d in teacher_documents if d.get("requestId")==x["id"])} for x in teacher_requests
                    ]),
                    _report_section("visits", "الزيارات والإشراف", [("date","التاريخ"),("type","النوع"),("lesson","الدرس"),("status","الحالة"),("followup","متابعة")], [
                        {"date":x["visitDate"],"type":x["visitType"],"lesson":x.get("lessonTitle") or "—","status":_report_status_label(x["effectiveStatus"]),"followup":x["openActionCount"]} for x in teacher_visits
                    ]),
                    _report_section("assessments", "التحصيل", [("title","التقويم"),("scope","النطاق"),("mastery","وفق الحد المسجل"),("average","المتوسط")], [
                        {"title":x["title"],"scope":f"{x['subject']} • {x['grade']}","mastery":f"{x['masteryPercent']}%","average":f"{x['averagePercent']}%"} for x in teacher_assessments
                    ]),
                    _report_section("events", "المشاركات والفعاليات", [("title","الفعالية"),("date","التاريخ"),("type","النوع"),("role","الدور")], [
                        {"title":x["title"],"date":x["event_date"],"type":x["event_type"],"role":x["role"]} for x in teacher_events
                    ]),
                ],
                "sourceCounts": {"requests":len(teacher_requests),"documents":len(teacher_documents),"visits":len(teacher_visits),"assessments":len(teacher_assessments),"events":len(teacher_events)},
            })
            return base

        if report_type == "planning":
            rows = plans_scope
            base.update({
                "title":"تقرير التخطيط ومتابعة المنهج","subtitle":f"{term} • {academic_year}",
                "summary":"يعرض التقرير تقدم الخطط والوحدات المتأخرة كما هي مسجلة في مرصد الإنجازات، ولا يفترض اكتمال منهج لمجرد مرور الزمن.",
                "metrics":[_report_metric("الخطط",len(rows)),_report_metric("متوسط الإنجاز",f"{int(round(sum(x['progressPercent'] for x in rows)/len(rows))) if rows else 0}%"),_report_metric("الوحدات المتأخرة",sum(x["overdueUnitCount"] for x in rows)),_report_metric("خطط مكتملة",sum(1 for x in rows if x["status"]=="completed"))],
                "sections":[_report_section("plans","الخطط",[("title","الخطة"),("scope","المادة والصف"),("owner","المسؤول"),("progress","الإنجاز"),("status","الحالة"),("overdue","متأخر")],[{"title":x["title"],"scope":f"{x['subject']} • {x['grade']}","owner":x.get("ownerName") or "—","progress":f"{x['progressPercent']}%","status":_report_status_label(x["status"]),"overdue":x["overdueUnitCount"]} for x in rows])],
                "sourceCounts":{"plans":len(rows)},
            }); return base

        if report_type == "achievement":
            rows=[x for x in assessments_scope if x["status"]!="draft"]
            achievement_aggregate = _achievement_standard_aggregate(rows)
            students = achievement_aggregate["students"]
            action_rows = []
            for assessment in rows:
                detail = _achievement_detail(assessment["id"])
                if not detail:
                    continue
                for action in detail["actions"]:
                    metric = action.get("metric")
                    action_rows.append({
                        "title": action["title"],
                        "type": {"remedial": "علاجي", "enrichment": "إثرائي", "followup": "متابعة"}.get(action["actionType"], action["actionType"]),
                        "targetGroup": action.get("targetGroup") or "—",
                        "metric": metric.get("metricName") if metric else "—",
                        "baseline": f"{metric['baselineValue']} {metric.get('unit') or ''}".strip() if metric else "—",
                        "target": f"{metric['targetValue']} {metric.get('unit') or ''}".strip() if metric else "—",
                        "outcome": f"{metric['outcomeValue']} {metric.get('unit') or ''}".strip() if metric and metric.get("outcomeValue") is not None else "—",
                        "impact": _impact_status_label(metric.get("impactStatus")) if metric else "لم يُسجل مقياس",
                        "reference": (metric.get("referenceSource") or "هدف برنامج داخلي غير منسوب لمرجع") if metric else "—",
                    })
            measured=sum(x["measuredActionCount"] for x in rows); target_met=sum(x["targetMetActionCount"] for x in rows)
            base.update({
                "title":"تقرير التحصيل والنتائج","subtitle":f"{term} • {academic_year}",
                "summary":"يجمع التقرير نتائج التقويمات والتدخلات وقياس أثرها كما سُجلت. لا يضع حدًا تربويًا من عنده ولا يحول الدرجة الكلية إلى تشخيص مهاري غير موجود في البيانات.",
                "metrics":[_report_metric("التقويمات",len(rows)),_report_metric("الطلبة",students),_report_metric("الفئة المحققة للحد عبر التقويمات",f"{achievement_aggregate['rate']}%" if achievement_aggregate["comparable"] else "غير مجمعة", achievement_aggregate["detail"]),_report_metric("تدخلات مفتوحة",sum(x["openActionCount"] for x in rows)),_report_metric("تدخلات مقاسة",measured),_report_metric("حققت الهدف المسجل",target_met, f"{_report_pct(target_met, measured)}% من التدخلات المقاسة" if measured else "لا توجد قياسات نهائية")],
                "sections":[
                    _report_section("assessments","التقويمات",[("title","التقويم"),("scope","النطاق"),("teacher","المعلم"),("average","المتوسط"),("mastery","الفئة المحققة للحد المسجل"),("reference","مرجع الحد"),("actions","المتابعة")],[{"title":x["title"],"scope":f"{x['subject']} • {x['grade']}","teacher":x.get("teacherName") or "—","average":f"{x['averagePercent']}%","mastery":f"{x['masteryPercent']}% وفق {x['masteryThresholdPct']}%","reference":x.get("masteryReferenceSource") or "سجل سابق بلا مرجع موثق","actions":x["openActionCount"]} for x in rows]),
                    _report_section("interventions","التدخلات والمتابعات وقياس الأثر",[("title","التدخل"),("type","النوع"),("targetGroup","الفئة المستهدفة"),("metric","المؤشر"),("baseline","خط الأساس"),("target","الهدف المسجل"),("outcome","النتيجة"),("impact","الأثر الحسابي"),("reference","مصدر المعيار/الهدف")], action_rows, "الحكم هنا حسابي بالنسبة للهدف المسجل فقط، ولا يعني اعتماد معيار تربوي ما لم يكن مصدره موثقًا.")
                ],
                "sourceCounts":{"assessments":len(rows),"interventions":len(action_rows),"measuredInterventions":measured},
            }); return base

        if report_type == "supervision":
            rows=visits_scope
            base.update({
                "title":"تقرير الإشراف الفني والزيارات","subtitle":f"العام الدراسي {academic_year}",
                "summary":"يوثق التقرير الزيارات وحالات المتابعة المرتبطة بها، ويعرض التأخر كحالة تشغيلية لا كحكم مهني على المعلم.",
                "metrics":[_report_metric("الزيارات",len(rows)),_report_metric("مغلقة",sum(1 for x in rows if x["status"]=="closed")),_report_metric("متابعات مفتوحة",sum(x["openActionCount"] for x in rows)),_report_metric("متابعات متأخرة",sum(x["overdueActionCount"] for x in rows))],
                "sections":[_report_section("visits","الزيارات",[("teacher","المعلم"),("date","التاريخ"),("type","النوع"),("lesson","الدرس"),("status","الحالة"),("followup","متابعة")],[{"teacher":x["teacherName"],"date":x["visitDate"],"type":x["visitType"],"lesson":x.get("lessonTitle") or "—","status":_report_status_label(x["effectiveStatus"]),"followup":x["openActionCount"]} for x in rows])],
                "sourceCounts":{"visits":len(rows)},
            }); return base

        if report_type == "meetings":
            rows=meetings_scope; total=sum(x["decisionCount"] for x in rows); done=sum(x["completedDecisionCount"] for x in rows)
            base.update({
                "title":"تقرير الاجتماعات والقرارات","subtitle":f"العام الدراسي {academic_year}",
                "summary":"يعرض التقرير الاجتماعات والقرارات وحالة التنفيذ مع إبراز القرارات المفتوحة والمتأخرة من السجلات الفعلية.",
                "metrics":[_report_metric("الاجتماعات",len(rows)),_report_metric("القرارات",total),_report_metric("قرارات مكتملة",done),_report_metric("نسبة التنفيذ",f"{_report_pct(done,total)}%"),_report_metric("قرارات مفتوحة",sum(x["openDecisionCount"] for x in rows))],
                "sections":[_report_section("meetings","الاجتماعات",[("title","الاجتماع"),("date","التاريخ"),("type","النوع"),("attendees","الحضور"),("decisions","القرارات"),("open","مفتوحة")],[{"title":x["title"],"date":x["meetingDate"],"type":x["meetingType"],"attendees":x["attendeeCount"],"decisions":x["decisionCount"],"open":x["openDecisionCount"]} for x in rows])],
                "sourceCounts":{"meetings":len(rows),"decisions":total},
            }); return base

        rows=events_scope
        base.update({
            "title":"تقرير الفعاليات والتوثيق","subtitle":f"العام الدراسي {academic_year}",
            "summary":"يلخص التقرير الفعاليات والمبادرات والمشاركة والأدلة التوثيقية المسجلة ضمن نطاق العام الدراسي.",
            "metrics":[_report_metric("الفعاليات",len(rows)),_report_metric("المشاركون",sum(x["participantCount"] for x in rows)),_report_metric("الأدلة",sum(x.get("mediaCount",0) for x in rows)),_report_metric("بلا أدلة",sum(1 for x in rows if not x.get("mediaCount")))],
            "sections":[_report_section("events","الفعاليات",[("title","الفعالية"),("date","التاريخ"),("type","النوع"),("audience","الفئة"),("participants","المشاركون"),("evidence","الأدلة")],[{"title":x["title"],"date":x["eventDate"],"type":x["eventType"],"audience":x.get("audience") or "—","participants":x["participantCount"],"evidence":x.get("mediaCount",0)} for x in rows])],
            "sourceCounts":{"events":len(rows)},
        }); return base


ARCHIVE_EXPLICIT_YEAR_SOURCES = (
    ("request_record_years", "academic_year"),
    ("event_record_years", "academic_year"),
    ("teacher_record_years", "academic_year"),
    ("documents", "academic_year"),
    ("meetings", "academic_year"),
    ("curriculum_plans", "academic_year"),
    ("supervision_visits", "academic_year"),
    ("achievement_assessments", "academic_year"),
)


def _academic_year_from_date(date_value: str | None) -> str | None:
    if not date_value:
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(date_value))
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if month < 1 or month > 12:
        return None
    first = year if month >= 8 else year - 1
    return f"{first:04d}/{first + 1:04d}"


def _archive_available_years(conn) -> list[str]:
    years: set[str] = {ACADEMIC_YEAR}
    for table, column in ARCHIVE_EXPLICIT_YEAR_SOURCES:
        for row in conn.execute(f"SELECT DISTINCT {column} AS academic_year FROM {table} WHERE {column} IS NOT NULL AND TRIM({column}) <> ''").fetchall():
            value = str(row["academic_year"] or "").strip()
            try:
                years.add(_validate_academic_year(value))
            except HTTPException:
                continue
    for row in conn.execute("SELECT e.event_date FROM events e LEFT JOIN event_record_years ey ON ey.event_id=e.id WHERE ey.event_id IS NULL").fetchall():
        value = _academic_year_from_date(row["event_date"])
        if value:
            years.add(value)
    for row in conn.execute("SELECT r.created_at FROM upload_requests r LEFT JOIN request_record_years ry ON ry.request_id=r.id WHERE ry.request_id IS NULL").fetchall():
        value = _academic_year_from_date(row["created_at"])
        if value:
            years.add(value)
    return sorted(years, key=lambda value: int(value[:4]), reverse=True)


def _archive_linked_teachers(conn, *, academic_year: str, requests: list[dict], documents: list[dict], plans: list[dict], visits: list[dict], assessments: list[dict], events: list[dict], meetings: list[dict]) -> list[dict]:
    counts: dict[int, int] = {row["teacher_id"]: 0 for row in conn.execute("SELECT teacher_id FROM teacher_record_years WHERE academic_year = ?", (academic_year,)).fetchall()}

    def add(teacher_id) -> None:
        if teacher_id is None:
            return
        try:
            value = int(teacher_id)
        except (TypeError, ValueError):
            return
        counts[value] = counts.get(value, 0) + 1

    for item in requests:
        add(item.get("teacherId"))
    for item in documents:
        add(item.get("teacherId"))
    for item in plans:
        add(item.get("ownerTeacherId"))
    for item in visits:
        add(item.get("teacherId"))
    for item in assessments:
        add(item.get("teacherId"))

    event_ids = [int(item["id"]) for item in events]
    if event_ids:
        placeholders = ",".join("?" for _ in event_ids)
        for row in conn.execute(f"SELECT teacher_id FROM event_teacher_links WHERE event_id IN ({placeholders})", event_ids).fetchall():
            add(row["teacher_id"])

    meeting_ids = [int(item["id"]) for item in meetings]
    if meeting_ids:
        placeholders = ",".join("?" for _ in meeting_ids)
        for row in conn.execute(f"SELECT teacher_id FROM meeting_attendees WHERE meeting_id IN ({placeholders})", meeting_ids).fetchall():
            add(row["teacher_id"])
        for row in conn.execute(f"SELECT responsible_teacher_id FROM meeting_decisions WHERE meeting_id IN ({placeholders}) AND responsible_teacher_id IS NOT NULL", meeting_ids).fetchall():
            add(row["responsible_teacher_id"])

    plan_ids = [int(item["id"]) for item in plans]
    if plan_ids:
        placeholders = ",".join("?" for _ in plan_ids)
        for row in conn.execute(f"SELECT responsible_teacher_id FROM curriculum_units WHERE plan_id IN ({placeholders}) AND responsible_teacher_id IS NOT NULL", plan_ids).fetchall():
            add(row["responsible_teacher_id"])

    visit_ids = [int(item["id"]) for item in visits]
    if visit_ids:
        placeholders = ",".join("?" for _ in visit_ids)
        for row in conn.execute(f"SELECT responsible_teacher_id FROM supervision_actions WHERE visit_id IN ({placeholders}) AND responsible_teacher_id IS NOT NULL", visit_ids).fetchall():
            add(row["responsible_teacher_id"])

    assessment_ids = [int(item["id"]) for item in assessments]
    if assessment_ids:
        placeholders = ",".join("?" for _ in assessment_ids)
        for row in conn.execute(f"SELECT responsible_teacher_id FROM achievement_actions WHERE assessment_id IN ({placeholders}) AND responsible_teacher_id IS NOT NULL", assessment_ids).fetchall():
            add(row["responsible_teacher_id"])

    if not counts:
        return []
    ids = sorted(counts)
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT id, name, subject FROM teachers WHERE id IN ({placeholders})", ids).fetchall()
    teachers = [
        {"id": row["id"], "name": row["name"], "subject": row["subject"], "linkedRecords": counts.get(row["id"], 0)}
        for row in rows
    ]
    teachers.sort(key=lambda item: (-item["linkedRecords"], item["name"]))
    return teachers


def _archive_scope(conn, academic_year: str) -> dict:
    requests = [_request_dict(row) for row in conn.execute(
        """SELECT r.*, ry.academic_year, t.name AS teacher_name FROM upload_requests r JOIN teachers t ON t.id = r.teacher_id LEFT JOIN request_record_years ry ON ry.request_id = r.id ORDER BY r.created_at DESC"""
    ).fetchall()]
    documents = [_document_dict(row) for row in conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()]
    events = [_event_dict(row) for row in conn.execute(
        """SELECT e.*, ey.academic_year, COUNT(m.id) AS media_count FROM events e LEFT JOIN event_media m ON m.event_id = e.id LEFT JOIN event_record_years ey ON ey.event_id = e.id GROUP BY e.id ORDER BY e.event_date DESC"""
    ).fetchall()]
    meetings = [_meeting_dict(row) for row in _meeting_summary_rows(conn)]
    plans = [_plan_dict(row) for row in _plan_summary_rows(conn)]
    visits = [_supervision_visit_dict(row) for row in _supervision_summary_rows(conn)]
    assessments = [_achievement_assessment_dict(row) for row in _achievement_summary_rows(conn)]

    requests_scope = [item for item in requests if item.get("academicYear") == academic_year]
    documents_scope = [item for item in documents if item.get("academicYear") == academic_year]
    events_scope = [item for item in events if item.get("academicYear") == academic_year]
    meetings_scope = [item for item in meetings if item.get("academicYear") == academic_year]
    plans_scope = [item for item in plans if item.get("academicYear") == academic_year]
    visits_scope = [item for item in visits if item.get("academicYear") == academic_year]
    assessments_scope = [item for item in assessments if item.get("academicYear") == academic_year]

    teachers = _archive_linked_teachers(
        conn,
        academic_year=academic_year,
        requests=requests_scope,
        documents=documents_scope,
        plans=plans_scope,
        visits=visits_scope,
        assessments=assessments_scope,
        events=events_scope,
        meetings=meetings_scope,
    )
    decisions = sum(int(item.get("decisionCount") or 0) for item in meetings_scope)
    source_counts = {
        "teachers": len(teachers),
        "plans": len(plans_scope),
        "assessments": len(assessments_scope),
        "visits": len(visits_scope),
        "meetings": len(meetings_scope),
        "decisions": decisions,
        "events": len(events_scope),
        "documents": len(documents_scope),
        "requests": len(requests_scope),
    }
    total_records = sum(source_counts[key] for key in ("plans", "assessments", "visits", "meetings", "events", "documents", "requests"))

    date_values = [
        *(item.get("updatedAt") for item in plans_scope),
        *(item.get("updatedAt") for item in assessments_scope),
        *(item.get("updatedAt") for item in visits_scope),
        *(item.get("updatedAt") for item in meetings_scope),
        *(item.get("updatedAt") for item in events_scope),
        *(item.get("uploadedAt") for item in documents_scope),
        *(item.get("updatedAt") for item in requests_scope),
    ]
    latest_record_at = max((str(value) for value in date_values if value), default=None)

    coverage = [
        {"id": "planning", "label": "التخطيط والمنهج", "count": len(plans_scope), "detail": f"{sum(int(item.get('unitCount') or 0) for item in plans_scope)} وحدة منهج"},
        {"id": "achievement", "label": "التحصيل والنتائج", "count": len(assessments_scope), "detail": f"{sum(int(item.get('openActionCount') or 0) for item in assessments_scope)} تدخلات مفتوحة • {sum(int(item.get('measuredActionCount') or 0) for item in assessments_scope)} مقاسة"},
        {"id": "supervision", "label": "الإشراف والمتابعة", "count": len(visits_scope), "detail": f"{sum(int(item.get('openActionCount') or 0) for item in visits_scope)} متابعات مفتوحة"},
        {"id": "meetings", "label": "الاجتماعات والقرارات", "count": len(meetings_scope), "detail": f"{decisions} قرارًا"},
        {"id": "events", "label": "الفعاليات والتوثيق", "count": len(events_scope), "detail": f"{sum(int(item.get('mediaCount') or 0) for item in events_scope)} أدلة"},
        {"id": "documents", "label": "الوثائق والطلبات", "count": len(documents_scope) + len(requests_scope), "detail": f"{len(documents_scope)} وثيقة • {len(requests_scope)} طلبات"},
    ]

    sections = [
        _report_section("planning", "التخطيط والمنهج", [("title","الخطة"),("scope","النطاق"),("term","الفصل"),("owner","المسؤول"),("progress","الإنجاز"),("status","الحالة")], [
            {"title": item["title"], "scope": f"{item['subject']} • {item['grade']}", "term": item["term"], "owner": item.get("ownerName") or "—", "progress": f"{item['progressPercent']}%", "status": _report_status_label(item.get("status"))} for item in plans_scope
        ]),
        _report_section("achievement", "التحصيل والنتائج", [("title","التقويم"),("scope","النطاق"),("term","الفصل"),("teacher","المعلم"),("mastery","الفئة المحققة للحد المسجل"),("actions","تدخلات مفتوحة"),("measured","تدخلات مقاسة")], [
            {"title": item["title"], "scope": f"{item['subject']} • {item['grade']}", "term": item["term"], "teacher": item.get("teacherName") or "—", "mastery": f"{item['masteryPercent']}%", "actions": item.get("openActionCount", 0), "measured": item.get("measuredActionCount", 0)} for item in assessments_scope
        ]),
        _report_section("supervision", "الإشراف والمتابعة", [("teacher","المعلم"),("date","التاريخ"),("type","النوع"),("lesson","الدرس"),("status","الحالة"),("followup","متابعة")], [
            {"teacher": item.get("teacherName") or "—", "date": item["visitDate"], "type": item["visitType"], "lesson": item.get("lessonTitle") or "—", "status": _report_status_label(item.get("effectiveStatus")), "followup": item.get("openActionCount", 0)} for item in visits_scope
        ]),
        _report_section("meetings", "الاجتماعات والقرارات", [("title","الاجتماع"),("date","التاريخ"),("type","النوع"),("decisions","القرارات"),("open","مفتوحة")], [
            {"title": item["title"], "date": item["meetingDate"], "type": item["meetingType"], "decisions": item.get("decisionCount", 0), "open": item.get("openDecisionCount", 0)} for item in meetings_scope
        ]),
        _report_section("events", "الفعاليات والتوثيق", [("title","الفعالية"),("date","التاريخ"),("type","النوع"),("participants","المشاركون"),("evidence","الأدلة")], [
            {"title": item["title"], "date": item["eventDate"], "type": item["eventType"], "participants": item.get("participantCount", 0), "evidence": item.get("mediaCount", 0)} for item in events_scope
        ]),
        _report_section("documents", "الوثائق والمراجع", [("title","الوثيقة"),("category","النوع"),("scope","النطاق"),("status","الحالة"),("uploaded","تاريخ الرفع")], [
            {"title": item["title"], "category": item["category"], "scope": " • ".join([value for value in [item.get("subject"), item.get("grade")] if value]) or "—", "status": _report_status_label(item.get("status")), "uploaded": str(item.get("uploadedAt") or "")[:10]} for item in documents_scope
        ]),
        _report_section("requests", "طلبات الملفات", [("title","الطلب"),("teacher","المعلم"),("type","النوع"),("scope","النطاق"),("status","الحالة")], [
            {"title": item["title"], "teacher": item["teacherName"], "type": item["requestType"], "scope": f"{item['subject']} • {item['grade']}", "status": _report_status_label(item.get("status"))} for item in requests_scope
        ]),
    ]

    return {
        "academicYear": academic_year,
        "isCurrent": academic_year == ACADEMIC_YEAR,
        "generatedAt": utc_now(),
        "totalRecords": total_records,
        "teacherCount": len(teachers),
        "documentCount": len(documents_scope),
        "decisionCount": decisions,
        "latestRecordAt": latest_record_at,
        "sourceCounts": source_counts,
        "coverage": coverage,
        "teachers": teachers,
        "sections": sections,
    }


def _archive_summary(detail: dict) -> dict:
    return {
        "academicYear": detail["academicYear"],
        "isCurrent": detail["isCurrent"],
        "totalRecords": detail["totalRecords"],
        "teacherCount": detail["teacherCount"],
        "documentCount": detail["documentCount"],
        "decisionCount": detail["decisionCount"],
        "latestRecordAt": detail["latestRecordAt"],
        "sourceCounts": detail["sourceCounts"],
    }


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


def _activity_academic_year(conn, row) -> str:
    entity_type = row["entity_type"] if "entity_type" in row.keys() else None
    entity_id = row["entity_id"] if "entity_id" in row.keys() else None
    if not entity_type or entity_id is None:
        return _academic_year_from_date(row["created_at"]) or ACADEMIC_YEAR
    if entity_type == "event":
        found = conn.execute(
            """SELECT e.event_date, ey.academic_year FROM events e
               LEFT JOIN event_record_years ey ON ey.event_id=e.id WHERE e.id=?""",
            (entity_id,),
        ).fetchone()
        if found:
            return found["academic_year"] or _academic_year_from_date(found["event_date"]) or ACADEMIC_YEAR
    if entity_type == "meeting":
        found = conn.execute("SELECT academic_year FROM meetings WHERE id=?", (entity_id,)).fetchone()
        if found:
            return found["academic_year"]
    if entity_type == "curriculum_plan":
        found = conn.execute("SELECT academic_year FROM curriculum_plans WHERE id=?", (entity_id,)).fetchone()
        if found:
            return found["academic_year"]
    if entity_type == "supervision_visit":
        found = conn.execute("SELECT academic_year FROM supervision_visits WHERE id=?", (entity_id,)).fetchone()
        if found:
            return found["academic_year"]
    if entity_type == "achievement_assessment":
        found = conn.execute("SELECT academic_year FROM achievement_assessments WHERE id=?", (entity_id,)).fetchone()
        if found:
            return found["academic_year"]
    if entity_type == "request":
        found = conn.execute(
            """SELECT r.created_at, ry.academic_year FROM upload_requests r
               LEFT JOIN request_record_years ry ON ry.request_id=r.id WHERE r.id=?""",
            (entity_id,),
        ).fetchone()
        if found:
            return found["academic_year"] or _academic_year_from_date(found["created_at"]) or ACADEMIC_YEAR
    if entity_type == "document":
        found = conn.execute("SELECT academic_year, uploaded_at FROM documents WHERE id=?", (entity_id,)).fetchone()
        if found:
            return found["academic_year"] or _academic_year_from_date(found["uploaded_at"]) or ACADEMIC_YEAR
    # Teacher/profile activity is attached to the current master record, not a historical school-year record.
    if entity_type in {"teacher", "teacher_cv_item"}:
        return ACADEMIC_YEAR
    return _academic_year_from_date(row["created_at"]) or ACADEMIC_YEAR


def _activities_for_year(conn, academic_year: str, limit: int = 8) -> list[dict]:
    rows = conn.execute("SELECT * FROM activities ORDER BY created_at DESC, id DESC LIMIT 120").fetchall()
    return [dict(row) for row in rows if _activity_academic_year(conn, row) == academic_year][:limit]


@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.13.1", "storageMode": os.getenv("STORAGE_MODE", "auto")}


@app.get("/api/bootstrap")
def bootstrap(academicYear: str = ACADEMIC_YEAR):
    scope_year = _validate_academic_year(academicYear)
    with connect() as conn:
        teachers = _teachers_for_year(conn, scope_year)
        teacher_directory = [_teacher_dict(row) for row in conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()]
        all_requests = [_request_dict(r) for r in _get_request_rows()]
        request_items = [item for item in all_requests if item.get("academicYear") == scope_year]
        all_events = [_event_dict(r) for r in conn.execute("""SELECT e.*, ey.academic_year, COUNT(m.id) AS media_count FROM events e LEFT JOIN event_media m ON m.event_id = e.id LEFT JOIN event_record_years ey ON ey.event_id = e.id GROUP BY e.id ORDER BY e.event_date DESC""").fetchall()]
        events = [item for item in all_events if item.get("academicYear") == scope_year]
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
        meetings = [item for item in (_meeting_dict(r) for r in _meeting_summary_rows(conn)) if item.get("academicYear") == scope_year]
        decision_attention = _decision_attention(conn, scope_year)
        plans = [item for item in (_plan_dict(r) for r in _plan_summary_rows(conn)) if item.get("academicYear") == scope_year]
        planning_attention = _planning_attention(conn, scope_year)
        visits = [item for item in (_supervision_visit_dict(r) for r in _supervision_summary_rows(conn)) if item.get("academicYear") == scope_year]
        supervision_attention = _supervision_attention(conn, scope_year)
        assessments = [item for item in (_achievement_assessment_dict(r) for r in _achievement_summary_rows(conn)) if item.get("academicYear") == scope_year]
        achievement_attention = _achievement_attention(conn, scope_year)
        all_documents = [_document_dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()]
        documents = [item for item in all_documents if item.get("academicYear") == scope_year or (not item.get("academicYear") and _academic_year_from_date(item.get("uploadedAt")) == scope_year)][:30]
        activities = _activities_for_year(conn, scope_year)
        available_years = sorted(set(_archive_available_years(conn)) | {scope_year}, key=lambda value: int(value[:4]), reverse=True)

    counts = _status_counts(request_items)
    request_den = sum(1 for item in request_items if item["status"] != "cancelled")
    request_done = sum(1 for item in request_items if item["status"] == "approved")
    achievement_aggregate = _achievement_standard_aggregate(assessments)
    dashboard = {
        "teacherCount": len(teachers),
        "openRequests": sum(counts.get(k, 0) for k in ["waiting_upload", "received", "review", "needs_revision", "late"]),
        "needsReview": counts.get("review", 0) + counts.get("received", 0),
        "lateRequests": counts.get("late", 0),
        "openDecisions": sum(item["openDecisionCount"] for item in meetings),
        "upcomingVisits": sum(1 for item in visits if item["status"] == "planned" and item["visitDate"] >= _oman_today_iso()) if scope_year == ACADEMIC_YEAR else 0,
        "planProgress": int(round(sum(item["progressPercent"] for item in plans if item["status"] == "active") / sum(1 for item in plans if item["status"] == "active"))) if any(item["status"] == "active" for item in plans) else 0,
        "visitProgress": int(round(100 * sum(1 for item in visits if item["status"] in {"completed", "needs_followup", "closed"}) / len(visits))) if visits else 0,
        "requestCompletion": int(round(100 * request_done / request_den)) if request_den else 0,
        "achievementMastery": achievement_aggregate["rate"] if achievement_aggregate["comparable"] else 0,
        "achievementMasteryComparable": achievement_aggregate["comparable"],
        "openAchievementActions": sum(item["openActionCount"] for item in assessments),
    }
    return {
        "academicYear": scope_year,
        "currentAcademicYear": ACADEMIC_YEAR,
        "availableAcademicYears": available_years,
        "term": "الفصل الأول",
        "dashboard": dashboard,
        "teachers": teachers,
        "teacherDirectory": teacher_directory,
        "requests": request_items,
        "events": events,
        "meetings": meetings,
        "decisionAttention": decision_attention,
        "plans": plans,
        "planningAttention": planning_attention,
        "visits": visits,
        "supervisionAttention": supervision_attention,
        "assessments": assessments,
        "achievementAttention": achievement_attention,
        "documents": documents,
        "activities": activities,
        "drive": drive.status(),
    }

@app.get("/api/reports/official")
def official_report(reportType: str = "department", academicYear: str = ACADEMIC_YEAR, term: str = "الفصل الأول", teacherId: int | None = None):
    return _official_report(reportType, academicYear, term, teacherId)



@app.get("/api/archive/years")
def archive_years():
    with connect() as conn:
        years = _archive_available_years(conn)
        summaries = [_archive_summary(_archive_scope(conn, academic_year)) for academic_year in years]
    return {"currentAcademicYear": ACADEMIC_YEAR, "generatedAt": utc_now(), "years": summaries}


@app.get("/api/archive/year")
def archive_year(academicYear: str = ACADEMIC_YEAR):
    academicYear = _validate_academic_year(academicYear)
    with connect() as conn:
        years = _archive_available_years(conn)
        if academicYear not in years:
            raise HTTPException(status_code=404, detail="العام الدراسي غير موجود في الأرشيف.")
        return _archive_scope(conn, academicYear)


@app.get("/api/search")
def global_search(q: str = "", section: str = "all", academicYear: str = "all", limit: int = 40):
    with connect() as conn:
        return run_search(conn, q=q, section=section, academic_year=academicYear, limit=limit)


@app.post("/api/teachers", status_code=201)
def create_teacher(payload: TeacherPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    now = utc_now()
    cv_fields = [payload.specialization, payload.qualification, payload.email]
    cv_completion = min(100, 40 + sum(20 for value in cv_fields if value.strip()))
    with connect() as conn:
        existing = None
        if payload.email.strip():
            existing = conn.execute("SELECT * FROM teachers WHERE lower(email)=lower(?) LIMIT 1", (payload.email.strip(),)).fetchone()
        if existing is None:
            existing = conn.execute(
                "SELECT * FROM teachers WHERE trim(name)=trim(?) AND trim(subject)=trim(?) ORDER BY id LIMIT 1",
                (payload.name, payload.subject),
            ).fetchone()
        if existing is not None:
            teacher_id = existing["id"]
            _ensure_teacher_year_links(conn, [teacher_id], academic_year)
            return {"id": teacher_id, "linkedExisting": True, "academicYear": academic_year}

        cursor = conn.execute(
            """INSERT INTO teachers
            (name, subject, specialization, qualification, experience_years, workload, cv_completion, email, phone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.name, payload.subject, payload.specialization, payload.qualification, payload.experienceYears, payload.workload, cv_completion, payload.email, payload.phone, now, now),
        )
        teacher_id = cursor.lastrowid
        _ensure_teacher_year_links(conn, [teacher_id], academic_year)
        if academic_year == ACADEMIC_YEAR:
            conn.execute(
                "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("teacher", f"إضافة {payload.name}", payload.subject, "teacher", teacher_id, now),
            )
    return {"id": teacher_id, "linkedExisting": False, "academicYear": academic_year}


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
    event_date = _validate_iso_date(payload.eventDate, "تاريخ الفعالية")
    academic_year = _validate_academic_year(payload.academicYear) if payload.academicYear else (_academic_year_from_date(event_date) or ACADEMIC_YEAR)
    _validate_date_in_academic_year(event_date, academic_year, "تاريخ الفعالية")
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
            _ensure_teacher_year_links(conn, teacher_ids, academic_year)
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO events
            (title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.title, payload.eventType, event_date, payload.location, payload.audience, payload.participantCount, payload.goals, payload.summary, payload.outcomes, payload.recommendations, tones[count % len(tones)], now, now),
        )
        event_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO event_record_years (event_id, academic_year, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (event_id, academic_year, now, now),
        )
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
    event_date = _validate_iso_date(payload.eventDate, "تاريخ الفعالية")
    academic_year = _validate_academic_year(payload.academicYear) if payload.academicYear else (_academic_year_from_date(event_date) or ACADEMIC_YEAR)
    _validate_date_in_academic_year(event_date, academic_year, "تاريخ الفعالية")
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
            _ensure_teacher_year_links(conn, teacher_ids, academic_year)
        conn.execute(
            """UPDATE events SET title = ?, event_type = ?, event_date = ?, location = ?, audience = ?,
               participant_count = ?, goals = ?, summary = ?, outcomes = ?, recommendations = ?, updated_at = ?
               WHERE id = ?""",
            (payload.title, payload.eventType, event_date, payload.location, payload.audience,
             payload.participantCount, payload.goals, payload.summary, payload.outcomes, payload.recommendations,
             now, event_id),
        )
        conn.execute(
            """INSERT INTO event_record_years (event_id, academic_year, created_at, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(event_id) DO UPDATE SET academic_year=excluded.academic_year, updated_at=excluded.updated_at""",
            (event_id, academic_year, now, now),
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
                result = drive.upload_event_file(temp_path, safe_name, mime_type, detail.get("academicYear") or ACADEMIC_YEAR, event_id, detail["title"])
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


@app.get("/api/meetings")
def list_meetings():
    with connect() as conn:
        return [_meeting_dict(row) for row in _meeting_summary_rows(conn)]


@app.post("/api/meetings", status_code=201)
def create_meeting(payload: MeetingPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    meeting_date = _validate_date_in_academic_year(payload.meetingDate, academic_year, "تاريخ الاجتماع")
    meeting_time = _validate_meeting_time(payload.meetingTime)
    now = utc_now()
    with connect() as conn:
        attendee_ids = _validate_teacher_ids(conn, payload.attendeeIds, "تتضمن قائمة الحضور معلمًا غير موجود.")
        _ensure_teacher_year_links(conn, attendee_ids, academic_year)
        cursor = conn.execute(
            """INSERT INTO meetings
               (title, meeting_type, meeting_date, meeting_time, location, agenda, discussion_summary, notes,
                academic_year, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.title.strip(), payload.meetingType.strip(), meeting_date, meeting_time, payload.location.strip(),
                payload.agenda.strip(), payload.discussionSummary.strip(), payload.notes.strip(), academic_year,
                payload.status, now, now,
            ),
        )
        meeting_id = cursor.lastrowid
        if attendee_ids:
            conn.executemany(
                "INSERT INTO meeting_attendees (meeting_id, teacher_id, attendance_status, created_at) VALUES (?, ?, 'present', ?)",
                [(meeting_id, teacher_id, now) for teacher_id in attendee_ids],
            )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("meeting", f"إنشاء اجتماع: {payload.title.strip()}", f"{len(attendee_ids)} حاضرًا", "meeting", meeting_id, now),
        )
    return {"id": meeting_id}


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int):
    detail = _meeting_detail(meeting_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الاجتماع غير موجود.")
    return detail


@app.patch("/api/meetings/{meeting_id}")
def update_meeting(meeting_id: int, payload: MeetingPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    meeting_date = _validate_date_in_academic_year(payload.meetingDate, academic_year, "تاريخ الاجتماع")
    meeting_time = _validate_meeting_time(payload.meetingTime)
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="الاجتماع غير موجود.")
        attendee_ids = _validate_teacher_ids(conn, payload.attendeeIds, "تتضمن قائمة الحضور معلمًا غير موجود.")
        _ensure_teacher_year_links(conn, attendee_ids, academic_year)
        conn.execute(
            """UPDATE meetings SET title = ?, meeting_type = ?, meeting_date = ?, meeting_time = ?, location = ?,
               agenda = ?, discussion_summary = ?, notes = ?, academic_year = ?, status = ?, updated_at = ? WHERE id = ?""",
            (
                payload.title.strip(), payload.meetingType.strip(), meeting_date, meeting_time, payload.location.strip(),
                payload.agenda.strip(), payload.discussionSummary.strip(), payload.notes.strip(), academic_year, payload.status, now, meeting_id,
            ),
        )
        conn.execute("DELETE FROM meeting_attendees WHERE meeting_id = ?", (meeting_id,))
        if attendee_ids:
            conn.executemany(
                "INSERT INTO meeting_attendees (meeting_id, teacher_id, attendance_status, created_at) VALUES (?, ?, 'present', ?)",
                [(meeting_id, teacher_id, now) for teacher_id in attendee_ids],
            )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("meeting", f"تحديث الاجتماع: {payload.title.strip()}", f"الحضور: {len(attendee_ids)}", "meeting", meeting_id, now),
        )
    return _meeting_detail(meeting_id)


@app.post("/api/plans", status_code=201)
def create_curriculum_plan(payload: CurriculumPlanPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    start_date, end_date = _normalize_plan_dates(payload.startDate, payload.endDate)
    if start_date:
        _validate_date_in_academic_year(start_date, academic_year, "تاريخ بداية الخطة")
    if end_date:
        _validate_date_in_academic_year(end_date, academic_year, "تاريخ نهاية الخطة")
    now = utc_now()
    with connect() as conn:
        if payload.ownerTeacherId is not None:
            _validate_teacher_ids(conn, [payload.ownerTeacherId], "المعلم المسؤول عن الخطة غير موجود.")
            _ensure_teacher_year_links(conn, [payload.ownerTeacherId], academic_year)
        cursor = conn.execute(
            """INSERT INTO curriculum_plans
               (title, subject, grade, term, academic_year, owner_teacher_id, start_date, end_date, notes, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.title, payload.subject, payload.grade, payload.term, academic_year, payload.ownerTeacherId, start_date, end_date, payload.notes, payload.status, now, now),
        )
        plan_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("planning", f"إنشاء خطة: {payload.title}", f"{payload.subject} • {payload.grade} • {payload.term}", "curriculum_plan", plan_id, now),
        )
    return {"id": plan_id}


@app.get("/api/plans/{plan_id}")
def get_curriculum_plan(plan_id: int):
    detail = _plan_detail(plan_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الخطة غير موجودة.")
    return detail


@app.patch("/api/plans/{plan_id}")
def update_curriculum_plan(plan_id: int, payload: CurriculumPlanPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    start_date, end_date = _normalize_plan_dates(payload.startDate, payload.endDate)
    if start_date:
        _validate_date_in_academic_year(start_date, academic_year, "تاريخ بداية الخطة")
    if end_date:
        _validate_date_in_academic_year(end_date, academic_year, "تاريخ نهاية الخطة")
    now = utc_now()
    with connect() as conn:
        if not conn.execute("SELECT id FROM curriculum_plans WHERE id = ?", (plan_id,)).fetchone():
            raise HTTPException(status_code=404, detail="الخطة غير موجودة.")
        if payload.ownerTeacherId is not None:
            _validate_teacher_ids(conn, [payload.ownerTeacherId], "المعلم المسؤول عن الخطة غير موجود.")
            _ensure_teacher_year_links(conn, [payload.ownerTeacherId], academic_year)
        conn.execute(
            """UPDATE curriculum_plans SET title=?, subject=?, grade=?, term=?, academic_year=?, owner_teacher_id=?, start_date=?, end_date=?, notes=?, status=?, updated_at=? WHERE id=?""",
            (payload.title, payload.subject, payload.grade, payload.term, academic_year, payload.ownerTeacherId, start_date, end_date, payload.notes, payload.status, now, plan_id),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("planning", f"تحديث خطة: {payload.title}", f"{payload.subject} • {payload.grade}", "curriculum_plan", plan_id, now),
        )
    return _plan_detail(plan_id)


@app.post("/api/plans/{plan_id}/units", status_code=201)
def create_curriculum_unit(plan_id: int, payload: CurriculumUnitPayload):
    planned_start, planned_end, progress, status = _normalize_unit_payload(payload)
    now = utc_now()
    with connect() as conn:
        plan = conn.execute("SELECT id, title, academic_year FROM curriculum_plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="الخطة غير موجودة.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المعلم المسؤول عن الوحدة غير موجود.")
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], plan["academic_year"])
        cursor = conn.execute(
            """INSERT INTO curriculum_units
               (plan_id, title, sequence, planned_start, planned_end, progress_percent, status, delay_reason, notes, responsible_teacher_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, payload.title, payload.sequence, planned_start, planned_end, progress, status, payload.delayReason, payload.notes, payload.responsibleTeacherId, now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("planning", f"إضافة وحدة: {payload.title}", f"{progress}% • {status}", "curriculum_plan", plan_id, now),
        )
        unit_id = cursor.lastrowid
    detail = _plan_detail(plan_id)
    return next(unit for unit in detail["units"] if unit["id"] == unit_id)


@app.patch("/api/plans/{plan_id}/units/{unit_id}")
def update_curriculum_unit(plan_id: int, unit_id: int, payload: CurriculumUnitPayload):
    planned_start, planned_end, progress, status = _normalize_unit_payload(payload)
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT id FROM curriculum_units WHERE id = ? AND plan_id = ?", (unit_id, plan_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="الوحدة غير موجودة.")
        plan = conn.execute("SELECT academic_year FROM curriculum_plans WHERE id = ?", (plan_id,)).fetchone()
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المعلم المسؤول عن الوحدة غير موجود.")
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], plan["academic_year"])
        conn.execute(
            """UPDATE curriculum_units SET title=?, sequence=?, planned_start=?, planned_end=?, progress_percent=?, status=?, delay_reason=?, notes=?, responsible_teacher_id=?, updated_at=? WHERE id=? AND plan_id=?""",
            (payload.title, payload.sequence, planned_start, planned_end, progress, status, payload.delayReason, payload.notes, payload.responsibleTeacherId, now, unit_id, plan_id),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("planning", f"تحديث وحدة: {payload.title}", f"التقدم {progress}%", "curriculum_plan", plan_id, now),
        )
    detail = _plan_detail(plan_id)
    return next(unit for unit in detail["units"] if unit["id"] == unit_id)


@app.delete("/api/plans/{plan_id}/units/{unit_id}")
def delete_curriculum_unit(plan_id: int, unit_id: int):
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT title FROM curriculum_units WHERE id = ? AND plan_id = ?", (unit_id, plan_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="الوحدة غير موجودة.")
        conn.execute("DELETE FROM curriculum_units WHERE id = ? AND plan_id = ?", (unit_id, plan_id))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("planning", f"حذف وحدة: {row['title']}", "حذف من توزيع المنهج", "curriculum_plan", plan_id, now),
        )
    return {"ok": True}


@app.get("/api/supervision/visits")
def list_supervision_visits():
    with connect() as conn:
        return [_supervision_visit_dict(row) for row in _supervision_summary_rows(conn)]


@app.post("/api/supervision/visits", status_code=201)
def create_supervision_visit(payload: SupervisionVisitPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    visit_date, followup_date = _normalize_supervision_visit(payload)
    _validate_date_in_academic_year(visit_date, academic_year, "تاريخ الزيارة")
    if followup_date:
        _validate_date_in_academic_year(followup_date, academic_year, "موعد المتابعة")
    now = utc_now()
    with connect() as conn:
        _validate_teacher_ids(conn, [payload.teacherId], "المعلم المحدد للزيارة غير موجود.")
        _ensure_teacher_year_links(conn, [payload.teacherId], academic_year)
        teacher = conn.execute("SELECT name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        closed_at = now if payload.status == "closed" else None
        cursor = conn.execute(
            """INSERT INTO supervision_visits
               (teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations,
                followup_date, followup_notes, academic_year, status, closed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.teacherId, payload.visitType.strip(), visit_date, payload.periodLabel.strip(), payload.grade.strip(), payload.lessonTitle.strip(),
             payload.objectives.strip(), payload.strengths.strip(), payload.developmentAreas.strip(), payload.recommendations.strip(),
             followup_date, payload.followupNotes.strip(), academic_year, payload.status, closed_at, now, now),
        )
        visit_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("supervision", f"إنشاء زيارة: {teacher['name']}", f"{payload.visitType.strip()} • {visit_date}", "supervision_visit", visit_id, now),
        )
    return {"id": visit_id}


@app.get("/api/supervision/visits/{visit_id}")
def get_supervision_visit(visit_id: int):
    detail = _supervision_detail(visit_id)
    if not detail:
        raise HTTPException(status_code=404, detail="الزيارة غير موجودة.")
    return detail


@app.patch("/api/supervision/visits/{visit_id}")
def update_supervision_visit(visit_id: int, payload: SupervisionVisitPayload):
    academic_year = _validate_academic_year(payload.academicYear)
    visit_date, followup_date = _normalize_supervision_visit(payload)
    _validate_date_in_academic_year(visit_date, academic_year, "تاريخ الزيارة")
    if followup_date:
        _validate_date_in_academic_year(followup_date, academic_year, "موعد المتابعة")
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT * FROM supervision_visits WHERE id = ?", (visit_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="الزيارة غير موجودة.")
        _validate_teacher_ids(conn, [payload.teacherId], "المعلم المحدد للزيارة غير موجود.")
        _ensure_teacher_year_links(conn, [payload.teacherId], academic_year)
        teacher = conn.execute("SELECT name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        closed_at = current["closed_at"]
        if payload.status == "closed" and not closed_at:
            closed_at = now
        elif payload.status != "closed":
            closed_at = None
        conn.execute(
            """UPDATE supervision_visits SET teacher_id=?, visit_type=?, visit_date=?, academic_year=?, period_label=?, grade=?, lesson_title=?, objectives=?, strengths=?,
               development_areas=?, recommendations=?, followup_date=?, followup_notes=?, status=?, closed_at=?, updated_at=? WHERE id=?""",
            (payload.teacherId, payload.visitType.strip(), visit_date, academic_year, payload.periodLabel.strip(), payload.grade.strip(), payload.lessonTitle.strip(),
             payload.objectives.strip(), payload.strengths.strip(), payload.developmentAreas.strip(), payload.recommendations.strip(), followup_date,
             payload.followupNotes.strip(), payload.status, closed_at, now, visit_id),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("supervision", f"تحديث زيارة: {teacher['name']}", payload.status, "supervision_visit", visit_id, now),
        )
    return _supervision_detail(visit_id)


@app.post("/api/supervision/visits/{visit_id}/actions", status_code=201)
def create_supervision_action(visit_id: int, payload: SupervisionActionPayload):
    due_date = _validate_iso_date(payload.dueDate, "موعد الإجراء") if payload.dueDate else None
    now = utc_now()
    with connect() as conn:
        visit = conn.execute("SELECT id, academic_year FROM supervision_visits WHERE id = ?", (visit_id,)).fetchone()
        if not visit:
            raise HTTPException(status_code=404, detail="الزيارة غير موجودة.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المسؤول عن الإجراء غير موجود.")
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], visit["academic_year"])
        completed_at = now if payload.status == "completed" else None
        cursor = conn.execute(
            """INSERT INTO supervision_actions
               (visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (visit_id, payload.title.strip(), payload.responsibleTeacherId, due_date, payload.status, payload.notes.strip(), completed_at, now, now),
        )
        action_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("supervision", f"إجراء متابعة: {payload.title.strip()}", payload.status, "supervision_visit", visit_id, now),
        )
        row = conn.execute(
            """SELECT a.*, t.name AS responsible_name FROM supervision_actions a
               LEFT JOIN teachers t ON t.id = a.responsible_teacher_id WHERE a.id = ?""",
            (action_id,),
        ).fetchone()
    return _supervision_action_dict(row)


@app.patch("/api/supervision/visits/{visit_id}/actions/{action_id}")
def update_supervision_action(visit_id: int, action_id: int, payload: SupervisionActionPayload):
    due_date = _validate_iso_date(payload.dueDate, "موعد الإجراء") if payload.dueDate else None
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT * FROM supervision_actions WHERE id = ? AND visit_id = ?", (action_id, visit_id)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="إجراء المتابعة غير موجود ضمن هذه الزيارة.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المسؤول عن الإجراء غير موجود.")
            visit = conn.execute("SELECT academic_year FROM supervision_visits WHERE id = ?", (visit_id,)).fetchone()
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], visit["academic_year"])
        completed_at = current["completed_at"]
        if payload.status == "completed" and not completed_at:
            completed_at = now
        elif payload.status != "completed":
            completed_at = None
        conn.execute(
            """UPDATE supervision_actions SET title=?, responsible_teacher_id=?, due_date=?, status=?, notes=?, completed_at=?, updated_at=?
               WHERE id=? AND visit_id=?""",
            (payload.title.strip(), payload.responsibleTeacherId, due_date, payload.status, payload.notes.strip(), completed_at, now, action_id, visit_id),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("supervision", f"تحديث إجراء: {payload.title.strip()}", payload.status, "supervision_visit", visit_id, now),
        )
        row = conn.execute(
            """SELECT a.*, t.name AS responsible_name FROM supervision_actions a
               LEFT JOIN teachers t ON t.id = a.responsible_teacher_id WHERE a.id = ?""",
            (action_id,),
        ).fetchone()
    return _supervision_action_dict(row)


@app.delete("/api/supervision/visits/{visit_id}/actions/{action_id}")
def delete_supervision_action(visit_id: int, action_id: int):
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT title FROM supervision_actions WHERE id = ? AND visit_id = ?", (action_id, visit_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="إجراء المتابعة غير موجود ضمن هذه الزيارة.")
        conn.execute("DELETE FROM supervision_actions WHERE id = ?", (action_id,))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("supervision", f"حذف إجراء: {row['title']}", "تم الحذف من متابعة الزيارة", "supervision_visit", visit_id, now),
        )
    return {"ok": True}


@app.post("/api/meetings/{meeting_id}/decisions", status_code=201)
def create_meeting_decision(meeting_id: int, payload: MeetingDecisionPayload):
    due_date = _validate_iso_date(payload.dueDate, "موعد القرار") if payload.dueDate else None
    now = utc_now()
    with connect() as conn:
        meeting = conn.execute("SELECT id, title, academic_year FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            raise HTTPException(status_code=404, detail="الاجتماع غير موجود.")
        responsible_name = payload.responsibleName.strip()
        if payload.responsibleTeacherId is not None:
            teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.responsibleTeacherId,)).fetchone()
            if not teacher:
                raise HTTPException(status_code=422, detail="المسؤول المحدد غير موجود ضمن المعلمين.")
            if not responsible_name:
                responsible_name = teacher["name"]
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], meeting["academic_year"])
        completed_at = now if payload.status == "completed" else None
        cursor = conn.execute(
            """INSERT INTO meeting_decisions
               (meeting_id, title, responsible_teacher_id, responsible_name, due_date, status, notes, completed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meeting_id, payload.title.strip(), payload.responsibleTeacherId, responsible_name, due_date,
                payload.status, payload.notes.strip(), completed_at, now, now,
            ),
        )
        decision_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("meeting", f"قرار جديد: {payload.title.strip()}", responsible_name or "دون مسؤول محدد", "meeting", meeting_id, now),
        )
        row = conn.execute("SELECT * FROM meeting_decisions WHERE id = ?", (decision_id,)).fetchone()
    return _decision_dict(row)


@app.patch("/api/meetings/{meeting_id}/decisions/{decision_id}")
def update_meeting_decision(meeting_id: int, decision_id: int, payload: MeetingDecisionPayload):
    due_date = _validate_iso_date(payload.dueDate, "موعد القرار") if payload.dueDate else None
    now = utc_now()
    with connect() as conn:
        current = conn.execute(
            "SELECT * FROM meeting_decisions WHERE id = ? AND meeting_id = ?",
            (decision_id, meeting_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="القرار غير موجود ضمن هذا الاجتماع.")
        meeting = conn.execute("SELECT academic_year FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        responsible_name = payload.responsibleName.strip()
        if payload.responsibleTeacherId is not None:
            teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.responsibleTeacherId,)).fetchone()
            if not teacher:
                raise HTTPException(status_code=422, detail="المسؤول المحدد غير موجود ضمن المعلمين.")
            if not responsible_name:
                responsible_name = teacher["name"]
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], meeting["academic_year"])
        completed_at = current["completed_at"]
        if payload.status == "completed" and not completed_at:
            completed_at = now
        elif payload.status != "completed":
            completed_at = None
        conn.execute(
            """UPDATE meeting_decisions SET title = ?, responsible_teacher_id = ?, responsible_name = ?, due_date = ?,
               status = ?, notes = ?, completed_at = ?, updated_at = ? WHERE id = ? AND meeting_id = ?""",
            (
                payload.title.strip(), payload.responsibleTeacherId, responsible_name, due_date, payload.status,
                payload.notes.strip(), completed_at, now, decision_id, meeting_id,
            ),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("meeting", f"تحديث قرار: {payload.title.strip()}", payload.status, "meeting", meeting_id, now),
        )
        row = conn.execute("SELECT * FROM meeting_decisions WHERE id = ?", (decision_id,)).fetchone()
    return _decision_dict(row)


@app.delete("/api/meetings/{meeting_id}/decisions/{decision_id}")
def delete_meeting_decision(meeting_id: int, decision_id: int):
    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT id, title FROM meeting_decisions WHERE id = ? AND meeting_id = ?",
            (decision_id, meeting_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="القرار غير موجود ضمن هذا الاجتماع.")
        conn.execute("DELETE FROM meeting_decisions WHERE id = ?", (decision_id,))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("meeting", f"حذف قرار: {row['title']}", "تم الحذف من محضر الاجتماع", "meeting", meeting_id, now),
        )
    return {"ok": True}


@app.get("/api/achievement/assessments")
def list_achievement_assessments():
    with connect() as conn:
        return [_achievement_assessment_dict(row) for row in _achievement_summary_rows(conn)]


@app.post("/api/achievement/assessments", status_code=201)
def create_achievement_assessment(payload: AchievementAssessmentPayload):
    _validate_achievement_payload(payload)
    now = utc_now()
    with connect() as conn:
        if payload.teacherId is not None:
            _validate_teacher_ids(conn, [payload.teacherId], "المعلم المسؤول عن التقويم غير موجود.")
            _ensure_teacher_year_links(conn, [payload.teacherId], payload.academicYear)
        cursor = conn.execute(
            """INSERT INTO achievement_assessments
               (title, assessment_type, subject, grade, assessment_date, term, academic_year, teacher_id,
                max_score, student_count, average_score, highest_score, lowest_score, mastery_threshold_pct,
                mastered_count, near_mastery_count, intervention_count, notes, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (payload.title, payload.assessmentType, payload.subject, payload.grade, payload.assessmentDate, payload.term,
             payload.academicYear, payload.teacherId, payload.maxScore, payload.studentCount, payload.averageScore,
             payload.highestScore, payload.lowestScore, payload.masteryThresholdPct, payload.masteredCount,
             payload.nearMasteryCount, payload.interventionCount, payload.notes, payload.status, now, now),
        )
        conn.execute(
            """INSERT INTO achievement_assessment_standards
               (assessment_id, mastery_reference_source, mastery_reference_year, mastery_reference_note, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (cursor.lastrowid, payload.masteryReferenceSource.strip(), payload.masteryReferenceYear.strip(),
             payload.masteryReferenceNote.strip(), now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"تسجيل نتيجة: {payload.title}", f"{payload.subject} • {payload.grade}", "achievement_assessment", cursor.lastrowid, now),
        )
    return _achievement_detail(cursor.lastrowid)


@app.get("/api/achievement/assessments/{assessment_id}")
def get_achievement_assessment(assessment_id: int):
    detail = _achievement_detail(assessment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="سجل التحصيل غير موجود.")
    return detail


@app.patch("/api/achievement/assessments/{assessment_id}")
def update_achievement_assessment(assessment_id: int, payload: AchievementAssessmentPayload):
    _validate_achievement_payload(payload)
    now = utc_now()
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM achievement_assessments WHERE id = ?", (assessment_id,)).fetchone():
            raise HTTPException(status_code=404, detail="سجل التحصيل غير موجود.")
        if payload.teacherId is not None:
            _validate_teacher_ids(conn, [payload.teacherId], "المعلم المسؤول عن التقويم غير موجود.")
            _ensure_teacher_year_links(conn, [payload.teacherId], payload.academicYear)
        conn.execute(
            """UPDATE achievement_assessments SET
               title=?, assessment_type=?, subject=?, grade=?, assessment_date=?, term=?, academic_year=?, teacher_id=?,
               max_score=?, student_count=?, average_score=?, highest_score=?, lowest_score=?, mastery_threshold_pct=?,
               mastered_count=?, near_mastery_count=?, intervention_count=?, notes=?, status=?, updated_at=?
               WHERE id=?""",
            (payload.title, payload.assessmentType, payload.subject, payload.grade, payload.assessmentDate, payload.term,
             payload.academicYear, payload.teacherId, payload.maxScore, payload.studentCount, payload.averageScore,
             payload.highestScore, payload.lowestScore, payload.masteryThresholdPct, payload.masteredCount,
             payload.nearMasteryCount, payload.interventionCount, payload.notes, payload.status, now, assessment_id),
        )
        conn.execute(
            """INSERT INTO achievement_assessment_standards
               (assessment_id, mastery_reference_source, mastery_reference_year, mastery_reference_note, created_at, updated_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(assessment_id) DO UPDATE SET
                 mastery_reference_source=excluded.mastery_reference_source,
                 mastery_reference_year=excluded.mastery_reference_year,
                 mastery_reference_note=excluded.mastery_reference_note,
                 updated_at=excluded.updated_at""",
            (assessment_id, payload.masteryReferenceSource.strip(), payload.masteryReferenceYear.strip(),
             payload.masteryReferenceNote.strip(), now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"تحديث نتيجة: {payload.title}", f"{payload.subject} • {payload.grade}", "achievement_assessment", assessment_id, now),
        )
    return _achievement_detail(assessment_id)


@app.post("/api/achievement/assessments/{assessment_id}/actions", status_code=201)
def create_achievement_action(assessment_id: int, payload: AchievementActionPayload):
    start, due = _validate_achievement_action(payload)
    now = utc_now()
    with connect() as conn:
        assessment = conn.execute("SELECT title, academic_year FROM achievement_assessments WHERE id = ?", (assessment_id,)).fetchone()
        if not assessment:
            raise HTTPException(status_code=404, detail="سجل التحصيل غير موجود.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المسؤول عن التدخل غير موجود.")
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], assessment["academic_year"])
        completed_at = now if payload.status == "completed" else None
        cursor = conn.execute(
            """INSERT INTO achievement_actions
               (assessment_id, action_type, title, target_group, responsible_teacher_id, start_date, due_date, status,
                baseline_indicator, target_indicator, outcome_indicator, notes, completed_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (assessment_id, payload.actionType, payload.title, payload.targetGroup, payload.responsibleTeacherId, start, due,
             payload.status, payload.baselineIndicator, payload.targetIndicator, payload.outcomeIndicator, payload.notes,
             completed_at, now, now),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"إجراء تحصيلي: {payload.title}", assessment["title"], "achievement_assessment", assessment_id, now),
        )
        created_action = _achievement_action_with_metric(conn, cursor.lastrowid)
    return created_action


@app.patch("/api/achievement/assessments/{assessment_id}/actions/{action_id}")
def update_achievement_action(assessment_id: int, action_id: int, payload: AchievementActionPayload):
    start, due = _validate_achievement_action(payload)
    now = utc_now()
    with connect() as conn:
        row = conn.execute("SELECT id FROM achievement_actions WHERE id = ? AND assessment_id = ?", (action_id, assessment_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="الإجراء التحصيلي غير موجود.")
        current = conn.execute("SELECT completed_at FROM achievement_actions WHERE id = ?", (action_id,)).fetchone()
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المسؤول عن التدخل غير موجود.")
            assessment = conn.execute("SELECT academic_year FROM achievement_assessments WHERE id = ?", (assessment_id,)).fetchone()
            _ensure_teacher_year_links(conn, [payload.responsibleTeacherId], assessment["academic_year"])
        completed_at = current["completed_at"]
        if payload.status == "completed" and not completed_at:
            completed_at = now
        elif payload.status != "completed":
            completed_at = None
        conn.execute(
            """UPDATE achievement_actions SET action_type=?, title=?, target_group=?, responsible_teacher_id=?, start_date=?, due_date=?,
               status=?, baseline_indicator=?, target_indicator=?, outcome_indicator=?, notes=?, completed_at=?, updated_at=? WHERE id=?""",
            (payload.actionType, payload.title, payload.targetGroup, payload.responsibleTeacherId, start, due, payload.status,
             payload.baselineIndicator, payload.targetIndicator, payload.outcomeIndicator, payload.notes, completed_at, now, action_id),
        )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"تحديث إجراء تحصيلي: {payload.title}", payload.status, "achievement_assessment", assessment_id, now),
        )
        updated_action = _achievement_action_with_metric(conn, action_id)
    return updated_action


@app.put("/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric")
def upsert_achievement_action_metric(assessment_id: int, action_id: int, payload: AchievementMetricPayload):
    measured_at = _validate_achievement_metric(payload)
    now = utc_now()
    with connect() as conn:
        action = conn.execute(
            "SELECT id, title FROM achievement_actions WHERE id = ? AND assessment_id = ?",
            (action_id, assessment_id),
        ).fetchone()
        if not action:
            raise HTTPException(status_code=404, detail="الإجراء التحصيلي غير موجود.")
        existing = conn.execute("SELECT created_at FROM achievement_action_metrics WHERE action_id = ?", (action_id,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE achievement_action_metrics SET metric_name=?, unit=?, direction=?, baseline_value=?, target_value=?,
                   outcome_value=?, measured_at=?, reference_source=?, reference_year=?, reference_note=?, notes=?, updated_at=?
                   WHERE action_id=?""",
                (payload.metricName, payload.unit, payload.direction, payload.baselineValue, payload.targetValue, payload.outcomeValue,
                 measured_at, payload.referenceSource, payload.referenceYear, payload.referenceNote, payload.notes, now, action_id),
            )
        else:
            conn.execute(
                """INSERT INTO achievement_action_metrics
                   (action_id, metric_name, unit, direction, baseline_value, target_value, outcome_value, measured_at,
                    reference_source, reference_year, reference_note, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (action_id, payload.metricName, payload.unit, payload.direction, payload.baselineValue, payload.targetValue, payload.outcomeValue,
                 measured_at, payload.referenceSource, payload.referenceYear, payload.referenceNote, payload.notes, now, now),
            )
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"تحديث قياس أثر: {action['title']}", payload.metricName, "achievement_assessment", assessment_id, now),
        )
        metric = conn.execute("SELECT * FROM achievement_action_metrics WHERE action_id = ?", (action_id,)).fetchone()
    return _achievement_metric_dict(metric)


@app.delete("/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric")
def delete_achievement_action_metric(assessment_id: int, action_id: int):
    with connect() as conn:
        action = conn.execute(
            "SELECT id, title FROM achievement_actions WHERE id = ? AND assessment_id = ?",
            (action_id, assessment_id),
        ).fetchone()
        if not action:
            raise HTTPException(status_code=404, detail="الإجراء التحصيلي غير موجود.")
        existing = conn.execute("SELECT 1 FROM achievement_action_metrics WHERE action_id = ?", (action_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="لا يوجد قياس أثر لهذا الإجراء.")
        conn.execute("DELETE FROM achievement_action_metrics WHERE action_id = ?", (action_id,))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"حذف قياس أثر: {action['title']}", "", "achievement_assessment", assessment_id, utc_now()),
        )
    return {"ok": True}


@app.delete("/api/achievement/assessments/{assessment_id}/actions/{action_id}")
def delete_achievement_action(assessment_id: int, action_id: int):
    with connect() as conn:
        row = conn.execute("SELECT title FROM achievement_actions WHERE id = ? AND assessment_id = ?", (action_id, assessment_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="الإجراء التحصيلي غير موجود.")
        conn.execute("DELETE FROM achievement_actions WHERE id = ?", (action_id,))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?,?,?,?,?,?)",
            ("achievement", f"حذف إجراء تحصيلي: {row['title']}", "", "achievement_assessment", assessment_id, utc_now()),
        )
    return {"ok": True}


@app.post("/api/requests", status_code=201)
def create_request(payload: CreateRequestPayload):
    with connect() as conn:
        teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود.")
        _ensure_teacher_year_links(conn, [payload.teacherId], ACADEMIC_YEAR)

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
            "INSERT INTO request_record_years (request_id, academic_year, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (request_id, ACADEMIC_YEAR, now, now),
        )
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
            result = drive.upload_file(temp_path, safe_name, mime_type, row["academic_year"] or ACADEMIC_YEAR, row["id"])
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
                row["academic_year"] or ACADEMIC_YEAR, safe_name, mime_type, total, storage_provider, storage_file_id, storage_path, web_view_link, now,
            ),
        )
        conn.execute("UPDATE upload_requests SET status = 'review', updated_at = ? WHERE id = ?", (now, row["id"]))
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("document", f"استلام {safe_name}", f"من {row['teacher_name']} للمراجعة", "document", cursor.lastrowid, now),
        )

    return {"ok": True, "documentId": cursor.lastrowid, "storageProvider": storage_provider}


@app.post("/api/documents", status_code=201)
async def upload_direct_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(default="وثيقة"),
    academicYear: str = Form(...),
    teacherId: int | None = Form(default=None),
    subject: str = Form(default=""),
    grade: str = Form(default=""),
):
    clean_title = title.strip()
    clean_category = category.strip() or "وثيقة"
    if len(clean_title) < 3 or len(clean_title) > 220:
        raise HTTPException(status_code=422, detail="عنوان الوثيقة يجب أن يكون بين 3 و220 حرفًا.")
    if len(clean_category) > 120 or len(subject.strip()) > 80 or len(grade.strip()) > 40:
        raise HTTPException(status_code=422, detail="بيانات تصنيف الوثيقة أطول من المسموح.")
    academic_year = _validate_academic_year(academicYear)
    if teacherId is not None:
        with connect() as conn:
            _validate_teacher_ids(conn, [teacherId], "المعلم المرتبط بالوثيقة غير موجود.")

    safe_name = _safe_filename(file.filename or "file")
    suffix = Path(safe_name).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="نوع الوثيقة غير مسموح به.")

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
            try:
                result = drive.upload_document_file(temp_path, safe_name, mime_type, academic_year, clean_title)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"فشل رفع الوثيقة إلى Google Drive: {exc}") from exc
            storage_provider = "google_drive"
            storage_file_id = result.get("id")
            web_view_link = result.get("webViewLink")
        else:
            document_dir = UPLOADS_DIR / "documents" / academic_year.replace("/", "-")
            document_dir.mkdir(parents=True, exist_ok=True)
            target = document_dir / f"{secrets.token_hex(4)}-{safe_name}"
            shutil.move(str(temp_path), target)
            try:
                storage_path = str(target.relative_to(BASE_DIR))
            except ValueError:
                storage_path = str(target)
    finally:
        temp_path.unlink(missing_ok=True)

    now = utc_now()
    with connect() as conn:
        if teacherId is not None:
            _ensure_teacher_year_links(conn, [teacherId], academic_year)
        cursor = conn.execute(
            """
            INSERT INTO documents
            (request_id, teacher_id, title, category, subject, grade, academic_year, original_name, mime_type, size_bytes,
             storage_provider, storage_file_id, storage_path, web_view_link, status, uploaded_at, approved_at)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?)
            """,
            (
                teacherId, clean_title, clean_category, subject.strip(), grade.strip(), academic_year,
                safe_name, mime_type, total, storage_provider, storage_file_id, storage_path, web_view_link, now, now,
            ),
        )
        document_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO activities (activity_type, title, detail, entity_type, entity_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("document", f"إضافة وثيقة: {clean_title}", clean_category, "document", document_id, now),
        )
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    return _document_dict(row)


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
