from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_b2_teacher_write_contract.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = "20260904130000_s3_b2_teacher_write_foundation.sql"
MIGRATION_SHA = "6cfce0ab365018feb8a3a3c5b9205120485cbaf5f21e6cb6de71f8119902e1f0"
REPOSITORY = ROOT / "src" / "lib" / "supabaseTeachersWrite.ts"
READ_REPOSITORY = ROOT / "src" / "lib" / "supabaseTeachers.ts"
API = ROOT / "src" / "lib" / "api.ts"
TEACHERS_PAGE = ROOT / "src" / "pages" / "Teachers.tsx"
S1_GUARD = ROOT / "scripts" / "check_supabase_foundation.py"
S3_B1_GUARD = ROOT / "scripts" / "check_supabase_s3_b1.py"
LIVE = ROOT / "supabase" / "tests" / "s3_b2_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
HISTORICAL_GUARDS = [
    ROOT / "scripts" / "check_supabase_s2_d_fix1.py",
    ROOT / "scripts" / "check_supabase_s2_e1.py",
    ROOT / "scripts" / "check_supabase_s2_e1b.py",
    ROOT / "scripts" / "check_supabase_s2_e2.py",
    ROOT / "scripts" / "check_supabase_s3_a.py",
    ROOT / "scripts" / "check_supabase_s3_b1.py",
]
HISTORICAL_MIGRATIONS = {
    "20260901120000_s2_b1_core_identity_tenancy.sql": "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    "20260901190000_s2_b2_teachers_domain.sql": "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    "20260901210000_s2_b3_operational_domains.sql": "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    "20260902080000_s2_b4_content_intake_domains.sql": "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    "20260902090000_s2_b5_schema_hardening.sql": "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql": "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b",
    "20260903100000_s2_c1_security_foundation.sql": "738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f",
    "20260903123000_s2_c2_domain_rls_baseline.sql": "85d8325bcbe42ada1446b78c62950448fc33c74229bf71a783fed5f8ad474d32",
}


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


