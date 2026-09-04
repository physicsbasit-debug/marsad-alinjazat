from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

COMPILER_VERSION = "1.0.0"
ID_BASE = 7_000_000_000_000_000_000
ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})/(\d{4})$")
SOURCE_TABLES = [
    "settings", "teachers", "teacher_profiles", "teacher_cv_items", "teacher_record_years",
    "upload_requests", "request_record_years", "documents", "events", "event_record_years",
    "event_media", "event_media_meta", "event_teacher_links", "activities", "meetings",
    "meeting_attendees", "meeting_decisions", "curriculum_plans", "curriculum_units",
    "supervision_visits", "supervision_actions", "achievement_assessments",
    "achievement_assessment_standards", "achievement_actions", "achievement_action_metrics",
]
TARGET_TABLES = [
    "schools", "profiles", "school_memberships", "academic_years", "school_settings", "teachers",
    "teacher_profiles", "teacher_years", "teacher_cv_items", "upload_requests", "documents", "events",
    "event_media", "event_teacher_links", "activities", "meetings", "meeting_attendees",
    "meeting_decisions", "curriculum_plans", "curriculum_units", "supervision_visits",
    "supervision_actions", "achievement_assessments", "achievement_assessment_standards",
    "achievement_actions", "achievement_action_metrics",
]
SECRET_SETTING_PATTERNS = (
    "refresh_token", "oauth_state", "client_secret", "service_role", "service-role", "password",
    "encryption_key", "secret_key", "access_token",
)
STORAGE_PROVIDER_MAP = {
    "local": "legacy_local",
    "legacy_local": "legacy_local",
    "google_drive": "google_drive",
    "supabase": "supabase",
}
ACTIVITY_ENTITY_TABLE = {
    "event": "events",
    "meeting": "meetings",
    "curriculum_plan": "curriculum_plans",
    "supervision_visit": "supervision_visits",
    "achievement_assessment": "achievement_assessments",
    "request": "upload_requests",
    "document": "documents",
    "teacher": "teachers",
    "teacher_cv_item": "teacher_cv_items",
}
YEAR_SCOPED_ACTIVITY_ENTITY = {
    "event", "meeting", "curriculum_plan", "supervision_visit", "achievement_assessment", "request", "document"
}


class CompileError(RuntimeError):
    pass


@dataclass
class Audit:
    source_rows: int = 0
    accepted_rows: int = 0
    excluded_rows: int = 0
    rejected_rows: int = 0
    exclusion_reason_counts: Counter[str] | None = None
    rejection_reason_counts: Counter[str] | None = None

    def __post_init__(self) -> None:
        self.exclusion_reason_counts = Counter()
        self.rejection_reason_counts = Counter()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_rows": self.source_rows,
            "accepted_rows": self.accepted_rows,
            "excluded_rows": self.excluded_rows,
            "rejected_rows": self.rejected_rows,
            "exclusion_reason_counts": dict(sorted(self.exclusion_reason_counts.items())),
            "rejection_reason_counts": dict(sorted(self.rejection_reason_counts.items())),
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_academic_year(value: str) -> tuple[int, int]:
    match = ACADEMIC_YEAR_RE.fullmatch(value.strip())
    if not match:
        raise CompileError(f"invalid academic year label: {value!r}")
    start, end = int(match.group(1)), int(match.group(2))
    if end != start + 1:
        raise CompileError(f"academic year must be consecutive: {value!r}")
    return start, end


def academic_year_from_date(value: str | None) -> str:
    if not value:
        raise CompileError("cannot infer academic year from empty date")
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        year, month = parsed.year, parsed.month
    except ValueError:
        try:
            parsed_d = date.fromisoformat(raw[:10])
            year, month = parsed_d.year, parsed_d.month
        except ValueError as exc:
            raise CompileError(f"cannot infer academic year from date {value!r}") from exc
    first = year if month >= 8 else year - 1
    return f"{first}/{first + 1}"


def mapped_id(value: Any) -> int | None:
    if value is None:
        return None
    return ID_BASE + int(value)


def sql_literal(value: Any, *, jsonb: bool = False) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if jsonb:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return "'" + encoded.replace("'", "''") + "'::jsonb"
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def normalize_provider(provider: str | None) -> str:
    key = (provider or "").strip().lower()
    if key not in STORAGE_PROVIDER_MAP:
        raise CompileError(f"unsupported storage_provider: {provider!r}")
    return STORAGE_PROVIDER_MAP[key]


def normalized_storage_path(row: dict[str, Any]) -> tuple[str | None, bool]:
    path = (row.get("storage_path") or "").strip()
    if path:
        return path, False
    file_id = (row.get("storage_file_id") or "").strip()
    if file_id:
        return file_id, True
    return None, False


def read_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"').fetchall()]


