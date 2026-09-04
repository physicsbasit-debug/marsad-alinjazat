from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_b3_teachers_ui_cutover_contract.json"
APP = ROOT / "src" / "App.tsx"
WORKSPACE = ROOT / "src" / "pages" / "TeachersWorkspace.tsx"
TEACHERS_PAGE = ROOT / "src" / "pages" / "Teachers.tsx"
PROFILE_REPO = ROOT / "src" / "lib" / "supabaseTeacherProfile.ts"
READ_REPO = ROOT / "src" / "lib" / "supabaseTeachers.ts"
WRITE_REPO = ROOT / "src" / "lib" / "supabaseTeachersWrite.ts"
API = ROOT / "src" / "lib" / "api.ts"
SERVER = ROOT / "server" / "main.py"
S1_GUARD = ROOT / "scripts" / "check_supabase_foundation.py"
ENV = ROOT / ".env.example"
ENV_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
VITE_ENV = ROOT / "src" / "vite-env.d.ts"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"
API_SHA = "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e"
SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
WRITE_REPO_SHA = "3e9605ec84d12b39a45db7174511938e373f664c6da8c929c99337e2d3c9879e"
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
    required = (PACKAGE, CONTRACT, APP, WORKSPACE, TEACHERS_PAGE, PROFILE_REPO, READ_REPO, WRITE_REPO,
                API, SERVER, S1_GUARD, ENV, ENV_VISIBLE, VITE_ENV, WORKFLOW, VISIBLE_WORKFLOW)
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-B3 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 30, 0):
        fail("S3-B3 requires package version >= 0.30.0")

    migrations = sorted(path.name for path in MIGRATIONS.glob("*.sql") if path.is_file())
    if migrations != EXPECTED_MIGRATIONS:
        fail(f"S3-B3 must add no migration and preserve migration history: {migrations}")

    if hashlib.sha256(API.read_bytes()).hexdigest() != API_SHA:
        fail("legacy api.ts changed during S3-B3")
    if hashlib.sha256(SERVER.read_bytes()).hexdigest() != SERVER_SHA:
        fail("server/main.py changed during S3-B3")
    if hashlib.sha256(WRITE_REPO.read_bytes()).hexdigest() != WRITE_REPO_SHA:
        fail("accepted S3-B2 teacher write RPC repository changed during UI cutover")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-B3" or contract.get("project_version") != "0.30.0":
        fail("invalid S3-B3 contract identity")
    for key in ("schema_changes_allowed", "rls_changes_allowed", "sql_schema_migration_added", "storage_changes_allowed",
                "teacher_delete_enabled", "other_domain_runtime_switch_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    for key in ("teachers_operational_ui_cutover", "current_academic_year_only", "historical_years_use_legacy",
                "legacy_api_unchanged", "server_unchanged", "legacy_teacher_search_deep_links_trigger_legacy_fallback"):
        if contract.get(key) is not True:
            fail(f"{key} must remain true")
    if contract.get("supabase_teacher_scope") != ["teachers", "teacher_years", "teacher_profiles", "teacher_cv_items"]:
        fail("teacher-domain scope drifted")
    if contract.get("related_domains_not_joined_by_teacher_id") != ["upload_requests", "documents", "supervision_visits"]:
        fail("related-domain isolation contract drifted")
    rollback = contract.get("rollback_switch", {})
    if rollback.get("implemented") is not True or rollback.get("label") != "الرجوع المؤقت إلى Legacy":
        fail("manual Legacy rollback switch is missing")

    env_text = ENV.read_text(encoding="utf-8")
    if env_text != ENV_VISIBLE.read_text(encoding="utf-8"):
        fail("visible env mirror is not byte-identical")
    if "VITE_TEACHERS_DATA_MODE=legacy" not in env_text:
        fail("default teachers data mode must remain legacy")

    if "VITE_TEACHERS_DATA_MODE" not in VITE_ENV.read_text(encoding="utf-8"):
        fail("Vite env typing does not include VITE_TEACHERS_DATA_MODE")

    app = APP.read_text(encoding="utf-8")
    for fragment in ("TeachersWorkspace", "legacyTeachers={data.teachers}", "onLegacyAddTeacher={()=>setTeacherModal(true)}",
                     "onSupabaseTeacherCount={setSupabaseTeacherCount}", "supabaseTeacherCount ?? data.dashboard.teacherCount"):
        if fragment not in app:
            fail(f"App cutover wiring missing: {fragment}")
    if "<Teachers teachers={data.teachers}" in app:
        fail("operational App still renders Teachers directly instead of cutover workspace")
    if "createTeacher(payload)" not in app:
        fail("Legacy TeacherModal rollback path was removed")

    workspace = WORKSPACE.read_text(encoding="utf-8")
    for fragment in (
        "VITE_TEACHERS_DATA_MODE", "academicYear === currentAcademicYear", "loadTenantSessionContext",
        "loadSupabaseTeachersReadSnapshot", "createSupabaseTeacher", "getSupabaseTeacherProfile",
        "updateSupabaseTeacherProfile", "createSupabaseTeacherCvItem", "deleteSupabaseTeacherCvItem",
        "الرجوع المؤقت إلى Legacy", "طلبات الملفات والوثائق والزيارات ما زالت على مصدر Legacy",
        "requests={[]}", "documents={[]}", "visits={[]}", "relatedDataNotice={RELATED_DATA_NOTICE}",
        "if (eligibleForSupabase && initialOpenId)", "setForceLegacy(true)",
    ):
        if fragment not in workspace:
            fail(f"TeachersWorkspace missing: {fragment}")
    for forbidden in ("service_role", "service-role", "sb_secret_", "raw_user_meta_data", "user_metadata.role", "app_metadata.role"):
        if forbidden.lower() in workspace.lower():
            fail(f"TeachersWorkspace contains forbidden auth/secret behavior: {forbidden}")

    teachers = TEACHERS_PAGE.read_text(encoding="utf-8")
    if "TeacherProfileActions" not in teachers or "profileActions = legacyTeacherProfileActions" not in teachers:
        fail("Teachers page does not expose a reversible data-access seam")
    if "relatedDataNotice" not in teachers or "relatedDataNotice ? '—'" not in teachers:
        fail("Teachers page does not visibly isolate non-migrated related domains")
    if re.search(r'from\s+[\'"][^\'"]*supabase', teachers):
        fail("presentational Teachers page must remain Supabase-agnostic")

    profile_repo = PROFILE_REPO.read_text(encoding="utf-8")
    for fragment in (
        "getSupabaseTeacherProfile", "updateSupabaseTeacherProfile", "createSupabaseTeacherCvItem", "deleteSupabaseTeacherCvItem",
        ".from('teacher_cv_items')", ".insert({", ".delete()", ".eq('school_id', context.schoolId)",
        "context.role !== 'owner' && context.role !== 'admin'", "Number.isSafeInteger",
    ):
        if fragment not in profile_repo:
            fail(f"Supabase teacher profile repository missing: {fragment}")
    for forbidden in ("service_role", "service-role", "sb_secret_", "error.message", ".from('upload_requests')", ".from('documents')", ".from('supervision_visits')"):
        if forbidden.lower() in profile_repo.lower():
            fail(f"Supabase teacher profile repository escaped S3-B3 scope: {forbidden}")

    read_repo = READ_REPO.read_text(encoding="utf-8").lower()
    for forbidden in (".insert(", ".update(", ".delete(", ".upsert("):
        if forbidden in read_repo:
            fail("S3-B1 read repository gained writes during S3-B3")

    s1 = S1_GUARD.read_text(encoding="utf-8")
    for path in ("src/lib/supabaseTeacherProfile.ts", "src/pages/TeachersWorkspace.tsx"):
        if path not in s1:
            fail(f"S1 guard does not whitelist S3-B3 consumer: {path}")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_b3.py" not in workflow:
        fail("workflow does not execute S3-B3 guard")
    if "VITE_TEACHERS_DATA_MODE: 'supabase'" not in workflow:
        fail("GitHub Pages does not activate S3-B3 Supabase teacher mode")

    print("PASS: Marsad S3-B3 Teachers UI cutover contract")
    print("INFO: teachers_ui=supabase current_year_only=1 historical_legacy=1 manual_rollback=1")
    print("INFO: create_update=RPC cv_items=RLS related_domains_isolated=3 migrations_added=0")
    print("INFO: api_legacy_unchanged=1 server_unchanged=1 teacher_delete=0 other_domain_cutover=0")


if __name__ == "__main__":
    main()
