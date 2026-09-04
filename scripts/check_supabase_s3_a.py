from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_a_auth_tenant_session_contract.json"
SESSION = ROOT / "src" / "lib" / "supabaseSession.ts"
DIAGNOSTIC = ROOT / "src" / "pages" / "AuthDiagnostic.tsx"
VITE_ENV = ROOT / "src" / "vite-env.d.ts"
APP = ROOT / "src" / "App.tsx"
API = ROOT / "src" / "lib" / "api.ts"
ENV = ROOT / ".env.example"
ENV_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
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
    required = (PACKAGE, CONTRACT, SESSION, DIAGNOSTIC, VITE_ENV, APP, API, ENV, ENV_VISIBLE, WORKFLOW, VISIBLE_WORKFLOW)
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-A artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 27, 0):
        fail("S3-A requires package version >= 0.27.0")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS:
        fail("S3-A must not alter PostgreSQL migration history")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-A" or contract.get("project_version") != "0.27.0":
        fail("invalid S3-A contract identity")
    for key in (
        "schema_changes_allowed",
        "rls_changes_allowed",
        "sql_schema_migration_added",
        "domain_runtime_switch_allowed",
        "storage_changes_allowed",
        "auth_user_creation_allowed",
        "membership_mutation_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("legacy_fastapi_bootstrap_remains_source") is not True:
        fail("legacy FastAPI bootstrap must remain the operational source in S3-A")
    if contract.get("diagnostic_read_tables") != ["profiles", "school_memberships", "schools", "academic_years"]:
        fail("S3-A diagnostic read scope drifted")
    if contract.get("authorization_source") != "public.school_memberships only; never Auth user_metadata/app_metadata":
        fail("authorization source drifted")
    if contract.get("supported_active_memberships") != 1:
        fail("S3-A must fail closed on multiple active memberships")
    privacy = contract.get("privacy", {})
    if any(privacy.get(key) is not False for key in ("owner_email_committed", "password_committed", "service_role_key_allowed_in_browser", "raw_provider_errors_shown_to_user")):
        fail("S3-A privacy contract drifted")

    vite_env = VITE_ENV.read_text(encoding="utf-8")
    if "VITE_SUPABASE_SESSION_MODE" not in vite_env:
        fail("Vite env types do not include VITE_SUPABASE_SESSION_MODE")

    if ENV.read_bytes() != ENV_VISIBLE.read_bytes():
        fail("visible env example is not byte-identical")
    env = ENV.read_text(encoding="utf-8")
    for fragment in ("VITE_SUPABASE_URL=", "VITE_SUPABASE_PUBLISHABLE_KEY=", "VITE_SUPABASE_SESSION_MODE=off"):
        if fragment not in env:
            fail(f"environment template missing {fragment}")
    for forbidden in ("SERVICE_ROLE", "VITE_SUPABASE_ANON_KEY", "SUPABASE_SECRET_KEY"):
        if forbidden in env:
            fail(f"browser environment template contains forbidden key: {forbidden}")

    session = SESSION.read_text(encoding="utf-8")
    lower_session = session.lower()
    for fragment in (
        "signinwithpassword",
        ".from('profiles')",
        ".from('school_memberships')",
        ".from('schools')",
        ".from('academic_years')",
        ".eq('status', 'active')",
        "memberships.length > 1",
        "لا توجد عضوية مدرسية نشطة",
        "يجب أن يكون للمدرسة عام دراسي حالي واحد بالضبط",
    ):
        if fragment.lower() not in lower_session:
            fail(f"session resolver missing {fragment}")
    for forbidden in (
        ".insert(", ".update(", ".delete(", ".upsert(", "service_role", "service-role",
        "raw_user_meta_data", "user_metadata.role", "app_metadata.role"
    ):
        if forbidden.lower() in lower_session:
            fail(f"session foundation contains forbidden behavior: {forbidden}")
    if "error.message" in lower_session:
        fail("raw Supabase provider error messages must not be surfaced")

    diagnostic = DIAGNOSTIC.read_text(encoding="utf-8")
    for fragment in (
        "PASS: S3-A Auth & Tenant Session",
        "تسجيل الدخول والتحقق",
        "المدرسة",
        "الدور",
        "العام الحالي",
        "لا تُنشئ هذه الصفحة مستخدمًا",
    ):
        if fragment not in diagnostic:
            fail(f"diagnostic page missing {fragment}")
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", diagnostic, flags=re.IGNORECASE):
        fail("diagnostic page must not commit a real-looking email")

    app = APP.read_text(encoding="utf-8")
    if "AuthDiagnostic" not in app or "get('auth-check') === '1'" not in app:
        fail("App does not expose the S3-A diagnostic entry")
    if app.index("if(isAuthDiagnostic)") > app.index("if(publicToken)"):
        fail("auth diagnostic route ordering drifted")

    api = API.read_text(encoding="utf-8")
    if "from './supabase" in api or 'from "./supabase' in api:
        fail("S3-A must not switch the operational API layer to Supabase")
    if "return parseResponse(await apiFetch(`/api/bootstrap${params}`))" not in api:
        fail("legacy /api/bootstrap path changed during S3-A")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "python scripts/check_supabase_s3_a.py",
        "VITE_SUPABASE_URL: ${{ vars.VITE_SUPABASE_URL }}",
        "VITE_SUPABASE_PUBLISHABLE_KEY: ${{ vars.VITE_SUPABASE_PUBLISHABLE_KEY }}",
        "VITE_SUPABASE_SESSION_MODE: 'diagnostic'",
        "VITE_PREVIEW_MODE: 'true'",
    ):
        if fragment not in workflow:
            fail(f"workflow missing S3-A requirement: {fragment}")

    print("PASS: Marsad S3-A Auth and tenant-session foundation")
    print("INFO: migrations=0 schema_changes=0 rls_changes=0 domain_runtime_switch=0")
    print("INFO: diagnostic_reads=profiles,memberships,schools,academic_years")
    print("INFO: github_pages_preview=1 auth_diagnostic=1 operational_bootstrap=legacy_fastapi")


if __name__ == "__main__":
    main()
