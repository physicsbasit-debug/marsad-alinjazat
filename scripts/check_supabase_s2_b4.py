from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "package.json"
TARGET_CONTRACT = ROOT / "supabase" / "schema" / "target_schema_v1.json"
PHASE_CONTRACT = ROOT / "supabase" / "schema" / "s2_b4_content_contract.json"
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
LIVE_ACCEPTANCE = ROOT / "supabase" / "tests" / "s2_b4_live_acceptance.sql"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW_FILE = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

B1 = "20260901120000_s2_b1_core_identity_tenancy.sql"
B2 = "20260901190000_s2_b2_teachers_domain.sql"
B3 = "20260901210000_s2_b3_operational_domains.sql"
B4 = "20260902080000_s2_b4_content_intake_domains.sql"
EXPECTED_TARGET_SHA256 = "84ba44b8104d09d62095c4af00a40d413ddc78fb1b2b251af1487d439368ecda"
EXPECTED_HASHES = {
    B1: "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    B2: "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    B3: "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    B4: "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
}
EXPECTED_TABLES = {
    "school_settings",
    "upload_requests",
    "documents",
    "events",
    "event_media",
    "event_teacher_links",
    "activities",
}
REMOVED_LEGACY = {"request_record_years", "event_record_years", "teacher_record_years", "event_media_meta"}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def compact(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def table_raw(sql: str, table: str) -> str:
    match = re.search(
        rf"create\s+table\s+public\.{re.escape(table)}\s*\((.*?)\n\);",
        sql,
        flags=re.I | re.S,
    )
    if not match:
        fail(f"missing CREATE TABLE public.{table}")
    return match.group(1)


def table_body(sql: str, table: str) -> str:
    return compact(table_raw(sql, table))


def require(haystack: str, fragment: str, label: str) -> None:
    if compact(fragment) not in haystack:
        fail(f"{label} missing required fragment: {fragment}")


def main() -> None:
    for path in (PACKAGE_FILE, TARGET_CONTRACT, PHASE_CONTRACT, LIVE_ACCEPTANCE, WORKFLOW_FILE, VISIBLE_WORKFLOW_FILE):
        if not path.exists():
            fail(f"required S2-B4 file missing: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    if package.get("version") != "0.20.0":
        fail("S2-B4 package version must be 0.20.0")

    if hashlib.sha256(TARGET_CONTRACT.read_bytes()).hexdigest() != EXPECTED_TARGET_SHA256:
        fail("S2-A frozen target schema changed during S2-B4")

    migrations = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    expected_migrations = [B1, B2, B3, B4]
    if migrations != expected_migrations:
        fail(f"unexpected migration history for S2-B4: {migrations}")
    for name, expected_hash in EXPECTED_HASHES.items():
        path = MIGRATIONS_DIR / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            fail(f"migration changed unexpectedly: {name}")

    contract = json.loads(PHASE_CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-B4" or contract.get("project_version") != "0.20.0":
        fail("invalid S2-B4 phase contract identity")
    if contract.get("frozen_schema_contract_sha256") != EXPECTED_TARGET_SHA256:
        fail("S2-B4 contract is not pinned to S2-A")
    if contract.get("migration") != B4 or contract.get("migration_sha256") != EXPECTED_HASHES[B4]:
        fail("S2-B4 contract migration identity/hash is wrong")
    if set(contract.get("new_tables", [])) != EXPECTED_TABLES:
        fail("S2-B4 contract table set changed")
    if contract.get("remaining_target_tables_after_s2_b4") != []:
        fail("S2-B4 must complete the frozen 26-table target set")
    for key in (
        "runtime_switch_allowed",
        "data_migration_allowed",
        "storage_bytes_migration_allowed",
        "public_upload_edge_function_allowed",
        "rls_ddl_allowed_in_migration",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-B4")
    if contract.get("deny_by_default_until_s2_c") is not True:
        fail("S2-B4 must remain deny-by-default")
    if contract.get("same_school_foreign_keys_required") is not True:
        fail("S2-B4 must require same-school foreign keys")
    if set(contract.get("storage_provider_contract", [])) != {"supabase", "google_drive", "legacy_local"}:
        fail("S2-B4 storage provider contract changed")

    target = json.loads(TARGET_CONTRACT.read_text(encoding="utf-8"))
    target_tables = {item["name"]: item for item in target["tables"]}
    if not EXPECTED_TABLES.issubset(target_tables):
        fail("S2-A target schema lacks S2-B4 tables")
    if set(target.get("removed_legacy_tables", [])) != REMOVED_LEGACY:
        fail("S2-A removed legacy table set changed")

    raw = (MIGRATIONS_DIR / B4).read_text(encoding="utf-8")
    sql = compact(raw)
    created = set(re.findall(r"create\s+table\s+public\.([a-z_][a-z0-9_]*)", sql))
    if created != EXPECTED_TABLES:
        fail(f"S2-B4 may create only the seven remaining target tables; got {sorted(created)}")
    if created & REMOVED_LEGACY:
        fail(f"removed legacy tables were recreated: {sorted(created & REMOVED_LEGACY)}")

    forbidden_patterns = {
        "RLS enablement": r"enable\s+row\s+level\s+security",
        "RLS policy": r"create\s+policy",
        "runtime function": r"create\s+(?:or\s+replace\s+)?function",
        "application data insert": r"insert\s+into",
        "application data update": r"update\s+public\.",
        "application data delete": r"delete\s+from",
        "auth mutation": r"(?:insert\s+into|update|delete\s+from)\s+auth\.",
        "storage mutation": r"storage\.objects",
        "raw upload token": r"\btoken\s+text\b",
        "service role": r"service[_ -]?role",
        "OAuth secret material": r"refresh[_ -]?token|access[_ -]?token|client[_ -]?secret",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, sql, flags=re.I):
            fail(f"forbidden S2-B4 SQL detected: {label}")

    # Every frozen target column for these seven tables must be a real column definition.
    for table in sorted(EXPECTED_TABLES):
        raw_body = table_raw(raw, table)
        expected_columns = set(target_tables[table]["columns"])
        found_columns: set[str] = set()
        for line in raw_body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            token = stripped.split()[0].rstrip(",").strip('"').lower()
            if token in expected_columns:
                found_columns.add(token)
        if found_columns != expected_columns:
            fail(f"{table} column contract mismatch: expected={sorted(expected_columns)} found={sorted(found_columns)}")

    for fragment, label in [
        ("primary key (school_id, key)", "school settings PK"),
        ("foreign key (school_id, updated_by) references public.school_memberships (school_id, user_id) on delete set null (updated_by)", "settings updater same-school FK"),
        ("foreign key (school_id, academic_year_id) references public.academic_years (school_id, id) on delete restrict", "academic-year same-school FK"),
        ("foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete restrict", "request teacher RESTRICT FK"),
        ("foreign key (school_id, request_id) references public.upload_requests (school_id, id) on delete set null (request_id)", "document request SET NULL FK"),
        ("foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete set null (teacher_id)", "document teacher SET NULL FK"),
        ("foreign key (school_id, event_id) references public.events (school_id, id) on delete cascade", "event child same-school FK"),
        ("foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete cascade", "event teacher same-school FK"),
        ("foreign key (school_id, actor_user_id) references public.school_memberships (school_id, user_id) on delete set null (actor_user_id)", "activity actor same-school FK"),
    ]:
        require(sql, fragment, label)

    for table in ("upload_requests", "events"):
        require(table_body(raw, table), "unique (school_id, id)", f"{table} composite reference key")

    for fragment, label in [
        ("status in ('waiting_upload', 'received', 'review', 'approved', 'needs_revision', 'late', 'cancelled')", "request status allowlist"),
        ("unique (token_hash)", "request token hash uniqueness"),
        ("storage_provider in ('supabase', 'google_drive', 'legacy_local')", "storage provider allowlist"),
        ("size_bytes >= 0", "file size integrity"),
        ("participant_count >= 0", "event participant count"),
        ("position >= 0", "event media position"),
    ]:
        require(sql, fragment, label)

    if "create unique index uq_event_media_one_cover_per_event on public.event_media (school_id, event_id) where is_cover" not in sql:
        fail("event media must enforce at most one cover per event")

    required_indexes = [
        "idx_school_settings_updated_by",
        "idx_upload_requests_scope", "idx_upload_requests_teacher", "idx_upload_requests_expires",
        "idx_documents_scope", "idx_documents_request", "idx_documents_teacher", "idx_documents_storage",
        "idx_events_scope", "idx_events_type",
        "idx_event_media_event", "uq_event_media_one_cover_per_event", "idx_event_media_storage",
        "idx_event_teacher_links_event", "idx_event_teacher_links_teacher",
        "idx_activities_created", "idx_activities_year", "idx_activities_actor", "idx_activities_entity",
    ]
    for index_name in required_indexes:
        if not re.search(rf"create\s+(?:unique\s+)?index\s+{re.escape(index_name)}\b", sql):
            fail(f"required S2-B4 index missing: {index_name}")

    for table in sorted(EXPECTED_TABLES):
        require(sql, f"revoke all on table public.{table} from public, anon, authenticated", f"deny-by-default {table}")
    for seq in ("upload_requests_id_seq", "documents_id_seq", "events_id_seq", "event_media_id_seq", "activities_id_seq"):
        require(sql, f"revoke all on sequence public.{seq} from public, anon, authenticated", f"deny-by-default {seq}")

    if not sql.startswith("begin;") or not sql.endswith("commit;"):
        fail("S2-B4 migration must use one explicit transaction")

    acceptance = compact(LIVE_ACCEPTANCE.read_text(encoding="utf-8"))
    for fragment in [
        "pass: s2-b4 live acceptance",
        "rollback;",
        "grantee in ('anon','authenticated')",
        "from pg_policies",
        "c.relrowsecurity",
        "v_rls_count not in (0, 7)",
        "exception when foreign_key_violation",
        "exception when check_violation",
        "exception when unique_violation",
        "school_settings_updated_by_fk",
        "documents_request_fk",
        "upload_requests_teacher_fk",
    ]:
        require(acceptance, fragment, "S2-B4 live acceptance")
    for pattern, label in [
        (r"insert\s+into\s+auth\.", "auth mutation"),
        (r"update\s+auth\.", "auth mutation"),
        (r"delete\s+from\s+auth\.", "auth mutation"),
        (r"storage\.objects", "storage mutation"),
    ]:
        if re.search(pattern, acceptance, flags=re.I):
            fail(f"forbidden S2-B4 live-acceptance operation: {label}")

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW_FILE.read_text(encoding="utf-8")
    if workflow != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_b4.py" not in workflow:
        fail("CI does not execute S2-B4 contract")

    print("PASS: Marsad Phase S2-B4 content/intake domains migration contract")
    print("INFO: migrations=4 new_tables=7 frozen_target_tables_complete=26 same_school_fk=PASS")
    print("INFO: runtime_switch=0 data_migration=0 storage_bytes=0 rls_ddl=0 policies=0 deny_by_default=PASS")


if __name__ == "__main__":
    main()
