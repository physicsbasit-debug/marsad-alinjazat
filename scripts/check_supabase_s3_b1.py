from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_b1_teachers_read_contract.json"
REPOSITORY = ROOT / "src" / "lib" / "supabaseTeachers.ts"
DIAGNOSTIC = ROOT / "src" / "pages" / "TeachersReadDiagnostic.tsx"
APP = ROOT / "src" / "App.tsx"
API = ROOT / "src" / "lib" / "api.ts"
TEACHERS_PAGE = ROOT / "src" / "pages" / "Teachers.tsx"
S1_GUARD = ROOT / "scripts" / "check_supabase_foundation.py"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"
EXPECTED_MIGRATIONS = [
    "20260901120000_s2_b1_core_identity_tenancy.sql",
    "20260901190000_s2_b2_teachers_domain.sql",
    "20260901210000_s2_b3_operational_domains.sql",
    "20260902080000_s2_b4_content_intake_domains.sql",
    "20260902090000_s2_b5_schema_hardening.sql",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql",
    "20260903100000_s2_c1_security_foundation.sql",
    "20260903123000_s2_c2_domain_rls_baseline.sql",
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
    required = (PACKAGE, CONTRACT, REPOSITORY, DIAGNOSTIC, APP, API, TEACHERS_PAGE, S1_GUARD, WORKFLOW, VISIBLE_WORKFLOW)
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-B1 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 28, 0):
        fail("S3-B1 requires package version >= 0.28.0")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS:
        fail("S3-B1 must not alter PostgreSQL migration history")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-B1" or contract.get("project_version") != "0.28.0":
        fail("invalid S3-B1 contract identity")
    for key in (
        "schema_changes_allowed", "rls_changes_allowed", "sql_schema_migration_added",
        "teacher_domain_writes_allowed", "domain_runtime_switch_allowed", "storage_changes_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("legacy_fastapi_teachers_remain_operational_source") is not True:
        fail("Teachers operational source must remain Legacy in S3-B1")
    if contract.get("read_tables") != ["teachers", "teacher_years", "teacher_profiles", "teacher_cv_items"]:
        fail("teacher read table scope drifted")
    if contract.get("tenant_scope_source") != "S3-A TenantSessionContext.schoolId":
        fail("tenant scope must come from S3-A session context")
    if contract.get("academic_year_scope_source") != "S3-A TenantSessionContext.academicYearId":
        fail("academic-year scope must come from S3-A session context")
    parity = contract.get("parity_gate", {})
    for key in ("implemented", "required_before_operational_cutover", "legacy_preview_data_must_not_count_as_parity", "mismatch_blocks_cutover"):
        if parity.get(key) is not True:
            fail(f"parity gate requirement drifted: {key}")
    if parity.get("live_status_without_real_legacy_source") != "not_comparable":
        fail("live parity must remain not_comparable without a real Legacy source")
    live = contract.get("live_acceptance", {})
    if live.get("expected_text") != "PASS: S3-B1 Teachers Read Repository" or live.get("cutover_authorized") is not False:
        fail("S3-B1 live acceptance contract drifted")

    repository = REPOSITORY.read_text(encoding="utf-8")
    lower_repository = repository.lower()
    for fragment in (
        ".from('teachers')", ".from('teacher_years')", ".from('teacher_profiles')", ".from('teacher_cv_items')",
        ".eq('school_id', context.schoolId)", ".eq('academic_year_id', context.academicYearId)",
        ".eq('is_active', true)", "compareTeacherReadParity", "legacySource === null", "kind: 'real_legacy'",
        "مصدر Legacy الحقيقي غير متاح", "Number.isSafeInteger",
    ):
        if fragment.lower() not in lower_repository:
            fail(f"teachers repository missing {fragment}")
    for forbidden in (
        ".insert(", ".update(", ".delete(", ".upsert(", "service_role", "service-role",
        "raw_user_meta_data", "user_metadata.role", "app_metadata.role",
    ):
        if forbidden.lower() in lower_repository:
            fail(f"S3-B1 repository contains forbidden behavior: {forbidden}")
    if "error.message" in lower_repository:
        fail("raw Supabase errors must not be surfaced by teachers repository")

    diagnostic = DIAGNOSTIC.read_text(encoding="utf-8")
    for fragment in (
        "PASS: S3-B1 Teachers Read Repository", "Parity Gate", "NOT ESTABLISHED",
        "التحويل التشغيلي غير معتمد", "لا توجد صفوف معلمين", "loadSupabaseTeachersReadSnapshot",
    ):
        if fragment not in diagnostic:
            fail(f"teachers diagnostic missing {fragment}")
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", diagnostic, flags=re.IGNORECASE):
        fail("teachers diagnostic must not commit a real-looking email")

    app = APP.read_text(encoding="utf-8")
    if "TeachersReadDiagnostic" not in app or "get('teachers-check') === '1'" not in app:
        fail("App does not expose S3-B1 diagnostic entry")
    if app.index("if(isTeachersReadDiagnostic)") > app.index("if(publicToken)"):
        fail("teachers diagnostic must be resolved before public upload route")

    api = API.read_text(encoding="utf-8")
    if "supabaseTeachers" in api or "supabaseSession" in api:
        fail("S3-B1 must not switch api.ts to Supabase")
    if "return parseResponse(await apiFetch(`/api/bootstrap${params}`))" not in api:
        fail("legacy /api/bootstrap path changed during S3-B1")

    teachers_page = TEACHERS_PAGE.read_text(encoding="utf-8")
    if "supabaseTeachers" in teachers_page or "getSupabaseClient" in teachers_page:
        fail("operational Teachers page switched to Supabase before parity")

    s1_guard = S1_GUARD.read_text(encoding="utf-8")
    for path in ("src/lib/supabaseTeachers.ts", "src/pages/TeachersReadDiagnostic.tsx"):
        if path not in s1_guard:
            fail(f"S1 guard does not whitelist approved S3-B1 consumer: {path}")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_b1.py" not in workflow:
        fail("workflow does not execute S3-B1 guard")
    for fragment in (
        "VITE_SUPABASE_URL: ${{ vars.VITE_SUPABASE_URL }}",
        "VITE_SUPABASE_PUBLISHABLE_KEY: ${{ vars.VITE_SUPABASE_PUBLISHABLE_KEY }}",
        "VITE_SUPABASE_SESSION_MODE: 'diagnostic'",
    ):
        if fragment not in workflow:
            fail(f"GitHub Pages Supabase configuration drifted: {fragment}")

    print("PASS: Marsad S3-B1 teachers read repository and parity gate")
    print("INFO: read_tables=4 writes=0 migrations=0 schema_changes=0 rls_changes=0 runtime_switch=0")
    print("INFO: tenant_scope=session.schoolId year_scope=session.academicYearId parity_gate=required")
    print("INFO: live_without_legacy=not_comparable zero_rows=accepted cutover_authorized=0")


if __name__ == "__main__":
    main()
