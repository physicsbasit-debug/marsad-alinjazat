from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_c2_supervision_cutover_contract.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = "20260904194500_s3_c2_supervision_write_cutover.sql"
MIGRATION_SHA = "f150c42b582cd6ffa560fcce33887f80cdea9b396334937d7da84512fc89b21f"
REPOSITORY = ROOT / "src" / "lib" / "supabaseSupervision.ts"
WORKSPACE = ROOT / "src" / "pages" / "SupervisionWorkspace.tsx"
SUPERVISION_PAGE = ROOT / "src" / "pages" / "Supervision.tsx"
APP = ROOT / "src" / "App.tsx"
API = ROOT / "src" / "lib" / "api.ts"
SERVER = ROOT / "server" / "main.py"
S1_GUARD = ROOT / "scripts" / "check_supabase_foundation.py"
S3_B3_GUARD = ROOT / "scripts" / "check_supabase_s3_b3.py"
S3_C1_GUARD = ROOT / "scripts" / "check_supabase_s3_c1.py"
ENV = ROOT / ".env.example"
ENV_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
VITE_ENV = ROOT / "src" / "vite-env.d.ts"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
LIVE = ROOT / "supabase" / "tests" / "s3_c2_live_acceptance.sql"

API_SHA = "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e"
SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
HISTORICAL_MIGRATIONS = {
    "20260901120000_s2_b1_core_identity_tenancy.sql": "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    "20260901190000_s2_b2_teachers_domain.sql": "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    "20260901210000_s2_b3_operational_domains.sql": "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    "20260902080000_s2_b4_content_intake_domains.sql": "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    "20260902090000_s2_b5_schema_hardening.sql": "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql": "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b",
    "20260903100000_s2_c1_security_foundation.sql": "738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f",
    "20260903123000_s2_c2_domain_rls_baseline.sql": "85d8325bcbe42ada1446b78c62950448fc33c74229bf71a783fed5f8ad474d32",
    "20260904130000_s3_b2_teacher_write_foundation.sql": "6cfce0ab365018feb8a3a3c5b9205120485cbaf5f21e6cb6de71f8119902e1f0",
    "20260904143000_s3_b2_r1_teacher_write_ambiguity_correction.sql": "417fb30a563a6cd92f7371a1c25ae07574258c8729e8f3cb44b0de785d3d9f3e",
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
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", " ", text)).strip().lower()


def main() -> None:
    required = (
        PACKAGE, CONTRACT, MIGRATIONS / MIGRATION, REPOSITORY, WORKSPACE, SUPERVISION_PAGE,
        APP, API, SERVER, S1_GUARD, S3_B3_GUARD, S3_C1_GUARD, ENV, ENV_VISIBLE,
        VITE_ENV, WORKFLOW, VISIBLE_WORKFLOW, LIVE,
    )
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C2 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 32, 0):
        fail("S3-C2 requires package version >= 0.32.0")

    for name, sha in HISTORICAL_MIGRATIONS.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical migration changed: {name}")
    migration_path = MIGRATIONS / MIGRATION
    if hashlib.sha256(migration_path.read_bytes()).hexdigest() != MIGRATION_SHA:
        fail("S3-C2 migration hash mismatch")
    migrations = sorted(path.name for path in MIGRATIONS.glob("*.sql") if path.is_file())
    expected = list(HISTORICAL_MIGRATIONS) + [MIGRATION]
    if migrations[:len(expected)] != expected:
        fail(f"S3-C2 migration history/order mismatch: {migrations}")

    if hashlib.sha256(API.read_bytes()).hexdigest() != API_SHA:
        fail("legacy api.ts changed during S3-C2")
    if hashlib.sha256(SERVER.read_bytes()).hexdigest() != SERVER_SHA:
        fail("server/main.py changed during S3-C2")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-C2" or contract.get("project_version") != "0.32.0":
        fail("invalid S3-C2 contract identity")
    if contract.get("migration") != MIGRATION or contract.get("migration_sha256") != MIGRATION_SHA:
        fail("S3-C2 contract migration identity/hash mismatch")
    for key in (
        "current_academic_year_only", "historical_years_use_legacy", "manual_legacy_rollback_preserved",
        "legacy_search_deep_links_trigger_legacy_fallback", "legacy_api_unchanged", "server_unchanged",
        "rls_changes_allowed", "database_function_changes_allowed", "sql_schema_migration_added",
        "supervision_action_delete_enabled", "closed_at_semantics_preserved", "completed_at_semantics_preserved",
    ):
        if contract.get(key) is not True:
            fail(f"{key} must be true")
    for key in (
        "table_or_column_schema_changes_allowed", "storage_changes_allowed", "public_upload_changes_allowed",
        "other_domain_runtime_switch_allowed", "supervision_visit_delete_enabled", "legacy_teacher_id_mapping",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("read_roles") != ["owner", "admin", "lead_teacher"]:
        fail("S3-C2 read roles drifted")
    if contract.get("write_roles") != ["owner", "admin"]:
        fail("S3-C2 write roles drifted")
    expected_rpcs = [
        "marsad_create_supervision_visit_v1", "marsad_update_supervision_visit_v1",
        "marsad_create_supervision_action_v1", "marsad_update_supervision_action_v1",
        "marsad_delete_supervision_action_v1",
    ]
    if contract.get("atomic_rpc_functions") != expected_rpcs:
        fail("S3-C2 RPC contract drifted")
    if contract.get("rpc_security") != "SECURITY INVOKER":
        fail("S3-C2 RPC security must remain SECURITY INVOKER")

    migration = MIGRATION_SHA and migration_path.read_text(encoding="utf-8")
    sql = compact(migration)
    for fragment in (
        "grant insert ( school_id, academic_year_id, actor_user_id, activity_type, title, detail, entity_type, entity_id ) on table public.activities to authenticated",
        "create policy activities_insert_managers on public.activities for insert to authenticated with check (private.has_school_role(school_id, array['owner', 'admin']::text[]))",
        "grant usage on sequence public.activities_id_seq to authenticated",
        "security invoker",
        "(select auth.uid())",
        "insert into public.activities",
        "case when p_status = 'closed' then now() else null end",
        "case when p_status='completed' then now() else null end",
    ):
        if fragment not in sql:
            fail(f"S3-C2 migration missing: {fragment}")
    for rpc in expected_rpcs:
        if f"function public.{rpc}" not in sql:
            fail(f"S3-C2 migration missing RPC: {rpc}")
    for forbidden in (
        "security definer", "service_role", "service-role", "sb_secret_",
        "grant delete on table public.supervision_visits", "create policy supervision_visits_delete",
        "alter table public.supervision_visits add", "alter table public.supervision_actions add",
        "drop table public.supervision_visits", "drop table public.supervision_actions",
    ):
        if forbidden in sql:
            fail(f"S3-C2 migration escaped boundary: {forbidden}")

    repository = REPOSITORY.read_text(encoding="utf-8")
    for fragment in (
        ".from('supervision_visits')", ".from('supervision_actions')", ".from('activities')",
        ".eq('school_id', context.schoolId)", ".eq('academic_year_id', context.academicYearId)",
        ".rpc('marsad_create_supervision_visit_v1'", ".rpc('marsad_update_supervision_visit_v1'",
        ".rpc('marsad_create_supervision_action_v1'", ".rpc('marsad_update_supervision_action_v1'",
        ".rpc('marsad_delete_supervision_action_v1'", "Asia/Muscat", "Number.isSafeInteger",
        "context.role !== 'owner' && context.role !== 'admin'",
    ):
        if fragment not in repository:
            fail(f"Supabase supervision repository missing: {fragment}")
    for forbidden in (
        ".insert(", ".update(", ".delete(", ".upsert(", "service_role", "service-role", "sb_secret_",
        "error.message", "legacyVisits", "normalizeName", "token_hash",
    ):
        if forbidden.lower() in repository.lower():
            fail(f"Supabase supervision repository escaped boundary: {forbidden}")
    if repository.count("list.push(row);") != 1:
        fail("supervision action aggregation must add each action row exactly once")

    page = SUPERVISION_PAGE.read_text(encoding="utf-8")
    for fragment in (
        "export type SupervisionDataActions", "dataActions = legacySupervisionDataActions",
        "dataActions.getVisit", "dataActions.updateVisit", "dataActions.createAction",
        "dataActions.updateAction", "dataActions.deleteAction", "canManage = true",
        "createVisit = createSupervisionVisit",
    ):
        if fragment not in page:
            fail(f"presentational Supervision seam missing: {fragment}")
    if re.search(r"from\s+['\"][^'\"]*supabase", page):
        fail("presentational Supervision page must remain Supabase-agnostic")

    workspace = WORKSPACE.read_text(encoding="utf-8")
    for fragment in (
        "VITE_SUPERVISION_DATA_MODE", "academicYear === currentAcademicYear", "loadTenantSessionContext",
        "loadSupabaseTeachersReadSnapshot", "loadSupabaseSupervisionSnapshot", "getSupabaseSupervisionVisit",
        "createSupabaseSupervisionVisit", "updateSupabaseSupervisionVisit", "createSupabaseSupervisionAction",
        "updateSupabaseSupervisionAction", "deleteSupabaseSupervisionAction", "S3-C2 • تشغيل الإشراف عبر Supabase",
        "الرجوع المؤقت إلى Legacy", "if (eligibleForSupabase && initialOpenId)", "setForceLegacy(true)",
        "context.role === 'lead_teacher'", "context.role === 'owner' || context.role === 'admin'",
    ):
        if fragment not in workspace:
            fail(f"SupervisionWorkspace missing: {fragment}")
    for forbidden in ("service_role", "service-role", "sb_secret_", "user_metadata.role", "app_metadata.role"):
        if forbidden.lower() in workspace.lower():
            fail(f"SupervisionWorkspace contains forbidden auth/secret behavior: {forbidden}")

    app = APP.read_text(encoding="utf-8")
    for fragment in (
        "SupervisionWorkspace", "SUPERVISION_DATA_MODE", "supervisionCreateSignal",
        "legacyVisits={data.visits}", "legacyAttention={data.supervisionAttention}",
        "legacyTeachers={data.teacherDirectory}", "createSignal={supervisionCreateSignal}",
        "SUPERVISION_DATA_MODE==='supabase'&&data.academicYear===data.currentAcademicYear",
        "<SupervisionVisitModal open={visitModal}",
    ):
        if fragment not in app:
            fail(f"App S3-C2 wiring missing: {fragment}")
    if "view==='supervision'?<Supervision visits={data.visits}" in app:
        fail("App still renders Legacy Supervision directly in the operational route")

    if ENV.read_bytes() != ENV_VISIBLE.read_bytes():
        fail("visible env mirror is not byte-identical")
    env_text = ENV.read_text(encoding="utf-8")
    if "VITE_SUPERVISION_DATA_MODE=legacy" not in env_text:
        fail("default supervision data mode must remain legacy")
    if "VITE_SUPERVISION_DATA_MODE" not in VITE_ENV.read_text(encoding="utf-8"):
        fail("Vite env typing does not include VITE_SUPERVISION_DATA_MODE")

    s1 = S1_GUARD.read_text(encoding="utf-8")
    for path in ("src/lib/supabaseSupervision.ts", "src/pages/SupervisionWorkspace.tsx"):
        if path not in s1:
            fail(f"S1 guard does not whitelist S3-C2 consumer: {path}")
    for historical_guard in (S3_B3_GUARD, S3_C1_GUARD):
        text = historical_guard.read_text(encoding="utf-8")
        if "migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS" not in text:
            fail(f"historical guard is not forward-compatible: {historical_guard.name}")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_c2.py" not in workflow:
        fail("workflow does not execute S3-C2 guard")
    if "VITE_SUPERVISION_DATA_MODE: 'supabase'" not in workflow:
        fail("GitHub Pages does not activate S3-C2 Supabase supervision mode")
    if "VITE_TEACHERS_DATA_MODE: 'supabase'" not in workflow:
        fail("S3-C2 accidentally disabled the accepted teacher Supabase mode")

    live = LIVE.read_text(encoding="utf-8")
    for fragment in (
        "PASS: S3-C2 supervision write RLS acceptance", "rollback;", "set local role authenticated",
        "lead_teacher create unexpectedly succeeded", "cross-tenant create unexpectedly succeeded",
        "closed_at was not stamped", "completed_at was not stamped", "activities_insert_managers",
    ):
        if fragment.lower() not in live.lower():
            fail(f"S3-C2 live acceptance missing: {fragment}")

    print("PASS: Marsad S3-C2 supervision read/write cutover contract")
    print("INFO: runtime=Supabase current_year_only=1 historical_legacy=1 manual_rollback=1")
    print("INFO: writes=visit_create+visit_update+action_create+action_update+action_delete timeline=activities")
    print("INFO: roles_read=owner,admin,lead_teacher roles_write=owner,admin visit_delete=0 storage_changes=0")


if __name__ == "__main__":
    main()