def insert_sql(table: str, columns: list[str], rows: list[dict[str, Any]], *, jsonb_columns: set[str] | None = None) -> str:
    if not rows:
        return f"-- {table}: 0 rows\n"
    jsonb_columns = jsonb_columns or set()
    lines = [f"-- {table}: {len(rows)} rows"]
    for row in rows:
        values = ", ".join(sql_literal(row.get(c), jsonb=c in jsonb_columns) for c in columns)
        lines.append(f"insert into public.{table} ({', '.join(columns)}) values ({values});")
    return "\n".join(lines) + "\n"


def ensure_unique_nonblank(rows: Iterable[dict[str, Any]], field: str, label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        if value in seen:
            raise CompileError(f"duplicate {label}: {value!r}")
        seen.add(value)


def resolve_year_map(
    tables: dict[str, list[dict[str, Any]]], current_year: str
) -> tuple[dict[str, int], dict[str, dict[int, str]], dict[str, int]]:
    validate_academic_year(current_year)
    years: set[str] = {current_year}
    inferred = Counter()

    request_explicit = {int(r["request_id"]): str(r["academic_year"]).strip() for r in tables["request_record_years"]}
    event_explicit = {int(r["event_id"]): str(r["academic_year"]).strip() for r in tables["event_record_years"]}
    for year in list(request_explicit.values()) + list(event_explicit.values()):
        validate_academic_year(year)
        years.add(year)

    request_year: dict[int, str] = {}
    for row in tables["upload_requests"]:
        rid = int(row["id"])
        year = request_explicit.get(rid)
        if not year:
            year = academic_year_from_date(row.get("created_at"))
            inferred["upload_requests"] += 1
        validate_academic_year(year)
        request_year[rid] = year
        years.add(year)

    event_year: dict[int, str] = {}
    for row in tables["events"]:
        eid = int(row["id"])
        year = event_explicit.get(eid)
        if not year:
            year = academic_year_from_date(row.get("event_date"))
            inferred["events"] += 1
        validate_academic_year(year)
        event_year[eid] = year
        years.add(year)

    document_year: dict[int, str] = {}
    for row in tables["documents"]:
        did = int(row["id"])
        explicit = str(row.get("academic_year") or "").strip()
        year = explicit or academic_year_from_date(row.get("uploaded_at"))
        if not explicit:
            inferred["documents"] += 1
        validate_academic_year(year)
        document_year[did] = year
        years.add(year)

    direct_tables = ("meetings", "curriculum_plans", "supervision_visits", "achievement_assessments")
    direct_maps: dict[str, dict[int, str]] = {}
    for table in direct_tables:
        mapping: dict[int, str] = {}
        for row in tables[table]:
            year = str(row.get("academic_year") or "").strip()
            validate_academic_year(year)
            mapping[int(row["id"])] = year
            years.add(year)
        direct_maps[table] = mapping

    for row in tables["teacher_record_years"]:
        year = str(row.get("academic_year") or "").strip()
        validate_academic_year(year)
        years.add(year)

    ordered = sorted(years, key=lambda y: validate_academic_year(y)[0])
    year_id = {year: ID_BASE + 100_000 + i for i, year in enumerate(ordered, 1)}
    maps = {
        "upload_requests": request_year,
        "events": event_year,
        "documents": document_year,
        **direct_maps,
    }
    return year_id, maps, dict(inferred)


def build_teacher_year_pairs(
    tables: dict[str, list[dict[str, Any]]], year_maps: dict[str, dict[int, str]], current_year: str
) -> dict[tuple[int, str], dict[str, Any]]:
    teachers = {int(r["id"]): r for r in tables["teachers"]}
    profiles = {int(r["teacher_id"]): r for r in tables["teacher_profiles"]}
    pairs: dict[tuple[int, str], dict[str, Any]] = {}

    def add(tid: int | None, year: str | None, source_created: str | None = None, source_updated: str | None = None) -> None:
        if tid is None or not year:
            return
        tid = int(tid)
        if tid not in teachers:
            raise CompileError(f"teacher_year reference points to missing teacher {tid}")
        validate_academic_year(year)
        key = (tid, year)
        if key in pairs:
            return
        teacher = teachers[tid]
        profile = profiles.get(tid, {})
        is_current = year == current_year
        pairs[key] = {
            "teacher_id": mapped_id(tid),
            "year": year,
            "subject": teacher.get("subject") if is_current else None,
            "experience_years": teacher.get("experience_years") if is_current else None,
            "workload": teacher.get("workload") if is_current else None,
            "grades": profile.get("grades") if is_current else None,
            "responsibilities": profile.get("responsibilities") if is_current else None,
            "is_active": True,
            "created_at": source_created or teacher.get("created_at"),
            "updated_at": source_updated or teacher.get("updated_at"),
        }

    for tid, teacher in teachers.items():
        add(tid, current_year, teacher.get("created_at"), teacher.get("updated_at"))

    for row in tables["teacher_record_years"]:
        add(row.get("teacher_id"), str(row.get("academic_year") or "").strip(), row.get("created_at"), row.get("updated_at"))

    for row in tables["upload_requests"]:
        add(row.get("teacher_id"), year_maps["upload_requests"][int(row["id"])], row.get("created_at"), row.get("updated_at"))
    for row in tables["documents"]:
        add(row.get("teacher_id"), year_maps["documents"][int(row["id"])], row.get("uploaded_at"), row.get("approved_at") or row.get("uploaded_at"))

    plan_year = year_maps["curriculum_plans"]
    plan_by_id = {int(r["id"]): r for r in tables["curriculum_plans"]}
    for row in tables["curriculum_plans"]:
        add(row.get("owner_teacher_id"), plan_year[int(row["id"])], row.get("created_at"), row.get("updated_at"))
    for row in tables["curriculum_units"]:
        plan_id = int(row["plan_id"])
        add(row.get("responsible_teacher_id"), plan_year[plan_id], row.get("created_at"), row.get("updated_at"))

    visit_year = year_maps["supervision_visits"]
    visit_by_id = {int(r["id"]): r for r in tables["supervision_visits"]}
    for row in tables["supervision_visits"]:
        add(row.get("teacher_id"), visit_year[int(row["id"])], row.get("created_at"), row.get("updated_at"))
    for row in tables["supervision_actions"]:
        visit_id = int(row["visit_id"])
        add(row.get("responsible_teacher_id"), visit_year[visit_id], row.get("created_at"), row.get("updated_at"))

    assessment_year = year_maps["achievement_assessments"]
    for row in tables["achievement_assessments"]:
        add(row.get("teacher_id"), assessment_year[int(row["id"])], row.get("created_at"), row.get("updated_at"))
    for row in tables["achievement_actions"]:
        aid = int(row["assessment_id"])
        add(row.get("responsible_teacher_id"), assessment_year[aid], row.get("created_at"), row.get("updated_at"))

    meeting_year = year_maps["meetings"]
    for row in tables["meeting_attendees"]:
        add(row.get("teacher_id"), meeting_year[int(row["meeting_id"])], row.get("created_at"), row.get("created_at"))
    for row in tables["meeting_decisions"]:
        add(row.get("responsible_teacher_id"), meeting_year[int(row["meeting_id"])], row.get("created_at"), row.get("updated_at"))

    event_year = year_maps["events"]
    for row in tables["event_teacher_links"]:
        add(row.get("teacher_id"), event_year[int(row["event_id"])], row.get("created_at"), row.get("created_at"))

    return pairs


def compile_database(source: Path, output_dir: Path, school_name: str, current_year: str) -> dict[str, Any]:
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha = sha256_file(source)
    school_id = uuid.uuid5(uuid.NAMESPACE_URL, f"marsad-s2e1:{source_sha}:{school_name}")

    conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise CompileError(f"SQLite integrity_check failed: {integrity}")
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_rows:
            raise CompileError(f"SQLite foreign_key_check returned {len(fk_rows)} violation(s)")
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in SOURCE_TABLES if t not in existing]
        if missing:
            raise CompileError(f"missing legacy source tables: {', '.join(missing)}")
        tables = {t: read_rows(conn, t) for t in SOURCE_TABLES}
    finally:
        conn.close()

    audits = {t: Audit(source_rows=len(rows), accepted_rows=len(rows)) for t, rows in tables.items()}

    # Security boundary for legacy settings: preserve configuration, exclude secret material with an explicit audit reason.
    accepted_settings: list[dict[str, Any]] = []
    for row in tables["settings"]:
        key = str(row.get("key") or "")
        lowered = key.lower()
        if any(pattern in lowered for pattern in SECRET_SETTING_PATTERNS):
            audits["settings"].accepted_rows -= 1
            audits["settings"].excluded_rows += 1
            audits["settings"].exclusion_reason_counts["security_boundary_secret_setting"] += 1
        else:
            accepted_settings.append(row)

    ensure_unique_nonblank(tables["teacher_profiles"], "employee_number", "teacher employee_number")

    year_ids, year_maps, inferred_year_counts = resolve_year_map(tables, current_year)
    teacher_year_pairs = build_teacher_year_pairs(tables, year_maps, current_year)

    # Folded-link reconciliation.
    request_ids = {int(r["id"]) for r in tables["upload_requests"]}
    event_ids = {int(r["id"]) for r in tables["events"]}
    teacher_ids = {int(r["id"]) for r in tables["teachers"]}
    media_ids = {int(r["id"]) for r in tables["event_media"]}
    folded = {
        "request_record_years": {
            "source_links": len(tables["request_record_years"]),
            "matched_links": sum(1 for r in tables["request_record_years"] if int(r["request_id"]) in request_ids),
        },
        "event_record_years": {
            "source_links": len(tables["event_record_years"]),
            "matched_links": sum(1 for r in tables["event_record_years"] if int(r["event_id"]) in event_ids),
        },
        "teacher_record_years": {
            "source_links": len(tables["teacher_record_years"]),
            "matched_links": sum(1 for r in tables["teacher_record_years"] if int(r["teacher_id"]) in teacher_ids),
        },
        "event_media_meta": {
            "source_links": len(tables["event_media_meta"]),
            "matched_links": sum(1 for r in tables["event_media_meta"] if int(r["media_id"]) in media_ids),
        },
    }
    for item in folded.values():
        item["unmatched_links"] = item["source_links"] - item["matched_links"]
        if item["unmatched_links"]:
            raise CompileError("folded legacy relation has unmatched links despite foreign_key_check")

    year_id = lambda year: year_ids[year]
    sid = str(school_id)

    target: dict[str, list[dict[str, Any]]] = {t: [] for t in TARGET_TABLES}
    target["schools"].append({"id": sid, "name": school_name, "is_active": True})
    for label, yid in year_ids.items():
        start, end = validate_academic_year(label)
        target["academic_years"].append({
            "id": yid, "school_id": sid, "label": label, "start_year": start, "end_year": end,
            "is_current": label == current_year,
        })
    for row in accepted_settings:
        target["school_settings"].append({
            "school_id": sid, "key": row["key"], "value": row["value"], "updated_at": row["updated_at"], "updated_by": None,
        })

    for row in tables["teachers"]:
        target["teachers"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "name": row["name"],
            "specialization": row.get("specialization"), "qualification": row.get("qualification"),
            "email": row.get("email"), "phone": row.get("phone"), "is_active": True,
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["teacher_profiles"]:
        target["teacher_profiles"].append({
            "teacher_id": mapped_id(row["teacher_id"]), "school_id": sid,
            "employee_number": row.get("employee_number"), "school_join_year": row.get("school_join_year"),
            "professional_summary": row.get("professional_summary"), "updated_at": row["updated_at"],
        })
    for (_, year), row in sorted(teacher_year_pairs.items()):
        target["teacher_years"].append({
            "school_id": sid, "academic_year_id": year_id(year), "teacher_id": row["teacher_id"],
            "subject": row["subject"], "experience_years": row["experience_years"], "workload": row["workload"],
            "grades": row["grades"], "responsibilities": row["responsibilities"], "is_active": row["is_active"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["teacher_cv_items"]:
        target["teacher_cv_items"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "teacher_id": mapped_id(row["teacher_id"]),
            "item_type": row["item_type"], "title": row["title"], "organization": row.get("organization"),
            "start_year": row.get("start_year"), "end_year": row.get("end_year"), "description": row.get("description"),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    for row in tables["upload_requests"]:
        target["upload_requests"].append({
            "id": mapped_id(row["id"]), "school_id": sid,
            "academic_year_id": year_id(year_maps["upload_requests"][int(row["id"])]),
            "teacher_id": mapped_id(row["teacher_id"]), "request_type": row["request_type"],
            "subject": row["subject"], "grade": row["grade"], "title": row["title"], "deadline": row.get("deadline"),
            "notes": row.get("notes"), "allowed_files": row["allowed_files"], "token_hash": row["token_hash"],
            "status": row["status"], "expires_at": row["expires_at"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    storage_file_id_folded = 0
    for row in tables["documents"]:
        provider = normalize_provider(row.get("storage_provider"))
        storage_path, folded_file_id = normalized_storage_path(row)
        storage_file_id_folded += int(folded_file_id)
        target["documents"].append({
            "id": mapped_id(row["id"]), "school_id": sid,
            "academic_year_id": year_id(year_maps["documents"][int(row["id"])]),
            "request_id": mapped_id(row.get("request_id")), "teacher_id": mapped_id(row.get("teacher_id")),
            "title": row["title"], "category": row["category"], "subject": row.get("subject"), "grade": row.get("grade"),
            "original_name": row["original_name"], "mime_type": row.get("mime_type"), "size_bytes": row["size_bytes"],
            "storage_provider": provider, "storage_bucket": None, "storage_path": storage_path,
            "external_url": row.get("web_view_link"), "status": row["status"], "uploaded_at": row["uploaded_at"],
            "approved_at": row.get("approved_at"),
        })

    for row in tables["events"]:
        target["events"].append({
            "id": mapped_id(row["id"]), "school_id": sid,
            "academic_year_id": year_id(year_maps["events"][int(row["id"])]), "title": row["title"],
            "event_type": row["event_type"], "event_date": row["event_date"], "location": row.get("location"),
            "audience": row.get("audience"), "participant_count": row["participant_count"], "goals": row.get("goals"),
            "summary": row.get("summary"), "outcomes": row.get("outcomes"), "recommendations": row.get("recommendations"),
            "cover_tone": row["cover_tone"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    meta_by_media = {int(r["media_id"]): r for r in tables["event_media_meta"]}
    covers = Counter()
    for row in tables["event_media"]:
        provider = normalize_provider(row.get("storage_provider"))
        storage_path, folded_file_id = normalized_storage_path(row)
        storage_file_id_folded += int(folded_file_id)
        meta = meta_by_media.get(int(row["id"]), {})
        is_cover = bool(meta.get("is_cover", 0))
        if is_cover:
            covers[int(row["event_id"])] += 1
        target["event_media"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "event_id": mapped_id(row["event_id"]),
            "original_name": row["original_name"], "mime_type": row.get("mime_type"), "size_bytes": row["size_bytes"],
            "storage_provider": provider, "storage_bucket": None, "storage_path": storage_path,
            "external_url": row.get("web_view_link"), "caption": meta.get("caption", ""), "position": meta.get("position", 0),
            "is_cover": is_cover, "created_at": row["created_at"], "updated_at": meta.get("updated_at") or row["created_at"],
        })
    bad_covers = [event_id for event_id, count in covers.items() if count > 1]
    if bad_covers:
        raise CompileError(f"multiple cover media rows for legacy event(s): {bad_covers}")

    for row in tables["event_teacher_links"]:
        target["event_teacher_links"].append({
            "school_id": sid, "event_id": mapped_id(row["event_id"]), "teacher_id": mapped_id(row["teacher_id"]),
            "role": row["role"], "created_at": row["created_at"],
        })

    entity_year_lookup: dict[tuple[str, int], str] = {}
    for entity_type, table in ACTIVITY_ENTITY_TABLE.items():
        if entity_type not in YEAR_SCOPED_ACTIVITY_ENTITY:
            continue
        if table in year_maps:
            for entity_id, year in year_maps[table].items():
                entity_year_lookup[(entity_type, entity_id)] = year
    for row in tables["activities"]:
        entity_type = row.get("entity_type")
        entity_id = row.get("entity_id")
        mapped_entity = entity_id
        if entity_type in ACTIVITY_ENTITY_TABLE and entity_id is not None:
            mapped_entity = mapped_id(entity_id)
        year = entity_year_lookup.get((str(entity_type), int(entity_id))) if entity_id is not None else None
        target["activities"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "academic_year_id": year_id(year) if year else None,
            "actor_user_id": None, "activity_type": row["activity_type"], "title": row["title"], "detail": row.get("detail"),
            "entity_type": entity_type, "entity_id": mapped_entity, "created_at": row["created_at"],
        })

    for row in tables["meetings"]:
        target["meetings"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "academic_year_id": year_id(year_maps["meetings"][int(row["id"])]),
            "title": row["title"], "meeting_type": row["meeting_type"], "meeting_date": row["meeting_date"],
            "meeting_time": row.get("meeting_time"), "location": row.get("location"), "agenda": row.get("agenda"),
            "discussion_summary": row.get("discussion_summary"), "notes": row.get("notes"), "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["meeting_attendees"]:
        target["meeting_attendees"].append({
            "school_id": sid, "meeting_id": mapped_id(row["meeting_id"]), "teacher_id": mapped_id(row["teacher_id"]),
            "attendance_status": row["attendance_status"], "created_at": row["created_at"],
        })
    for row in tables["meeting_decisions"]:
        target["meeting_decisions"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "meeting_id": mapped_id(row["meeting_id"]),
            "title": row["title"], "responsible_teacher_id": mapped_id(row.get("responsible_teacher_id")),
            "responsible_name": row.get("responsible_name"), "due_date": row.get("due_date"), "status": row["status"],
            "notes": row.get("notes"), "completed_at": row.get("completed_at"), "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    for row in tables["curriculum_plans"]:
        target["curriculum_plans"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "academic_year_id": year_id(year_maps["curriculum_plans"][int(row["id"])]),
            "title": row["title"], "subject": row["subject"], "grade": row["grade"], "term": row["term"],
            "owner_teacher_id": mapped_id(row.get("owner_teacher_id")), "start_date": row.get("start_date"), "end_date": row.get("end_date"),
            "notes": row.get("notes"), "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["curriculum_units"]:
        target["curriculum_units"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "plan_id": mapped_id(row["plan_id"]), "title": row["title"],
            "sequence": row["sequence"], "planned_start": row.get("planned_start"), "planned_end": row.get("planned_end"),
            "progress_percent": row["progress_percent"], "status": row["status"], "delay_reason": row.get("delay_reason"),
            "notes": row.get("notes"), "responsible_teacher_id": mapped_id(row.get("responsible_teacher_id")),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    for row in tables["supervision_visits"]:
        target["supervision_visits"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "academic_year_id": year_id(year_maps["supervision_visits"][int(row["id"])]),
            "teacher_id": mapped_id(row["teacher_id"]), "visit_type": row["visit_type"], "visit_date": row["visit_date"],
            "period_label": row.get("period_label"), "grade": row.get("grade"), "lesson_title": row.get("lesson_title"),
            "objectives": row.get("objectives"), "strengths": row.get("strengths"), "development_areas": row.get("development_areas"),
            "recommendations": row.get("recommendations"), "followup_date": row.get("followup_date"), "followup_notes": row.get("followup_notes"),
            "status": row["status"], "closed_at": row.get("closed_at"), "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["supervision_actions"]:
        target["supervision_actions"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "visit_id": mapped_id(row["visit_id"]), "title": row["title"],
            "responsible_teacher_id": mapped_id(row.get("responsible_teacher_id")), "due_date": row.get("due_date"), "status": row["status"],
            "notes": row.get("notes"), "completed_at": row.get("completed_at"), "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    for row in tables["achievement_assessments"]:
        target["achievement_assessments"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "academic_year_id": year_id(year_maps["achievement_assessments"][int(row["id"])]),
            "title": row["title"], "assessment_type": row["assessment_type"], "subject": row["subject"], "grade": row["grade"],
            "assessment_date": row["assessment_date"], "term": row["term"], "teacher_id": mapped_id(row.get("teacher_id")),
            "max_score": row["max_score"], "student_count": row["student_count"], "average_score": row.get("average_score"),
            "highest_score": row.get("highest_score"), "lowest_score": row.get("lowest_score"), "mastery_threshold_pct": row["mastery_threshold_pct"],
            "mastered_count": row["mastered_count"], "near_mastery_count": row["near_mastery_count"], "intervention_count": row["intervention_count"],
            "notes": row.get("notes"), "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["achievement_assessment_standards"]:
        target["achievement_assessment_standards"].append({
            "assessment_id": mapped_id(row["assessment_id"]), "school_id": sid,
            "mastery_reference_source": row["mastery_reference_source"], "mastery_reference_year": row.get("mastery_reference_year"),
            "mastery_reference_note": row.get("mastery_reference_note"), "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["achievement_actions"]:
        target["achievement_actions"].append({
            "id": mapped_id(row["id"]), "school_id": sid, "assessment_id": mapped_id(row["assessment_id"]),
            "action_type": row["action_type"], "title": row["title"], "target_group": row.get("target_group"),
            "responsible_teacher_id": mapped_id(row.get("responsible_teacher_id")), "start_date": row.get("start_date"), "due_date": row.get("due_date"),
            "status": row["status"], "baseline_indicator": row.get("baseline_indicator"), "target_indicator": row.get("target_indicator"),
            "outcome_indicator": row.get("outcome_indicator"), "notes": row.get("notes"), "completed_at": row.get("completed_at"),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })
    for row in tables["achievement_action_metrics"]:
        target["achievement_action_metrics"].append({
            "action_id": mapped_id(row["action_id"]), "school_id": sid, "metric_name": row["metric_name"], "unit": row["unit"],
            "direction": row["direction"], "baseline_value": row["baseline_value"], "target_value": row["target_value"],
            "outcome_value": row.get("outcome_value"), "measured_at": row.get("measured_at"), "reference_source": row.get("reference_source"),
            "reference_year": row.get("reference_year"), "reference_note": row.get("reference_note"), "notes": row.get("notes"),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    # SQL generation. Every row is rolled back; no production data is committed.
    sections: list[str] = [
        "-- Marsad Al-Injazat S2-E1 SQLite -> Supabase controlled dry run",
        f"-- compiler_version={COMPILER_VERSION}",
        f"-- source_sha256={source_sha}",
        f"-- dry_run_school_id={sid}",
        f"-- current_academic_year={current_year}",
        "-- IMPORTANT: this script ends with ROLLBACK and must never be edited to COMMIT.",
        "begin;",
        "",
    ]
    column_order: dict[str, list[str]] = {
        "schools": ["id", "name", "is_active"],
        "academic_years": ["id", "school_id", "label", "start_year", "end_year", "is_current"],
        "school_settings": ["school_id", "key", "value", "updated_at", "updated_by"],
        "teachers": ["id", "school_id", "name", "specialization", "qualification", "email", "phone", "is_active", "created_at", "updated_at"],
        "teacher_profiles": ["teacher_id", "school_id", "employee_number", "school_join_year", "professional_summary", "updated_at"],
        "teacher_years": ["school_id", "academic_year_id", "teacher_id", "subject", "experience_years", "workload", "grades", "responsibilities", "is_active", "created_at", "updated_at"],
        "teacher_cv_items": ["id", "school_id", "teacher_id", "item_type", "title", "organization", "start_year", "end_year", "description", "created_at", "updated_at"],
        "upload_requests": ["id", "school_id", "academic_year_id", "teacher_id", "request_type", "subject", "grade", "title", "deadline", "notes", "allowed_files", "token_hash", "status", "expires_at", "created_at", "updated_at"],
        "documents": ["id", "school_id", "academic_year_id", "request_id", "teacher_id", "title", "category", "subject", "grade", "original_name", "mime_type", "size_bytes", "storage_provider", "storage_bucket", "storage_path", "external_url", "status", "uploaded_at", "approved_at"],
        "events": ["id", "school_id", "academic_year_id", "title", "event_type", "event_date", "location", "audience", "participant_count", "goals", "summary", "outcomes", "recommendations", "cover_tone", "created_at", "updated_at"],
        "event_media": ["id", "school_id", "event_id", "original_name", "mime_type", "size_bytes", "storage_provider", "storage_bucket", "storage_path", "external_url", "caption", "position", "is_cover", "created_at", "updated_at"],
        "event_teacher_links": ["school_id", "event_id", "teacher_id", "role", "created_at"],
        "activities": ["id", "school_id", "academic_year_id", "actor_user_id", "activity_type", "title", "detail", "entity_type", "entity_id", "created_at"],
        "meetings": ["id", "school_id", "academic_year_id", "title", "meeting_type", "meeting_date", "meeting_time", "location", "agenda", "discussion_summary", "notes", "status", "created_at", "updated_at"],
        "meeting_attendees": ["school_id", "meeting_id", "teacher_id", "attendance_status", "created_at"],
        "meeting_decisions": ["id", "school_id", "meeting_id", "title", "responsible_teacher_id", "responsible_name", "due_date", "status", "notes", "completed_at", "created_at", "updated_at"],
        "curriculum_plans": ["id", "school_id", "academic_year_id", "title", "subject", "grade", "term", "owner_teacher_id", "start_date", "end_date", "notes", "status", "created_at", "updated_at"],
        "curriculum_units": ["id", "school_id", "plan_id", "title", "sequence", "planned_start", "planned_end", "progress_percent", "status", "delay_reason", "notes", "responsible_teacher_id", "created_at", "updated_at"],
        "supervision_visits": ["id", "school_id", "academic_year_id", "teacher_id", "visit_type", "visit_date", "period_label", "grade", "lesson_title", "objectives", "strengths", "development_areas", "recommendations", "followup_date", "followup_notes", "status", "closed_at", "created_at", "updated_at"],
        "supervision_actions": ["id", "school_id", "visit_id", "title", "responsible_teacher_id", "due_date", "status", "notes", "completed_at", "created_at", "updated_at"],
        "achievement_assessments": ["id", "school_id", "academic_year_id", "title", "assessment_type", "subject", "grade", "assessment_date", "term", "teacher_id", "max_score", "student_count", "average_score", "highest_score", "lowest_score", "mastery_threshold_pct", "mastered_count", "near_mastery_count", "intervention_count", "notes", "status", "created_at", "updated_at"],
        "achievement_assessment_standards": ["assessment_id", "school_id", "mastery_reference_source", "mastery_reference_year", "mastery_reference_note", "created_at", "updated_at"],
        "achievement_actions": ["id", "school_id", "assessment_id", "action_type", "title", "target_group", "responsible_teacher_id", "start_date", "due_date", "status", "baseline_indicator", "target_indicator", "outcome_indicator", "notes", "completed_at", "created_at", "updated_at"],
        "achievement_action_metrics": ["action_id", "school_id", "metric_name", "unit", "direction", "baseline_value", "target_value", "outcome_value", "measured_at", "reference_source", "reference_year", "reference_note", "notes", "created_at", "updated_at"],
    }
    load_order = [
        "schools", "academic_years", "school_settings", "teachers", "teacher_profiles", "teacher_years", "teacher_cv_items",
        "upload_requests", "documents", "events", "event_media", "event_teacher_links", "activities", "meetings",
        "meeting_attendees", "meeting_decisions", "curriculum_plans", "curriculum_units", "supervision_visits",
        "supervision_actions", "achievement_assessments", "achievement_assessment_standards", "achievement_actions",
        "achievement_action_metrics",
    ]
    for table in load_order:
        sections.append(insert_sql(table, column_order[table], target[table], jsonb_columns={"value"} if table == "school_settings" else set()))

    expected_counts = {table: len(rows) for table, rows in target.items() if table not in {"profiles", "school_memberships"}}
    sections.append("-- Reconciliation: every dry-run target row count must match the compiler manifest.")
    sections.append("do $$")
    sections.append("declare v_count bigint;")
    sections.append("begin")
    sections.append(f"  select count(*) into v_count from public.schools where id={sql_literal(sid)}::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: schools'; end if;")
    for table, count in expected_counts.items():
        if table == "schools":
            continue
        sections.append(f"  select count(*) into v_count from public.{table} where school_id={sql_literal(sid)}::uuid; if v_count <> {count} then raise exception 'S2-E1 reconciliation failed: {table} expected {count} got %', v_count; end if;")
    sections.append("end $$;")
    sections.append("select 'PASS: S2-E1 SQLite migration dry run' as result;")
    sections.append("rollback;")
    sql_text = "\n".join(sections) + "\n"

    sql_path = output_dir / "marsad_s2_e1_dry_run.sql"
    sql_path.write_text(sql_text, encoding="utf-8", newline="\n")

    report = {
        "phase": "S2-E1",
        "compiler_version": COMPILER_VERSION,
        "status": "READY_FOR_SUPABASE_DRY_RUN",
        "source": {
            "filename": source.name,
            "sha256": source_sha,
            "size_bytes": source.stat().st_size,
            "integrity_check": "ok",
            "foreign_key_violations": 0,
            "source_table_count": len(SOURCE_TABLES),
        },
        "dry_run": {
            "school_id": sid,
            "school_name": school_name,
            "current_academic_year": current_year,
            "id_base": ID_BASE,
            "sql_ends_with_rollback": sql_text.rstrip().lower().endswith("rollback;"),
            "production_commit_allowed": False,
        },
        "source_audit": {table: audit.as_dict() for table, audit in audits.items()},
        "folded_relations": folded,
        "academic_years": {
            "labels": sorted(year_ids, key=lambda y: validate_academic_year(y)[0]),
            "inferred_counts": inferred_year_counts,
        },
        "transform_metrics": {
            "teacher_year_rows": len(target["teacher_years"]),
            "storage_file_id_folded_to_storage_path": storage_file_id_folded,
            "secret_settings_excluded": audits["settings"].excluded_rows,
        },
        "target_expected_counts": {table: len(rows) for table, rows in target.items()},
        "boundaries": {
            "auth_users_migrated": False,
            "school_memberships_migrated": False,
            "storage_bytes_migrated": False,
            "runtime_cutover": False,
            "live_data_commit": False,
        },
        "next_gate": "run marsad_s2_e1_dry_run.sql in Supabase SQL Editor and require PASS; the script rolls back",
    }
    reconciliation_path = output_dir / "marsad_s2_e1_reconciliation.json"
    reconciliation_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    md_lines = [
        "# S2-E1 SQLite Migration Dry-Run Report",
        "",
        f"- Source: `{source.name}`",
        f"- SHA-256: `{source_sha}`",
        f"- SQLite integrity: **PASS**",
        f"- Foreign-key violations: **0**",
        f"- Dry-run school UUID: `{sid}`",
        f"- Current academic year: `{current_year}`",
        f"- Source tables: **{len(SOURCE_TABLES)}/25**",
        f"- Target tables represented in dry run: **{sum(1 for v in target.values() if v)}/26** (profiles/memberships intentionally excluded)",
        f"- Secret settings excluded with audit trail: **{audits['settings'].excluded_rows}**",
        f"- Storage file IDs folded into storage_path metadata: **{storage_file_id_folded}**",
        "- Storage bytes moved: **No**",
        "- Runtime cutover: **No**",
        "- Live commit: **No**",
        "",
        "## Academic years",
        "",
    ]
    md_lines.extend(f"- `{year}`" for year in report["academic_years"]["labels"])
    md_lines += [
        "",
        "## Gate",
        "",
        "Run `marsad_s2_e1_dry_run.sql` in Supabase SQL Editor. Required result:",
        "",
        "`PASS: S2-E1 SQLite migration dry run`",
        "",
        "The SQL ends with `ROLLBACK;`; any missing rollback is a hard failure.",
    ]
    (output_dir / "marsad_s2_e1_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile a verified Marsad SQLite snapshot into a rollback-only Supabase dry-run pack.")
    parser.add_argument("source", type=Path, help="Path to a consistent marsad_alinjazat SQLite backup")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for generated SQL/reconciliation/report")
    parser.add_argument("--school-name", required=True, help="Dry-run tenant display name (not production provisioning)")
    parser.add_argument("--current-year", required=True, help="Explicit current academic year YYYY/YYYY")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = compile_database(args.source, args.output_dir, args.school_name, args.current_year)
    except (CompileError, sqlite3.DatabaseError, OSError, ValueError) as exc:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "phase": "S2-E1",
            "compiler_version": COMPILER_VERSION,
            "status": "NOT_READY",
            "error": str(exc),
        }
        (args.output_dir / "marsad_s2_e1_reconciliation.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print("PASS: Marsad S2-E1 SQLite migration compiler")
    print(f"INFO: source_sha256={report['source']['sha256']}")
    print(f"INFO: output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
