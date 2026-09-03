from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
TARGET = ROOT / "supabase" / "schema" / "target_schema_v1.json"
CONTRACT = ROOT / "supabase" / "schema" / "s2_b5_schema_closure_contract.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
LIVE = ROOT / "supabase" / "tests" / "s2_b5_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

B1 = "20260901120000_s2_b1_core_identity_tenancy.sql"
B2 = "20260901190000_s2_b2_teachers_domain.sql"
B3 = "20260901210000_s2_b3_operational_domains.sql"
B4 = "20260902080000_s2_b4_content_intake_domains.sql"
B5 = "20260902090000_s2_b5_schema_hardening.sql"
TARGET_SHA = "84ba44b8104d09d62095c4af00a40d413ddc78fb1b2b251af1487d439368ecda"
HASHES = {
    B1: "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    B2: "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    B3: "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    B4: "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    B5: "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
}
REMOVED_LEGACY = {"request_record_years", "event_record_years", "teacher_record_years", "event_media_meta"}
UPDATED_TABLES = [
    "schools", "profiles", "school_memberships", "academic_years", "school_settings",
    "teachers", "teacher_profiles", "teacher_years", "teacher_cv_items", "upload_requests",
    "events", "event_media", "meetings", "meeting_decisions", "curriculum_plans", "curriculum_units",
    "supervision_visits", "supervision_actions", "achievement_assessments",
    "achievement_assessment_standards", "achievement_actions", "achievement_action_metrics",
]
FINAL_INDEXES = {
    "idx_school_memberships_school_status_role",
    "idx_academic_years_school_start",
    "idx_teacher_cv_items_teacher_type",
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


def table_body(all_sql: str, table: str) -> str:
    m = re.search(rf"create\s+table\s+public\.{re.escape(table)}\s*\((.*?)\n\);", all_sql, re.I | re.S)
    if not m:
        fail(f"missing CREATE TABLE public.{table}")
    return m.group(1)


def type_ok(line: str, expected: str) -> bool:
    s = re.sub(r"\s+", " ", line.strip().lower())
    rest = s.split(" ", 1)[1] if " " in s else ""
    expected = expected.lower()
    if expected == "bigint identity":
        return bool(re.match(r"bigint\s+generated\s+by\s+default\s+as\s+identity\b", rest))
    return rest.startswith(expected)


def main() -> None:
    for path in (PACKAGE, TARGET, CONTRACT, LIVE, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists():
            fail(f"missing S2-B5 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if parse_version(package.get("version", "0.0.0")) < (0, 21, 0):
        fail("S2-B5 requires package version >= 0.21.0")

    if hashlib.sha256(TARGET.read_bytes()).hexdigest() != TARGET_SHA:
        fail("S2-A frozen target schema changed during S2-B5")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected = [B1, B2, B3, B4, B5]
    if len(migrations) < 5 or migrations[:5] != expected:
        fail(f"migration history must begin with approved S2-B1..B5 chain: {migrations}")
    for name, sha in HASHES.items():
        if hashlib.sha256((MIGRATIONS / name).read_bytes()).hexdigest() != sha:
            fail(f"approved migration changed unexpectedly: {name}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-B5" or contract.get("project_version") != "0.21.0":
        fail("invalid S2-B5 contract identity")
    if contract.get("frozen_schema_contract_sha256") != TARGET_SHA:
        fail("S2-B5 contract is not pinned to S2-A")
    if contract.get("migration") != B5 or contract.get("migration_sha256") != HASHES[B5]:
        fail("S2-B5 migration identity/hash mismatch")
    if contract.get("target_table_count") != 26 or contract.get("new_tables") != []:
        fail("S2-B5 must close 26 target tables without creating a new domain table")
    if set(contract.get("updated_at_trigger_tables", [])) != set(UPDATED_TABLES):
        fail("S2-B5 updated_at trigger table set changed")
    if set(contract.get("added_indexes", [])) != FINAL_INDEXES:
        fail("S2-B5 final index set changed")
    for key in (
        "runtime_switch_allowed", "data_migration_allowed", "storage_bytes_migration_allowed",
        "auth_user_creation_allowed", "rls_policy_creation_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-B5")
    if contract.get("browser_grants_before_s2_c") != 0 or contract.get("policies_before_s2_c") != 0:
        fail("S2-B5 must keep browser grants/policies at zero")
    if contract.get("raw_upload_token_forbidden") is not True or contract.get("secret_material_in_public_schema_forbidden") is not True:
        fail("S2-B5 public-schema secret/token guards must stay enabled")

    # Every S2-B1..B4 migration remains the frozen source of the 26 domain tables.
    sql_b1_b4 = "\n".join((MIGRATIONS / name).read_text(encoding="utf-8") for name in (B1, B2, B3, B4))
    sql_compact = compact(sql_b1_b4)
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    target_tables = {t["name"]: t for t in target["tables"]}
    created = re.findall(r"create\s+table\s+public\.([a-z_][a-z0-9_]*)", sql_compact)
    if len(created) != 26 or set(created) != set(target_tables):
        fail(f"frozen migration chain must create exactly 26 target tables; got count={len(created)} set={sorted(set(created))}")
    if set(created) & REMOVED_LEGACY:
        fail(f"removed legacy tables were recreated: {sorted(set(created) & REMOVED_LEGACY)}")

    # Exact target column names and declared PostgreSQL types across all 299 columns.
    actual_column_total = 0
    for table_name, table in target_tables.items():
        body = table_body(sql_b1_b4, table_name)
        found: dict[str, str] = {}
        expected_cols = set(table["columns"])
        for raw_line in body.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            token = stripped.split()[0].rstrip(",").strip('"').lower()
            if token in expected_cols and token not in found:
                found[token] = stripped
        if set(found) != expected_cols:
            fail(f"{table_name} column-name drift: expected={sorted(expected_cols)} found={sorted(found)}")
        for col, expected_type in table["column_types"].items():
            if not type_ok(found[col], expected_type):
                fail(f"{table_name}.{col} type drift: expected {expected_type}; line={found[col]}")
        actual_column_total += len(found)
    if actual_column_total != 299:
        fail(f"expected 299 frozen columns, found {actual_column_total}")

    # Generic static same-school FK audit for tenant-to-tenant public references.
    tenant_tables = {name for name, t in target_tables.items() if "school_id" in t["columns"]}
    for child in tenant_tables:
        body = table_body(sql_b1_b4, child)
        for m in re.finditer(
            r"foreign\s+key\s*\(([^)]*)\)\s*references\s+public\.([a-z_][a-z0-9_]*)\s*\(([^)]*)\)",
            body,
            re.I | re.S,
        ):
            child_cols = [x.strip().lower() for x in m.group(1).split(",")]
            parent = m.group(2).lower()
            parent_cols = [x.strip().lower() for x in m.group(3).split(",")]
            if parent in tenant_tables:
                if "school_id" not in child_cols or "school_id" not in parent_cols:
                    fail(f"unsafe tenant FK {child}->{parent}: school_id missing")
                if child_cols.index("school_id") != parent_cols.index("school_id"):
                    fail(f"unsafe tenant FK {child}->{parent}: school_id positions differ")

    # The deferred membership->teacher same-school FK lives in ALTER TABLE after teachers exists.
    if "foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete restrict" not in sql_compact:
        fail("school_memberships->teachers same-school FK missing")

    b5_raw = (MIGRATIONS / B5).read_text(encoding="utf-8")
    b5 = compact(b5_raw)
    if re.search(r"create\s+table", b5):
        fail("S2-B5 must not create domain tables")
    for label, pattern in {
        "RLS policy": r"create\s+policy",
        "RLS enablement": r"enable\s+row\s+level\s+security",
        "application insert": r"insert\s+into",
        "application update": r"update\s+public\.",
        "application delete": r"delete\s+from",
        "auth mutation": r"(?:insert\s+into|update|delete\s+from)\s+auth\.",
        "storage mutation": r"storage\.objects",
        "SECURITY DEFINER": r"security\s+definer",
    }.items():
        if re.search(pattern, b5, re.I):
            fail(f"forbidden S2-B5 SQL detected: {label}")

    for fragment in (
        "create or replace function public.set_row_updated_at()",
        "returns trigger",
        "language plpgsql",
        "set search_path = pg_catalog",
        "new.updated_at := statement_timestamp()",
        "revoke all on function public.set_row_updated_at() from public, anon, authenticated",
    ):
        if compact(fragment) not in b5:
            fail(f"S2-B5 trigger helper missing fragment: {fragment}")

    trigger_tables = set(re.findall(r"before\s+update\s+on\s+public\.([a-z_][a-z0-9_]*)\s+for\s+each\s+row\s+execute\s+function\s+public\.set_row_updated_at\(\)", b5))
    if trigger_tables != set(UPDATED_TABLES):
        fail(f"updated_at trigger set mismatch: {sorted(trigger_tables)}")
    trigger_names = re.findall(r"create\s+trigger\s+([a-z_][a-z0-9_]*)", b5)
    if len(trigger_names) != 22 or len(set(trigger_names)) != 22:
        fail(f"expected exactly 22 unique updated_at triggers, got {len(trigger_names)}")

    index_names = set(re.findall(r"create\s+(?:unique\s+)?index\s+([a-z_][a-z0-9_]*)", b5))
    if index_names != FINAL_INDEXES:
        fail(f"S2-B5 may add only the three approved final indexes; got {sorted(index_names)}")

    if not b5.startswith("begin;") or not b5.endswith("commit;"):
        fail("S2-B5 migration must be one explicit transaction")

    live = compact(LIVE.read_text(encoding="utf-8"))
    for fragment in (
        "pass: s2-b5 final schema acceptance",
        "rollback;",
        "v_column_count <> 299",
        "186981dda2d7dab6889068fba74dcb3e",
        "v_unsafe_fk_count <> 0",
        "v_trigger_count <> 22",
        "v_sequence_leak_count <> 0",
        "v_policy_count <> 0",
        "v_grant_count <> 0",
        "v_unvalidated_count <> 0",
        "v_invalid_index_count <> 0",
        "updated_at did not advance",
    ):
        if compact(fragment) not in live:
            fail(f"S2-B5 live acceptance missing: {fragment}")
    for pattern in (r"insert\s+into\s+auth\.", r"update\s+auth\.", r"delete\s+from\s+auth\.", r"storage\.objects"):
        if re.search(pattern, live, re.I):
            fail("S2-B5 live acceptance must not mutate auth/storage")

    wf = WORKFLOW.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW.read_text(encoding="utf-8")
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_b5.py" not in wf:
        fail("CI does not execute S2-B5 closure guard")

    print("PASS: Marsad Phase S2-B5 final schema closure contract")
    print("INFO: target_tables=26 target_columns=299 prior_migrations=4 hardening_migration=1")
    print("INFO: same_school_fk=AUDITED updated_at_triggers=22 final_indexes=3 browser_grants=0 policies=0")
    print("INFO: runtime_switch=0 data_migration=0 auth_mutation=0 storage_bytes=0")


if __name__ == "__main__":
    main()
