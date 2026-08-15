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

app = FastAPI(title="مرصد الإنجازات API", version="0.7.0")


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


class MeetingPayload(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    meetingType: str = Field(default="اجتماع قسم", min_length=2, max_length=80)
    meetingDate: str
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


def _oman_today_iso() -> str:
    return datetime.now(timezone(timedelta(hours=4))).date().isoformat()


def _validate_iso_date(value: str, label: str) -> str:
    try:
        parsed = datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label} غير صالح.") from exc
    return parsed.isoformat()


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


def _decision_attention(conn, limit: int = 6):
    rows = conn.execute(
        """SELECT d.*, m.title AS meeting_title
           FROM meeting_decisions d JOIN meetings m ON m.id = d.meeting_id
           WHERE d.status NOT IN ('completed','cancelled')
           ORDER BY CASE WHEN d.due_date IS NOT NULL AND d.due_date < ? THEN 0 ELSE 1 END,
                    CASE WHEN d.due_date IS NULL THEN 1 ELSE 0 END,
                    d.due_date, d.id DESC LIMIT ?""",
        (_oman_today_iso(), limit),
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


def _planning_attention(conn, limit: int = 6):
    rows = conn.execute(
        """SELECT u.*, t.name AS responsible_name, p.title AS plan_title, p.subject AS plan_subject, p.grade AS plan_grade
           FROM curriculum_units u
           JOIN curriculum_plans p ON p.id = u.plan_id
           LEFT JOIN teachers t ON t.id = u.responsible_teacher_id
           WHERE p.status = 'active' AND u.status != 'completed' AND u.progress_percent < 100
             AND u.planned_end IS NOT NULL AND u.planned_end < ?
           ORDER BY u.planned_end, u.sequence, u.id LIMIT ?""",
        (_oman_today_iso(), limit),
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


def _supervision_attention(conn, limit: int = 6):
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
           WHERE v.status != 'closed'
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
        (today, today, today, today, today, limit),
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
    return {"ok": True, "version": "0.7.0", "storageMode": os.getenv("STORAGE_MODE", "auto")}


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
        meetings = [_meeting_dict(r) for r in _meeting_summary_rows(conn)]
        decision_attention = _decision_attention(conn)
        plans = [_plan_dict(r) for r in _plan_summary_rows(conn)]
        planning_attention = _planning_attention(conn)
        visits = [_supervision_visit_dict(r) for r in _supervision_summary_rows(conn)]
        supervision_attention = _supervision_attention(conn)
        documents = [_document_dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC LIMIT 30").fetchall()]
        activities = [dict(r) for r in conn.execute("SELECT * FROM activities ORDER BY created_at DESC LIMIT 8").fetchall()]

    counts = _status_counts(request_items)
    dashboard = {
        "teacherCount": len(teachers),
        "openRequests": sum(counts.get(k, 0) for k in ["waiting_upload", "received", "review", "needs_revision", "late"]),
        "needsReview": counts.get("review", 0) + counts.get("received", 0),
        "lateRequests": counts.get("late", 0),
        "openDecisions": sum(item["openDecisionCount"] for item in meetings),
        "upcomingVisits": sum(1 for item in visits if item["status"] == "planned" and item["visitDate"] >= _oman_today_iso()),
        "planProgress": int(round(sum(item["progressPercent"] for item in plans if item["status"] == "active") / sum(1 for item in plans if item["status"] == "active"))) if any(item["status"] == "active" for item in plans) else 0,
        "visitProgress": int(round(100 * sum(1 for item in visits if item["status"] in {"completed", "needs_followup", "closed"}) / len(visits))) if visits else 0,
        "requestCompletion": 91,
    }
    return {
        "academicYear": ACADEMIC_YEAR,
        "term": "الفصل الأول",
        "dashboard": dashboard,
        "teachers": teachers,
        "requests": request_items,
        "events": events,
        "meetings": meetings,
        "decisionAttention": decision_attention,
        "plans": plans,
        "planningAttention": planning_attention,
        "visits": visits,
        "supervisionAttention": supervision_attention,
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


@app.get("/api/meetings")
def list_meetings():
    with connect() as conn:
        return [_meeting_dict(row) for row in _meeting_summary_rows(conn)]


@app.post("/api/meetings", status_code=201)
def create_meeting(payload: MeetingPayload):
    meeting_date = _validate_iso_date(payload.meetingDate, "تاريخ الاجتماع")
    meeting_time = _validate_meeting_time(payload.meetingTime)
    now = utc_now()
    with connect() as conn:
        attendee_ids = _validate_teacher_ids(conn, payload.attendeeIds, "تتضمن قائمة الحضور معلمًا غير موجود.")
        cursor = conn.execute(
            """INSERT INTO meetings
               (title, meeting_type, meeting_date, meeting_time, location, agenda, discussion_summary, notes,
                academic_year, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.title.strip(), payload.meetingType.strip(), meeting_date, meeting_time, payload.location.strip(),
                payload.agenda.strip(), payload.discussionSummary.strip(), payload.notes.strip(), ACADEMIC_YEAR,
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
    meeting_date = _validate_iso_date(payload.meetingDate, "تاريخ الاجتماع")
    meeting_time = _validate_meeting_time(payload.meetingTime)
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="الاجتماع غير موجود.")
        attendee_ids = _validate_teacher_ids(conn, payload.attendeeIds, "تتضمن قائمة الحضور معلمًا غير موجود.")
        conn.execute(
            """UPDATE meetings SET title = ?, meeting_type = ?, meeting_date = ?, meeting_time = ?, location = ?,
               agenda = ?, discussion_summary = ?, notes = ?, status = ?, updated_at = ? WHERE id = ?""",
            (
                payload.title.strip(), payload.meetingType.strip(), meeting_date, meeting_time, payload.location.strip(),
                payload.agenda.strip(), payload.discussionSummary.strip(), payload.notes.strip(), payload.status, now, meeting_id,
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
    start_date, end_date = _normalize_plan_dates(payload.startDate, payload.endDate)
    now = utc_now()
    with connect() as conn:
        if payload.ownerTeacherId is not None:
            _validate_teacher_ids(conn, [payload.ownerTeacherId], "المعلم المسؤول عن الخطة غير موجود.")
        cursor = conn.execute(
            """INSERT INTO curriculum_plans
               (title, subject, grade, term, academic_year, owner_teacher_id, start_date, end_date, notes, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.title, payload.subject, payload.grade, payload.term, ACADEMIC_YEAR, payload.ownerTeacherId, start_date, end_date, payload.notes, payload.status, now, now),
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
    start_date, end_date = _normalize_plan_dates(payload.startDate, payload.endDate)
    now = utc_now()
    with connect() as conn:
        if not conn.execute("SELECT id FROM curriculum_plans WHERE id = ?", (plan_id,)).fetchone():
            raise HTTPException(status_code=404, detail="الخطة غير موجودة.")
        if payload.ownerTeacherId is not None:
            _validate_teacher_ids(conn, [payload.ownerTeacherId], "المعلم المسؤول عن الخطة غير موجود.")
        conn.execute(
            """UPDATE curriculum_plans SET title=?, subject=?, grade=?, term=?, owner_teacher_id=?, start_date=?, end_date=?, notes=?, status=?, updated_at=? WHERE id=?""",
            (payload.title, payload.subject, payload.grade, payload.term, payload.ownerTeacherId, start_date, end_date, payload.notes, payload.status, now, plan_id),
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
        plan = conn.execute("SELECT id, title FROM curriculum_plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="الخطة غير موجودة.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المعلم المسؤول عن الوحدة غير موجود.")
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
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المعلم المسؤول عن الوحدة غير موجود.")
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
    visit_date, followup_date = _normalize_supervision_visit(payload)
    now = utc_now()
    with connect() as conn:
        _validate_teacher_ids(conn, [payload.teacherId], "المعلم المحدد للزيارة غير موجود.")
        teacher = conn.execute("SELECT name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        closed_at = now if payload.status == "closed" else None
        cursor = conn.execute(
            """INSERT INTO supervision_visits
               (teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations,
                followup_date, followup_notes, academic_year, status, closed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.teacherId, payload.visitType.strip(), visit_date, payload.periodLabel.strip(), payload.grade.strip(), payload.lessonTitle.strip(),
             payload.objectives.strip(), payload.strengths.strip(), payload.developmentAreas.strip(), payload.recommendations.strip(),
             followup_date, payload.followupNotes.strip(), ACADEMIC_YEAR, payload.status, closed_at, now, now),
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
    visit_date, followup_date = _normalize_supervision_visit(payload)
    now = utc_now()
    with connect() as conn:
        current = conn.execute("SELECT * FROM supervision_visits WHERE id = ?", (visit_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="الزيارة غير موجودة.")
        _validate_teacher_ids(conn, [payload.teacherId], "المعلم المحدد للزيارة غير موجود.")
        teacher = conn.execute("SELECT name FROM teachers WHERE id = ?", (payload.teacherId,)).fetchone()
        closed_at = current["closed_at"]
        if payload.status == "closed" and not closed_at:
            closed_at = now
        elif payload.status != "closed":
            closed_at = None
        conn.execute(
            """UPDATE supervision_visits SET teacher_id=?, visit_type=?, visit_date=?, period_label=?, grade=?, lesson_title=?, objectives=?, strengths=?,
               development_areas=?, recommendations=?, followup_date=?, followup_notes=?, status=?, closed_at=?, updated_at=? WHERE id=?""",
            (payload.teacherId, payload.visitType.strip(), visit_date, payload.periodLabel.strip(), payload.grade.strip(), payload.lessonTitle.strip(),
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
        visit = conn.execute("SELECT id FROM supervision_visits WHERE id = ?", (visit_id,)).fetchone()
        if not visit:
            raise HTTPException(status_code=404, detail="الزيارة غير موجودة.")
        if payload.responsibleTeacherId is not None:
            _validate_teacher_ids(conn, [payload.responsibleTeacherId], "المسؤول عن الإجراء غير موجود.")
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
        meeting = conn.execute("SELECT id, title FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            raise HTTPException(status_code=404, detail="الاجتماع غير موجود.")
        responsible_name = payload.responsibleName.strip()
        if payload.responsibleTeacherId is not None:
            teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.responsibleTeacherId,)).fetchone()
            if not teacher:
                raise HTTPException(status_code=422, detail="المسؤول المحدد غير موجود ضمن المعلمين.")
            if not responsible_name:
                responsible_name = teacher["name"]
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
        responsible_name = payload.responsibleName.strip()
        if payload.responsibleTeacherId is not None:
            teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (payload.responsibleTeacherId,)).fetchone()
            if not teacher:
                raise HTTPException(status_code=422, detail="المسؤول المحدد غير موجود ضمن المعلمين.")
            if not responsible_name:
                responsible_name = teacher["name"]
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
