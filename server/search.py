from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import HTTPException

from .db import utc_now

SEARCH_SECTIONS = {
    "all": "الكل",
    "teachers": "المعلمون",
    "planning": "التخطيط والمنهج",
    "achievement": "التحصيل والنتائج",
    "supervision": "الإشراف والمتابعة",
    "requests": "طلبات الملفات",
    "meetings": "الاجتماعات والقرارات",
    "events": "الفعاليات والتوثيق",
    "documents": "الوثائق والمراجع",
}

SECTION_VIEW = {
    "teachers": "teachers",
    "planning": "planning",
    "achievement": "achievement",
    "supervision": "supervision",
    "requests": "requests",
    "meetings": "meetings",
    "events": "events",
    "documents": "documents",
}

ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
WHITESPACE_RE = re.compile(r"\s+")
ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})/(\d{4})$")


def normalize_arabic(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold().replace("ـ", "")
    text = ARABIC_DIACRITICS_RE.sub("", text)
    for source, target in {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ؤ": "و",
        "ئ": "ي",
        "ى": "ي",
    }.items():
        text = text.replace(source, target)
    return WHITESPACE_RE.sub(" ", text).strip()


def academic_year_from_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if month < 1 or month > 12:
        return None
    first = year if month >= 8 else year - 1
    return f"{first}/{first + 1}"


def _validate_academic_year(value: str) -> None:
    match = ACADEMIC_YEAR_RE.fullmatch(value)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        raise HTTPException(status_code=422, detail="صيغة العام الدراسي غير صحيحة. استخدم مثال 2026/2027.")


def _status_label(value: str | None) -> str:
    labels = {
        "waiting_upload": "بانتظار الرفع",
        "received": "تم الاستلام",
        "review": "للمراجعة",
        "approved": "معتمد",
        "needs_revision": "يحتاج تعديل",
        "late": "متأخر",
        "cancelled": "ملغي",
        "planned": "مخطط",
        "held": "منعقد",
        "active": "نشطة",
        "archived": "مؤرشفة",
        "not_started": "لم تبدأ",
        "in_progress": "قيد التنفيذ",
        "completed": "مكتمل",
        "needs_followup": "تحتاج متابعة",
        "closed": "مغلقة",
        "overdue": "متأخر",
        "draft": "مسودة",
        "recorded": "مسجلة",
        "reviewed": "مراجعة مكتملة",
        "new": "جديد",
    }
    return labels.get(value or "", value or "")


def _clean_excerpt(*values: object, limit: int = 170) -> str:
    text = " • ".join(str(value).strip() for value in values if value is not None and str(value).strip())
    text = WHITESPACE_RE.sub(" ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _score(query_norm: str, title: str, searchable: str) -> int:
    title_norm = normalize_arabic(title)
    text_norm = normalize_arabic(searchable)
    if not query_norm or not text_norm:
        return 0
    if title_norm == query_norm:
        return 120
    if title_norm.startswith(query_norm):
        return 108
    if query_norm in title_norm:
        return 96
    if query_norm in text_norm:
        return 78
    tokens = [token for token in query_norm.split(" ") if token]
    if not tokens:
        return 0
    title_hits = sum(token in title_norm for token in tokens)
    text_hits = sum(token in text_norm for token in tokens)
    if title_hits == len(tokens):
        return 88
    if text_hits == len(tokens):
        return 66
    required = max(2, (len(tokens) + 1) // 2) if len(tokens) > 1 else 1
    if text_hits >= required:
        return 30 + text_hits * 8
    return 0


def _result(
    *,
    query_norm: str,
    section: str,
    entity_type: str,
    entity_id: int,
    title: str,
    subtitle: str,
    searchable: str,
    excerpt: str = "",
    academic_year: str | None = None,
    date_value: str | None = None,
    status: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
    teacher_name: str | None = None,
    target_id: int | None = None,
) -> dict | None:
    score = _score(query_norm, title, searchable)
    if score <= 0:
        return None
    return {
        "key": f"{section}:{entity_type}:{entity_id}",
        "section": section,
        "sectionLabel": SEARCH_SECTIONS[section],
        "entityType": entity_type,
        "entityId": entity_id,
        "title": title,
        "subtitle": subtitle,
        "excerpt": excerpt,
        "academicYear": academic_year,
        "date": date_value,
        "status": _status_label(status),
        "subject": subject,
        "grade": grade,
        "teacherName": teacher_name,
        "targetView": SECTION_VIEW[section],
        "targetId": target_id if target_id is not None else entity_id,
        "score": score,
    }


def _add(results: list[dict], item: dict | None) -> None:
    if item is not None:
        results.append(item)


def _linked_teacher_ids_for_year(conn, academic_year: str) -> set[int]:
    linked: set[int] = set()
    for row in conn.execute("SELECT teacher_id, created_at FROM upload_requests").fetchall():
        if academic_year_from_date(row["created_at"]) == academic_year:
            linked.add(row["teacher_id"])
    for row in conn.execute("SELECT teacher_id, academic_year, uploaded_at FROM documents WHERE teacher_id IS NOT NULL").fetchall():
        year = row["academic_year"] or academic_year_from_date(row["uploaded_at"])
        if year == academic_year:
            linked.add(row["teacher_id"])
    for query in [
        "SELECT owner_teacher_id AS teacher_id FROM curriculum_plans WHERE academic_year = ? AND owner_teacher_id IS NOT NULL",
        "SELECT u.responsible_teacher_id AS teacher_id FROM curriculum_units u JOIN curriculum_plans p ON p.id = u.plan_id WHERE p.academic_year = ? AND u.responsible_teacher_id IS NOT NULL",
        "SELECT teacher_id FROM supervision_visits WHERE academic_year = ?",
        "SELECT a.responsible_teacher_id AS teacher_id FROM supervision_actions a JOIN supervision_visits v ON v.id = a.visit_id WHERE v.academic_year = ? AND a.responsible_teacher_id IS NOT NULL",
        "SELECT teacher_id FROM achievement_assessments WHERE academic_year = ? AND teacher_id IS NOT NULL",
        "SELECT a.responsible_teacher_id AS teacher_id FROM achievement_actions a JOIN achievement_assessments x ON x.id = a.assessment_id WHERE x.academic_year = ? AND a.responsible_teacher_id IS NOT NULL",
        "SELECT ma.teacher_id FROM meeting_attendees ma JOIN meetings m ON m.id = ma.meeting_id WHERE m.academic_year = ?",
        "SELECT d.responsible_teacher_id AS teacher_id FROM meeting_decisions d JOIN meetings m ON m.id = d.meeting_id WHERE m.academic_year = ? AND d.responsible_teacher_id IS NOT NULL",
    ]:
        linked.update(row["teacher_id"] for row in conn.execute(query, (academic_year,)).fetchall())
    event_rows = conn.execute(
        "SELECT l.teacher_id, e.event_date FROM event_teacher_links l JOIN events e ON e.id = l.event_id"
    ).fetchall()
    linked.update(row["teacher_id"] for row in event_rows if academic_year_from_date(row["event_date"]) == academic_year)
    return linked


def _available_years(conn) -> list[str]:
    years: set[str] = set()
    for table in ["curriculum_plans", "supervision_visits", "achievement_assessments", "meetings"]:
        years.update(
            row[0]
            for row in conn.execute(f"SELECT DISTINCT academic_year FROM {table} WHERE academic_year IS NOT NULL AND academic_year != ''").fetchall()
            if row[0]
        )
    for row in conn.execute("SELECT academic_year, uploaded_at FROM documents").fetchall():
        year = row["academic_year"] or academic_year_from_date(row["uploaded_at"])
        if year:
            years.add(year)
    for table, column in [("events", "event_date"), ("upload_requests", "created_at")]:
        for row in conn.execute(f"SELECT {column} FROM {table}").fetchall():
            year = academic_year_from_date(row[column])
            if year:
                years.add(year)
    return sorted(years, key=lambda value: int(value[:4]), reverse=True)


def _oman_today_iso() -> str:
    return datetime.now(timezone(timedelta(hours=4))).date().isoformat()


def _effective_status(base_status: str, due_date: str | None) -> str:
    if base_status not in {"completed", "cancelled", "closed"} and due_date and due_date < _oman_today_iso():
        return "overdue"
    return base_status


def run_search(conn, *, q: str, section: str = "all", academic_year: str = "all", limit: int = 40) -> dict:
    query = WHITESPACE_RE.sub(" ", (q or "").strip())[:120]
    query_norm = normalize_arabic(query)
    if section not in SEARCH_SECTIONS:
        raise HTTPException(status_code=422, detail="قسم البحث غير صالح.")
    if academic_year != "all":
        _validate_academic_year(academic_year)
    limit = max(1, min(int(limit), 100))
    available_years = _available_years(conn)
    if len(query_norm) < 2:
        return {
            "query": query,
            "normalizedQuery": query_norm,
            "section": section,
            "academicYear": academic_year,
            "generatedAt": utc_now(),
            "total": 0,
            "counts": {},
            "availableYears": available_years,
            "results": [],
        }

    results: list[dict] = []
    enabled = lambda name: section in {"all", name}

    if enabled("teachers"):
        allowed_ids = _linked_teacher_ids_for_year(conn, academic_year) if academic_year != "all" else None
        rows = conn.execute(
            """SELECT t.*, p.employee_number, p.grades, p.responsibilities, p.professional_summary,
                      COALESCE(GROUP_CONCAT(cv.title || ' ' || COALESCE(cv.organization,'') || ' ' || COALESCE(cv.description,''), ' '), '') AS cv_text
               FROM teachers t
               LEFT JOIN teacher_profiles p ON p.teacher_id = t.id
               LEFT JOIN teacher_cv_items cv ON cv.teacher_id = t.id
               GROUP BY t.id ORDER BY t.name"""
        ).fetchall()
        for row in rows:
            if allowed_ids is not None and row["id"] not in allowed_ids:
                continue
            searchable = " ".join(str(row[key] or "") for key in ["name", "subject", "specialization", "qualification", "email", "phone", "employee_number", "grades", "responsibilities", "professional_summary", "cv_text"])
            _add(results, _result(
                query_norm=query_norm, section="teachers", entity_type="teacher", entity_id=row["id"],
                title=row["name"], subtitle=_clean_excerpt(row["subject"], row["specialization"] or row["qualification"]),
                searchable=searchable, excerpt=_clean_excerpt(row["professional_summary"], row["responsibilities"], row["cv_text"]),
                academic_year=academic_year if academic_year != "all" else None, subject=row["subject"], teacher_name=row["name"],
            ))

    if enabled("planning"):
        params: tuple = (academic_year,) if academic_year != "all" else ()
        where = "WHERE p.academic_year = ?" if academic_year != "all" else ""
        rows = conn.execute(
            f"""SELECT p.*, t.name AS owner_name FROM curriculum_plans p
                LEFT JOIN teachers t ON t.id = p.owner_teacher_id {where} ORDER BY p.updated_at DESC""", params
        ).fetchall()
        for row in rows:
            searchable = " ".join(str(row[key] or "") for key in ["title", "subject", "grade", "term", "notes", "owner_name", "status"])
            _add(results, _result(
                query_norm=query_norm, section="planning", entity_type="plan", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["subject"], row["grade"], row["term"], row["owner_name"]), searchable=searchable,
                excerpt=_clean_excerpt(row["notes"]), academic_year=row["academic_year"], date_value=row["updated_at"], status=row["status"],
                subject=row["subject"], grade=row["grade"], teacher_name=row["owner_name"],
            ))
        rows = conn.execute(
            f"""SELECT u.*, p.title AS plan_title, p.subject, p.grade, p.academic_year, p.term,
                       t.name AS responsible_name
                FROM curriculum_units u JOIN curriculum_plans p ON p.id = u.plan_id
                LEFT JOIN teachers t ON t.id = u.responsible_teacher_id {where}
                ORDER BY u.updated_at DESC""", params
        ).fetchall()
        for row in rows:
            status = _effective_status(row["status"], row["planned_end"])
            searchable = " ".join(str(row[key] or "") for key in ["title", "plan_title", "subject", "grade", "term", "delay_reason", "notes", "responsible_name", "status"])
            _add(results, _result(
                query_norm=query_norm, section="planning", entity_type="curriculum_unit", entity_id=row["id"], target_id=row["plan_id"],
                title=row["title"], subtitle=_clean_excerpt("وحدة منهج", row["plan_title"], row["subject"], row["grade"]), searchable=searchable,
                excerpt=_clean_excerpt(row["delay_reason"], row["notes"]), academic_year=row["academic_year"],
                date_value=row["planned_end"] or row["planned_start"], status=status, subject=row["subject"], grade=row["grade"], teacher_name=row["responsible_name"],
            ))

    if enabled("achievement"):
        params = (academic_year,) if academic_year != "all" else ()
        where = "WHERE a.academic_year = ?" if academic_year != "all" else ""
        rows = conn.execute(
            f"""SELECT a.*, t.name AS teacher_name FROM achievement_assessments a
                LEFT JOIN teachers t ON t.id = a.teacher_id {where} ORDER BY a.assessment_date DESC""", params
        ).fetchall()
        for row in rows:
            searchable = " ".join(str(row[key] or "") for key in ["title", "assessment_type", "subject", "grade", "term", "notes", "teacher_name", "status"])
            _add(results, _result(
                query_norm=query_norm, section="achievement", entity_type="assessment", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["assessment_type"], row["subject"], row["grade"], row["teacher_name"]), searchable=searchable,
                excerpt=_clean_excerpt(row["notes"]), academic_year=row["academic_year"], date_value=row["assessment_date"], status=row["status"],
                subject=row["subject"], grade=row["grade"], teacher_name=row["teacher_name"],
            ))
        rows = conn.execute(
            f"""SELECT x.*, a.title AS assessment_title, a.subject, a.grade, a.academic_year, a.assessment_date,
                       t.name AS responsible_name, m.metric_name, m.unit, m.reference_source, m.reference_year, m.reference_note, m.notes AS metric_notes
                FROM achievement_actions x JOIN achievement_assessments a ON a.id = x.assessment_id
                LEFT JOIN teachers t ON t.id = x.responsible_teacher_id
                LEFT JOIN achievement_action_metrics m ON m.action_id = x.id {where}
                ORDER BY x.updated_at DESC""", params
        ).fetchall()
        for row in rows:
            status = _effective_status(row["status"], row["due_date"])
            searchable = " ".join(str(row[key] or "") for key in ["title", "assessment_title", "action_type", "target_group", "baseline_indicator", "target_indicator", "outcome_indicator", "notes", "responsible_name", "subject", "grade", "status", "metric_name", "unit", "reference_source", "reference_year", "reference_note", "metric_notes"])
            _add(results, _result(
                query_norm=query_norm, section="achievement", entity_type="achievement_action", entity_id=row["id"], target_id=row["assessment_id"],
                title=row["title"], subtitle=_clean_excerpt("تدخل تحصيلي", row["assessment_title"], row["target_group"], row["responsible_name"]), searchable=searchable,
                excerpt=_clean_excerpt(row["metric_name"], row["reference_source"], row["baseline_indicator"], row["target_indicator"], row["outcome_indicator"], row["notes"]),
                academic_year=row["academic_year"], date_value=row["due_date"] or row["start_date"] or row["assessment_date"], status=status,
                subject=row["subject"], grade=row["grade"], teacher_name=row["responsible_name"],
            ))

    if enabled("supervision"):
        params = (academic_year,) if academic_year != "all" else ()
        where = "WHERE v.academic_year = ?" if academic_year != "all" else ""
        rows = conn.execute(
            f"""SELECT v.*, t.name AS teacher_name, t.subject AS teacher_subject FROM supervision_visits v
                JOIN teachers t ON t.id = v.teacher_id {where} ORDER BY v.visit_date DESC""", params
        ).fetchall()
        for row in rows:
            status = "overdue" if row["status"] == "planned" and row["visit_date"] < _oman_today_iso() else row["status"]
            searchable = " ".join(str(row[key] or "") for key in ["teacher_name", "teacher_subject", "visit_type", "grade", "lesson_title", "objectives", "strengths", "development_areas", "recommendations", "followup_notes", "status"])
            title = row["lesson_title"] or f"{row['visit_type']} • {row['teacher_name']}"
            _add(results, _result(
                query_norm=query_norm, section="supervision", entity_type="visit", entity_id=row["id"], title=title,
                subtitle=_clean_excerpt(row["visit_type"], row["teacher_name"], row["teacher_subject"], row["grade"]), searchable=searchable,
                excerpt=_clean_excerpt(row["strengths"], row["development_areas"], row["recommendations"], row["followup_notes"]),
                academic_year=row["academic_year"], date_value=row["visit_date"], status=status, subject=row["teacher_subject"], grade=row["grade"], teacher_name=row["teacher_name"],
            ))
        rows = conn.execute(
            f"""SELECT a.*, v.visit_type, v.visit_date, v.lesson_title, v.grade, v.academic_year,
                       vt.name AS visited_teacher_name, vt.subject AS subject, rt.name AS responsible_name
                FROM supervision_actions a JOIN supervision_visits v ON v.id = a.visit_id
                JOIN teachers vt ON vt.id = v.teacher_id
                LEFT JOIN teachers rt ON rt.id = a.responsible_teacher_id {where}
                ORDER BY a.updated_at DESC""", params
        ).fetchall()
        for row in rows:
            status = _effective_status(row["status"], row["due_date"])
            searchable = " ".join(str(row[key] or "") for key in ["title", "visit_type", "lesson_title", "visited_teacher_name", "responsible_name", "notes", "subject", "grade", "status"])
            _add(results, _result(
                query_norm=query_norm, section="supervision", entity_type="supervision_action", entity_id=row["id"], target_id=row["visit_id"],
                title=row["title"], subtitle=_clean_excerpt("متابعة إشرافية", row["visited_teacher_name"], row["lesson_title"], row["responsible_name"]), searchable=searchable,
                excerpt=_clean_excerpt(row["notes"]), academic_year=row["academic_year"], date_value=row["due_date"] or row["visit_date"], status=status,
                subject=row["subject"], grade=row["grade"], teacher_name=row["responsible_name"] or row["visited_teacher_name"],
            ))

    if enabled("requests"):
        rows = conn.execute(
            """SELECT r.*, t.name AS teacher_name FROM upload_requests r
               JOIN teachers t ON t.id = r.teacher_id ORDER BY r.updated_at DESC"""
        ).fetchall()
        for row in rows:
            year = academic_year_from_date(row["created_at"])
            if academic_year != "all" and year != academic_year:
                continue
            status = _effective_status(row["status"], row["deadline"]) if row["status"] not in {"approved", "cancelled"} else row["status"]
            searchable = " ".join(str(row[key] or "") for key in ["title", "request_type", "teacher_name", "subject", "grade", "notes", "allowed_files", "status"])
            _add(results, _result(
                query_norm=query_norm, section="requests", entity_type="request", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["request_type"], row["teacher_name"], row["subject"], row["grade"]), searchable=searchable,
                excerpt=_clean_excerpt(row["notes"]), academic_year=year, date_value=row["deadline"] or row["created_at"], status=status,
                subject=row["subject"], grade=row["grade"], teacher_name=row["teacher_name"],
            ))

    if enabled("meetings"):
        params = (academic_year,) if academic_year != "all" else ()
        where = "WHERE m.academic_year = ?" if academic_year != "all" else ""
        rows = conn.execute(
            f"SELECT m.* FROM meetings m {where} ORDER BY m.meeting_date DESC", params
        ).fetchall()
        for row in rows:
            searchable = " ".join(str(row[key] or "") for key in ["title", "meeting_type", "location", "agenda", "discussion_summary", "notes", "status"])
            _add(results, _result(
                query_norm=query_norm, section="meetings", entity_type="meeting", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["meeting_type"], row["location"]), searchable=searchable,
                excerpt=_clean_excerpt(row["agenda"], row["discussion_summary"], row["notes"]), academic_year=row["academic_year"],
                date_value=row["meeting_date"], status=row["status"],
            ))
        rows = conn.execute(
            f"""SELECT d.*, m.title AS meeting_title, m.meeting_date, m.academic_year,
                       COALESCE(t.name, d.responsible_name) AS responsible_display
                FROM meeting_decisions d JOIN meetings m ON m.id = d.meeting_id
                LEFT JOIN teachers t ON t.id = d.responsible_teacher_id {where}
                ORDER BY d.updated_at DESC""", params
        ).fetchall()
        for row in rows:
            status = _effective_status(row["status"], row["due_date"])
            searchable = " ".join(str(row[key] or "") for key in ["title", "meeting_title", "responsible_display", "notes", "status"])
            _add(results, _result(
                query_norm=query_norm, section="meetings", entity_type="decision", entity_id=row["id"], target_id=row["meeting_id"],
                title=row["title"], subtitle=_clean_excerpt("قرار", row["meeting_title"], row["responsible_display"]), searchable=searchable,
                excerpt=_clean_excerpt(row["notes"]), academic_year=row["academic_year"], date_value=row["due_date"] or row["meeting_date"], status=status,
                teacher_name=row["responsible_display"],
            ))

    if enabled("events"):
        rows = conn.execute("SELECT e.* FROM events e ORDER BY e.event_date DESC").fetchall()
        for row in rows:
            year = academic_year_from_date(row["event_date"])
            if academic_year != "all" and year != academic_year:
                continue
            teacher_names = " ".join(
                r[0]
                for r in conn.execute(
                    "SELECT t.name FROM event_teacher_links l JOIN teachers t ON t.id = l.teacher_id WHERE l.event_id = ? ORDER BY t.name",
                    (row["id"],),
                ).fetchall()
            )
            searchable = " ".join(str(row[key] or "") for key in ["title", "event_type", "location", "audience", "goals", "summary", "outcomes", "recommendations"]) + " " + teacher_names
            _add(results, _result(
                query_norm=query_norm, section="events", entity_type="event", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["event_type"], row["audience"], row["location"]), searchable=searchable,
                excerpt=_clean_excerpt(row["goals"], row["summary"], row["outcomes"], row["recommendations"]), academic_year=year,
                date_value=row["event_date"], status="موثق",
            ))

    if enabled("documents"):
        rows = conn.execute(
            """SELECT d.*, t.name AS teacher_name FROM documents d
               LEFT JOIN teachers t ON t.id = d.teacher_id ORDER BY d.uploaded_at DESC"""
        ).fetchall()
        for row in rows:
            year = row["academic_year"] or academic_year_from_date(row["uploaded_at"])
            if academic_year != "all" and year != academic_year:
                continue
            searchable = " ".join(str(row[key] or "") for key in ["title", "category", "subject", "grade", "original_name", "status", "teacher_name"])
            _add(results, _result(
                query_norm=query_norm, section="documents", entity_type="document", entity_id=row["id"], title=row["title"],
                subtitle=_clean_excerpt(row["category"], row["teacher_name"], row["subject"], row["grade"]), searchable=searchable,
                excerpt=_clean_excerpt(row["original_name"]), academic_year=year, date_value=row["uploaded_at"], status=row["status"],
                subject=row["subject"], grade=row["grade"], teacher_name=row["teacher_name"],
            ))

    counts: dict[str, int] = {}
    for item in results:
        counts[item["section"]] = counts.get(item["section"], 0) + 1
    results.sort(key=lambda item: (-item["score"], -(int(re.sub(r"\D", "", (item.get("date") or "")[:10]) or "0")), item["title"]))
    total = len(results)
    limited = results[:limit]
    for item in limited:
        item.pop("score", None)
    return {
        "query": query,
        "normalizedQuery": query_norm,
        "section": section,
        "academicYear": academic_year,
        "generatedAt": utc_now(),
        "total": total,
        "counts": counts,
        "availableYears": available_years,
        "results": limited,
    }
