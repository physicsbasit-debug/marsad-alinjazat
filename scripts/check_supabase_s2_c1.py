from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
CONTRACT = ROOT / "supabase" / "schema" / "s2_c1_security_foundation_contract.json"
LIVE = ROOT / "supabase" / "tests" / "s2_c1_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

C1 = "20260903100000_s2_c1_security_foundation.sql"
C1_SHA = "738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f"
HISTORICAL = {
    "20260901120000_s2_b1_core_identity_tenancy.sql": "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    "20260901190000_s2_b2_teachers_domain.sql": "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    "20260901210000_s2_b3_operational_domains.sql": "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    "20260902080000_s2_b4_content_intake_domains.sql": "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    "20260902090000_s2_b5_schema_hardening.sql": "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql": "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b",
}
CORE = {"schools", "profiles", "school_memberships", "academic_years", "school_settings"}
POLICIES = {
    "schools_select_active_members",
    "schools_update_owner",
    "profiles_select_self_or_school_managers",
    "profiles_update_self",
    "memberships_select_self_or_school_managers",
    "academic_years_select_active_members",
    "academic_years_insert_managers",
    "academic_years_update_managers",
    "school_settings_select_active_members",
    "school_settings_insert_managers",
    "school_settings_update_managers",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def compact(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def parse_version(value: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in value.split(".")[:3])
    except ValueError:
        fail(f"invalid package version: {value}")
    if len(parts) != 3:
        fail(f"invalid package version: {value}")
    return parts


def main() -> None:
    required_paths = (PACKAGE, CONTRACT, LIVE, WORKFLOW, VISIBLE_WORKFLOW, MIGRATIONS / C1)
    for path in required_paths:
        if not path.exists():
            fail(f"missing S2-C1 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if parse_version(package.get("version", "0.0.0")) < (0, 22, 0):
        fail("S2-C1 requires package version >= 0.22.0")

    for name, sha in HISTORICAL.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical live migration changed: {name}")

    if hashlib.sha256((MIGRATIONS / C1).read_bytes()).hexdigest() != C1_SHA:
        fail("S2-C1 migration hash mismatch")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected_prefix = list(HISTORICAL) + [C1]
    if migrations[: len(expected_prefix)] != expected_prefix:
        fail(f"migration order mismatch: {migrations}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-C1" or contract.get("project_version") != "0.22.0":
        fail("invalid S2-C1 contract identity")
    if contract.get("migration") != C1 or contract.get("migration_sha256") != C1_SHA:
        fail("S2-C1 contract migration identity/hash mismatch")
    if contract.get("tenant_boundary") != "school_memberships":
        fail("school_memberships must remain the tenant boundary")
    if contract.get("trusted_role_source") != "public.school_memberships.role":
        fail("authorization role must come from school_memberships.role")
    if contract.get("user_metadata_authorization_forbidden") is not True:
        fail("user_metadata must never be an authorization source")
    if set(contract.get("core_policy_tables", [])) != CORE or contract.get("policy_count") != 11:
        fail("S2-C1 core policy surface changed")
    for key in (
        "direct_membership_writes_from_browser",
        "direct_school_create_delete_from_browser",
        "direct_profile_create_delete_from_browser",
        "remaining_domain_tables_exposed",
        "runtime_switch_allowed",
        "sqlite_data_migration_allowed",
        "storage_policy_creation_allowed",
        "storage_bytes_migration_allowed",
        "auth_user_creation_in_migration_allowed",
        "service_secret_in_browser_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-C1")

    raw = (MIGRATIONS / C1).read_text(encoding="utf-8")
    sql = compact(raw)
    for fragment in (
        "create schema if not exists private",
        "security definer set search_path = ''",
        "create or replace function private.is_active_school_member(p_school_id uuid)",
        "create or replace function private.has_school_role(p_school_id uuid, p_roles text[])",
        "create or replace function private.can_view_profile(p_profile_id uuid)",
        "create or replace function private.handle_new_auth_user()",
        "after insert on auth.users",
        "execute function private.handle_new_auth_user()",
        "alter table public.schools enable row level security",
        "alter table public.profiles enable row level security",
        "alter table public.school_memberships enable row level security",
        "alter table public.academic_years enable row level security",
        "alter table public.school_settings enable row level security",
        "grant select on table public.schools to authenticated",
        "grant select on table public.profiles to authenticated",
        "grant select on table public.school_memberships to authenticated",
        "grant select on table public.academic_years to authenticated",
        "grant select on table public.school_settings to authenticated",
        "grant update (display_name) on table public.profiles to authenticated",
        "grant usage on sequence public.academic_years_id_seq to authenticated",
    ):
        if compact(fragment) not in sql:
            fail(f"S2-C1 migration missing: {fragment}")

    if re.search(r"grant\s+[^;]+\s+to\s+anon\b", sql, re.I):
        fail("S2-C1 must not grant browser access to anon")
    if "raw_user_meta_data ->> 'role'" in sql or "raw_user_meta_data ->> 'status'" in sql:
        fail("Auth user_metadata must not control Marsad role/status")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", sql, re.I):
        fail("S2-C1 migration must not create/mutate Auth users")
    if "storage.objects" in sql or "storage.buckets" in sql:
        fail("Storage policies/bytes are outside S2-C1")
    if re.search(r"create\s+table\s+public\.", sql, re.I):
        fail("S2-C1 must not create a new public domain table")

    policy_matches = re.findall(
        r"create\s+policy\s+([a-z_][a-z0-9_]*)\s+on\s+public\.([a-z_][a-z0-9_]*)",
        sql,
        re.I,
    )
    names = {name.lower() for name, _ in policy_matches}
    tables = {table.lower() for _, table in policy_matches}
    if len(policy_matches) != 11 or names != POLICIES or not tables <= CORE:
        fail(f"unexpected S2-C1 policies: count={len(policy_matches)} names={sorted(names)} tables={sorted(tables)}")

    # Membership writes remain trusted-server only even for owner/admin.
    if re.search(r"grant\s+(?:insert|update|delete)[^;]*on\s+(?:table\s+)?public\.school_memberships", sql, re.I):
        fail("browser membership writes are forbidden in S2-C1")
    if re.search(r"create\s+policy\s+[^;]+on\s+public\.school_memberships\s+for\s+(?:insert|update|delete)", sql, re.I):
        fail("membership mutation policies are forbidden in S2-C1")

    # Only three policy helpers are executable by authenticated; the Auth trigger is not.
    auth_exec = set(re.findall(r"grant\s+execute\s+on\s+function\s+([^;]+?)\s+to\s+authenticated", sql, re.I))
    expected_exec = {
        "private.is_active_school_member(uuid)",
        "private.has_school_role(uuid, text[])",
        "private.can_view_profile(uuid)",
    }
    if {re.sub(r"\s+", " ", x.strip().lower()) for x in auth_exec} != expected_exec:
        fail(f"authenticated helper EXECUTE surface changed: {sorted(auth_exec)}")
    if "grant execute on function private.handle_new_auth_user() to supabase_auth_admin" not in sql:
        fail("Auth profile trigger function must be executable only by supabase_auth_admin")

    live = compact(LIVE.read_text(encoding="utf-8"))
    for fragment in (
        "pass: s2-c1 security foundation acceptance",
        "set local role authenticated",
        "request.jwt.claim.sub",
        "create one temporary auth user",
        "browser membership write unexpectedly succeeded",
        "cross-school academic year insert unexpectedly succeeded",
        "rollback;",
    ):
        if compact(fragment) not in live:
            fail(f"S2-C1 live acceptance missing: {fragment}")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", live, re.I):
        fail("S2-C1 live acceptance must not mutate auth.users directly")

    wf = WORKFLOW.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW.read_text(encoding="utf-8")
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_c1.py" not in wf:
        fail("CI does not execute S2-C1 guard")

    print("PASS: Marsad Phase S2-C1 Auth/RLS security foundation contract")
    print("INFO: policy_tables=5 policies=11 helper_schema=private auth_profile_trigger=1")
    print("INFO: anon_grants=0 membership_browser_writes=0 remaining_domain_tables_exposed=0 runtime_switch=0")


if __name__ == "__main__":
    main()