def compact(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> None:
    required = (
        PACKAGE, CONTRACT, MIGRATIONS / MIGRATION, REPOSITORY, READ_REPOSITORY,
        API, TEACHERS_PAGE, S1_GUARD, S3_B1_GUARD, LIVE, WORKFLOW, VISIBLE_WORKFLOW,
    )
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-B2 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 29, 0):
        fail("S3-B2 requires package version >= 0.29.0")

    # Historical live migrations are immutable; S3-B2 is migration number nine.
    for name, sha in HISTORICAL_MIGRATIONS.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical migration changed: {name}")
    migration_path = MIGRATIONS / MIGRATION
    if hashlib.sha256(migration_path.read_bytes()).hexdigest() != MIGRATION_SHA:
        fail("S3-B2 migration hash mismatch")
    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected_prefix = list(HISTORICAL_MIGRATIONS) + [MIGRATION]
    if migrations[:len(expected_prefix)] != expected_prefix:
        fail(f"S3-B2 migration order mismatch: {migrations}")

    # Historical stage guards must allow later additive migrations rather than pinning exactly eight forever.
    for path in HISTORICAL_GUARDS:
        text = path.read_text(encoding="utf-8")
        if "migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS" not in text:
            fail(f"historical guard is not forward-compatible with S3-B2 migration: {path.name}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-B2" or contract.get("project_version") != "0.29.0":
        fail("invalid S3-B2 contract identity")
    if contract.get("migration") != MIGRATION or contract.get("migration_sha256") != MIGRATION_SHA:
        fail("S3-B2 contract migration identity/hash mismatch")
    if contract.get("table_or_column_schema_changes_allowed") is not False:
        fail("S3-B2 must not change teacher table/column schema")
    if contract.get("rls_changes_allowed") is not True or contract.get("database_function_changes_allowed") is not True:
        fail("S3-B2 must explicitly authorize its narrow RLS/RPC changes")
    if contract.get("sql_schema_migration_added") is not True:
        fail("S3-B2 migration presence must be explicit")
    for key in (
        "domain_runtime_switch_allowed", "storage_changes_allowed", "teacher_delete_enabled",
        "lead_teacher_write_enabled", "operational_ui_cutover",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S3-B2")
    if contract.get("legacy_fastapi_teachers_remain_operational_source") is not True:
        fail("Teachers operational source must remain Legacy in S3-B2")
    if contract.get("write_roles") != ["owner", "admin"]:
        fail("S3-B2 write roles must remain owner/admin only")
    update_behavior = contract.get("update_behavior", {})
    if update_behavior.get("preserves_teacher_is_active") is not True or update_behavior.get("preserves_existing_teacher_year_is_active") is not True:
        fail("S3-B2 update must preserve existing active-state flags")
    unlock = contract.get("teacher_years_write_unlock", {})
    if unlock.get("insert") is not True or unlock.get("update") is not True or unlock.get("delete") is not False:
        fail("teacher_years write unlock contract drifted")
    if unlock.get("insert_columns") != ["school_id", "academic_year_id", "teacher_id", "subject", "experience_years", "workload", "grades", "responsibilities"]:
        fail("teacher_years INSERT column allowlist drifted")
    if unlock.get("update_columns") != ["subject", "experience_years", "workload", "grades", "responsibilities"]:
        fail("teacher_years UPDATE column allowlist drifted")
    atomic = contract.get("atomic_write_strategy", {})
    if atomic.get("security_mode") != "SECURITY INVOKER" or atomic.get("caller_rls_remains_authoritative") is not True:
        fail("S3-B2 RPCs must remain SECURITY INVOKER with RLS authoritative")
    if atomic.get("functions") != ["marsad_create_teacher_v1", "marsad_update_teacher_v1"]:
        fail("S3-B2 atomic RPC list drifted")
    live_contract = contract.get("live_acceptance", {})
    if live_contract.get("expected_text") != "PASS: S3-B2 teacher write RLS acceptance":
        fail("S3-B2 live acceptance text drifted")
    if any(live_contract.get(k) is not True for k in (
        "uses_authenticated_role", "tests_owner_create_update", "tests_cross_tenant_block",
        "tests_lead_teacher_block", "tests_delete_stays_blocked", "rollback_required",
    )):
        fail("S3-B2 live acceptance requirements drifted")

    migration = migration_path.read_text(encoding="utf-8")
    sql = compact(migration)
    for fragment in (
        "grant insert ( school_id, academic_year_id, teacher_id, subject, experience_years, workload, grades, responsibilities ) on table public.teacher_years to authenticated",
        "grant update ( subject, experience_years, workload, grades, responsibilities ) on table public.teacher_years to authenticated",
        "create policy teacher_years_insert_managers on public.teacher_years for insert to authenticated with check (private.has_school_role(school_id, array['owner', 'admin']::text[]))",
        "create policy teacher_years_update_managers on public.teacher_years for update to authenticated using (private.has_school_role(school_id, array['owner', 'admin']::text[]))",
        "create or replace function public.marsad_create_teacher_v1",
        "create or replace function public.marsad_update_teacher_v1",
        "security invoker",
        "private.has_school_role(p_school_id, array['owner', 'admin']::text[])",
        "on conflict (school_id, academic_year_id, teacher_id) do nothing",
        "on conflict (school_id, academic_year_id, teacher_id) do update",
        "on conflict (teacher_id) do update",
        "grant execute on function public.marsad_create_teacher_v1",
        "grant execute on function public.marsad_update_teacher_v1",
    ):
        if compact(fragment) not in sql:
            fail(f"S3-B2 migration missing: {fragment}")
    if "set name = v_name, specialization = v_specialization, qualification = v_qualification, email = v_email, phone = v_phone, is_active = true" in sql:
        fail("S3-B2 update must not reactivate teacher identity implicitly")
    if "responsibilities = excluded.responsibilities, is_active = true" in sql:
        fail("S3-B2 update must not reactivate an existing teacher_year implicitly")
    if re.search(r"grant\s+(?:insert|update)\s*\([^)]*\bis_active\b[^)]*\)\s+on\s+table\s+public\.teacher_years", sql, re.I):
        fail("S3-B2 must not expose teacher_years is_active through staged column grants")
    if "security definer" in sql:
        fail("S3-B2 public teacher RPC must not use SECURITY DEFINER")
    if re.search(r"create\s+table\s+public\.", sql, re.I) or re.search(r"alter\s+table\s+public\.[^;]+\b(?:add|drop|alter)\s+column\b", sql, re.I):
        fail("S3-B2 must not create tables or alter columns")
    if re.search(r"grant\s+delete[^;]+public\.(?:teachers|teacher_years)\b", sql, re.I):
        fail("S3-B2 must not grant root teacher delete")
    if re.search(r"create\s+policy\s+[^;]+on\s+public\.(?:teachers|teacher_years)\s+for\s+delete", sql, re.I):
        fail("S3-B2 must not add root teacher delete policy")
    if re.search(r"grant\s+[^;]+\s+to\s+anon\b", sql, re.I):
        fail("S3-B2 must not grant teacher write access to anon")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", sql, re.I):
        fail("S3-B2 must not mutate auth users")
    if any(token in sql for token in ("service_role", "service-role", "raw_user_meta_data", "user_metadata.role", "app_metadata.role")):
        fail("S3-B2 authorization must not use browser secrets or Auth metadata roles")

    repository = REPOSITORY.read_text(encoding="utf-8")
    lower_repository = repository.lower()
    for fragment in (
        "createSupabaseTeacher", "updateSupabaseTeacher",
        ".rpc('marsad_create_teacher_v1'", ".rpc('marsad_update_teacher_v1'",
        "context.schoolId", "context.academicYearId", "context.role !== 'owner' && context.role !== 'admin'",
        "Number.isSafeInteger", "S3-B2 يسمح بالكتابة في العام الدراسي الحالي للجلسة فقط",
    ):
        if fragment.lower() not in lower_repository:
            fail(f"S3-B2 repository missing {fragment}")
    for forbidden in (
        ".insert(", ".update(", ".delete(", ".upsert(", "service_role", "service-role",
        "raw_user_meta_data", "user_metadata.role", "app_metadata.role", "error.message",
    ):
        if forbidden.lower() in lower_repository:
            fail(f"S3-B2 repository contains forbidden direct/bypass behavior: {forbidden}")

    # Read repository remains read-only and operational UI stays Legacy.
    read_repo = READ_REPOSITORY.read_text(encoding="utf-8").lower()
    for forbidden in (".insert(", ".update(", ".delete(", ".upsert("):
        if forbidden in read_repo:
            fail("S3-B1 read repository was mutated into a write path")
    api = API.read_text(encoding="utf-8")
    teachers_page = TEACHERS_PAGE.read_text(encoding="utf-8")
    if "supabaseTeachersWrite" in api or "marsad_create_teacher_v1" in api or "marsad_update_teacher_v1" in api:
        fail("api.ts switched teacher writes to Supabase before S3-B3")
    if "supabaseTeachersWrite" in teachers_page or "marsad_create_teacher_v1" in teachers_page:
        fail("Teachers UI switched to Supabase write repository before S3-B3")
    if "createTeacher(payload)" not in (ROOT / "src" / "App.tsx").read_text(encoding="utf-8"):
        fail("Legacy TeacherModal create path changed during S3-B2")

    s1_guard = S1_GUARD.read_text(encoding="utf-8")
    if "src/lib/supabaseTeachersWrite.ts" not in s1_guard or "version_tuple >= (0, 29, 0)" not in s1_guard:
        fail("S1 guard does not whitelist the approved staged S3-B2 repository")

    live = LIVE.read_text(encoding="utf-8")
    live_sql = compact(live)
    for fragment in (
        "pass: s3-b2 teacher write rls acceptance",
        "set local role authenticated",
        "marsad_create_teacher_v1",
        "marsad_update_teacher_v1",
        "cross-tenant teacher create unexpectedly succeeded",
        "lead_teacher create unexpectedly succeeded",
        "root teacher delete unexpectedly succeeded",
        "teacher_years delete unexpectedly succeeded",
        "rollback;",
    ):
        if compact(fragment) not in live_sql:
            fail(f"S3-B2 live acceptance missing: {fragment}")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", live_sql, re.I):
        fail("S3-B2 live acceptance must not mutate auth.users")
    if "@gmail.com" in live_sql or "@outlook.com" in live_sql or "@hotmail.com" in live_sql:
        fail("S3-B2 live acceptance must not commit a real owner email")
    if not live_sql.endswith("rollback;"):
        fail("S3-B2 live acceptance must end with ROLLBACK")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_b2.py" not in workflow:
        fail("workflow does not execute S3-B2 guard")

    print("PASS: Marsad S3-B2 teachers write repository and RLS acceptance contract")
    print("INFO: migration=1 teacher_years_insert_update=owner/admin atomic_rpcs=2 security=invoker")
    print("INFO: teacher_delete=0 lead_teacher_write=0 operational_cutover=0 storage_changes=0")
    print("INFO: live_acceptance=rollback cross_tenant_block=required")


if __name__ == "__main__":
    main()
