from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_c1_teacher_related_read_contract.json"
RELATED = ROOT / "src" / "lib" / "supabaseTeacherRelated.ts"
WORKSPACE = ROOT / "src" / "pages" / "TeachersWorkspace.tsx"
PROFILE = ROOT / "src" / "lib" / "supabaseTeacherProfile.ts"
TEACHERS_PAGE = ROOT / "src" / "pages" / "Teachers.tsx"
API = ROOT / "src" / "lib" / "api.ts"
SERVER = ROOT / "server" / "main.py"
S1_GUARD = ROOT / "scripts" / "check_supabase_foundation.py"
ENV = ROOT / ".env.example"
ENV_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"

API_SHA = "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e"
SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
EXPECTED_MIGRATIONS = [
    "20260901120000_s2_b1_core_identity_tenancy.sql",
    "20260901190000_s2_b2_teachers_domain.sql",
    "20260901210000_s2_b3_operational_domains.sql",
    "20260902080000_s2_b4_content_intake_domains.sql",
    "20260902090000_s2_b5_schema_hardening.sql",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql",
    "20260903100000_s2_c1_security_foundation.sql",
    "20260903123000_s2_c2_domain_rls_baseline.sql",
    "20260904130000_s3_b2_teacher_write_foundation.sql",
    "20260904143000_s3_b2_r1_teacher_write_ambiguity_correction.sql",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def version_tuple(raw: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in raw.split("."))
    except ValueError:
        fail("invalid package version")
    if len(parts) != 3:
        fail("package version must be semantic x.y.z")
    return parts


def main() -> None:
    required = (PACKAGE, CONTRACT, RELATED, WORKSPACE, PROFILE, TEACHERS_PAGE, API, SERVER,
                S1_GUARD, ENV, ENV_VISIBLE, WORKFLOW, VISIBLE_WORKFLOW)
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C1 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 31, 0):
        fail("S3-C1 requires package version >= 0.31.0")

    migrations = sorted(path.name for path in MIGRATIONS.glob("*.sql") if path.is_file())
    if migrations != EXPECTED_MIGRATIONS:
        fail(f"S3-C1 must add no migration and preserve migration history: {migrations}")

    if hashlib.sha256(API.read_bytes()).hexdigest() != API_SHA:
        fail("legacy api.ts changed during S3-C1")
    if hashlib.sha256(SERVER.read_bytes()).hexdigest() != SERVER_SHA:
        fail("server/main.py changed during S3-C1")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-C1" or contract.get("project_version") != "0.31.0":
        fail("invalid S3-C1 contract identity")
    for key in (
        "schema_changes_allowed", "rls_changes_allowed", "sql_schema_migration_added",
        "related_domain_writes_enabled", "teacher_delete_enabled", "other_domain_runtime_switch_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    for key in (
        "current_academic_year_only", "historical_years_use_legacy",
        "legacy_related_rows_never_joined_to_supabase_teacher_ids",
        "supabase_teacher_identity_is_authoritative", "manual_legacy_rollback_preserved",
    ):
        if contract.get(key) is not True:
            fail(f"{key} must remain true")
    if contract.get("related_read_tables") != ["upload_requests", "documents", "supervision_visits", "supervision_actions"]:
        fail("S3-C1 related read table scope drifted")
    if contract.get("forbidden_selected_columns") != ["token_hash"]:
        fail("S3-C1 secret-column exclusion drifted")

    related = RELATED.read_text(encoding="utf-8")
    for fragment in (
        ".from('upload_requests')", ".from('documents')", ".from('supervision_visits')", ".from('supervision_actions')",
        ".eq('school_id', context.schoolId)", ".eq('academic_year_id', context.academicYearId)",
        "teacherById", "teacherRelatedStats", "Number.isSafeInteger", "Asia/Muscat", ".in('visit_id', [...visibleVisitIds])",
    ):
        if fragment not in related:
            fail(f"related repository missing: {fragment}")
    for forbidden in (
        ".insert(", ".update(", ".delete(", ".upsert(", "token_hash", "legacyTeachers",
        "normalizeName", "service_role", "service-role", "sb_secret_", "user_metadata.role", "app_metadata.role",
    ):
        if forbidden.lower() in related.lower():
            fail(f"related repository escaped S3-C1 boundary: {forbidden}")

    workspace = WORKSPACE.read_text(encoding="utf-8")
    for fragment in (
        "loadSupabaseTeacherRelatedSnapshot", "setRelatedSnapshot", "requests={relatedSnapshot.requests}",
        "documents={relatedSnapshot.documents}", "visits={relatedSnapshot.visits}",
        "getSupabaseTeacherProfile(context, teacherId, relatedSnapshot)", "S3-C1 • علاقات Supabase",
        "الرجوع المؤقت إلى Legacy", "legacyTeachers", "requests={requests}", "documents={documents}", "visits={visits}",
    ):
        if fragment not in workspace:
            fail(f"TeachersWorkspace S3-C1 wiring missing: {fragment}")
    for forbidden in ("requests={[]}", "documents={[]}", "visits={[]}", "RELATED_DATA_NOTICE"):
        if forbidden in workspace:
            fail(f"obsolete S3-B3 isolation remains active: {forbidden}")

    profile = PROFILE.read_text(encoding="utf-8")
    for fragment in ("SupabaseTeacherRelatedSnapshot", "teacherRelatedStats", "relatedSnapshot?:", "teacherRelatedStats(relatedSnapshot, safeTeacherId)"):
        if fragment not in profile:
            fail(f"profile repository missing S3-C1 stats seam: {fragment}")
    for forbidden in (".from('upload_requests')", ".from('documents')", ".from('supervision_visits')"):
        if forbidden in profile:
            fail("profile repository must not duplicate related-domain queries")

    teachers = TEACHERS_PAGE.read_text(encoding="utf-8")
    if "TeacherProfileActions" not in teachers or "profileActions = legacyTeacherProfileActions" not in teachers:
        fail("presentational teacher page lost reversible data-access seam")
    if "from '../lib/supabase" in teachers or 'from "../lib/supabase' in teachers:
        fail("presentational Teachers page must remain Supabase-agnostic")

    if ENV.read_bytes() != ENV_VISIBLE.read_bytes():
        fail("visible env mirror is not byte-identical")
    if "VITE_TEACHERS_DATA_MODE=legacy" not in ENV.read_text(encoding="utf-8"):
        fail("default teachers data mode must remain legacy")

    s1 = S1_GUARD.read_text(encoding="utf-8")
    if "src/lib/supabaseTeacherRelated.ts" not in s1:
        fail("S1 guard does not whitelist S3-C1 repository")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_c1.py" not in workflow:
        fail("workflow does not execute S3-C1 guard")
    if "VITE_TEACHERS_DATA_MODE: 'supabase'" not in workflow:
        fail("GitHub Pages no longer activates teacher Supabase mode")

    print("PASS: Marsad S3-C1 teacher-related Supabase read boundary")
    print("INFO: reads=upload_requests,documents,supervision_visits,supervision_actions writes=0 migrations_added=0")
    print("INFO: teacher_identity=supabase_fk legacy_id_join=0 token_hash_selected=0 historical_legacy=1")
    print("INFO: related_counts=live_supabase current_year_only=1 manual_rollback=1")


if __name__ == "__main__":
    main()
