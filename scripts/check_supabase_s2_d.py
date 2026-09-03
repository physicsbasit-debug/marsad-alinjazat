from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
TARGET = ROOT / "supabase" / "schema" / "target_schema_v1.json"
C2_CONTRACT = ROOT / "supabase" / "schema" / "s2_c2_domain_rls_contract.json"
CONTRACT = ROOT / "supabase" / "schema" / "s2_d_database_acceptance_contract.json"
MANIFEST = ROOT / "supabase" / "schema" / "s2_d_data_migration_manifest.json"
LIVE = ROOT / "supabase" / "tests" / "s2_d_live_acceptance.sql"
DBPY = ROOT / "server" / "db.py"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"
TARGET_SHA = "84ba44b8104d09d62095c4af00a40d413ddc78fb1b2b251af1487d439368ecda"
HISTORICAL = {
    "20260901120000_s2_b1_core_identity_tenancy.sql": "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    "20260901190000_s2_b2_teachers_domain.sql": "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    "20260901210000_s2_b3_operational_domains.sql": "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    "20260902080000_s2_b4_content_intake_domains.sql": "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    "20260902090000_s2_b5_schema_hardening.sql": "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql": "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b",
    "20260903100000_s2_c1_security_foundation.sql": "738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f",
    "20260903123000_s2_c2_domain_rls_baseline.sql": "85d8325bcbe42ada1446b78c62950448fc33c74229bf71a783fed5f8ad474d32",
}
FOLDED = {"request_record_years", "event_record_years", "teacher_record_years", "event_media_meta"}
YEAR_SCOPED = {"teacher_years", "upload_requests", "documents", "events", "meetings", "curriculum_plans", "supervision_visits", "achievement_assessments", "activities"}
ROLES = {"owner", "admin", "lead_teacher", "teacher", "viewer", "suspended"}


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
    for path in (PACKAGE, TARGET, C2_CONTRACT, CONTRACT, MANIFEST, LIVE, DBPY, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists():
            fail(f"missing S2-D file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    version = parse_version(package.get("version", "0.0.0"))
    if version < (0, 24, 0):
        fail("S2-D requires package version >= 0.24.0")

    if hashlib.sha256(TARGET.read_bytes()).hexdigest() != TARGET_SHA:
        fail("frozen S2-A target schema changed")

    for name, sha in HISTORICAL.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical live migration changed: {name}")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected_prefix = list(HISTORICAL)
    if migrations[: len(expected_prefix)] != expected_prefix:
        fail(f"historical migration order changed: {migrations}")
    if version == (0, 24, 0) and migrations != expected_prefix:
        fail("S2-D v0.24.0 is acceptance-only and must not add a SQL migration")

    target = json.loads(TARGET.read_text(encoding="utf-8"))
    target_tables = [item["name"] for item in target["tables"]]
    source_from_freeze = [item["legacy"] for item in target["legacy_transformations"]]
    if len(target_tables) != 26 or len(set(target_tables)) != 26:
        fail("frozen target table count is not 26 unique tables")
    if len(source_from_freeze) != 25 or len(set(source_from_freeze)) != 25:
        fail("frozen legacy transformation coverage is not 25 unique tables")

    db_text = DBPY.read_text(encoding="utf-8")
    source_from_code: list[str] = []
    for match in re.finditer(r"CREATE TABLE IF NOT EXISTS\s+([a-z_][a-z0-9_]*)\s*\(", db_text, re.I):
        name = match.group(1).lower()
        if name not in source_from_code:
            source_from_code.append(name)
    if len(source_from_code) != 25 or set(source_from_code) != set(source_from_freeze):
        fail(f"legacy SQLite schema drifted from the frozen 25-table source: {source_from_code}")

    c2 = json.loads(C2_CONTRACT.read_text(encoding="utf-8"))
    if c2.get("live_acceptance_status") != "passed_live_2026-09-03":
        fail("S2-C2 must be recorded LIVE GREEN before S2-D")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("phase") != "S2-D" or manifest.get("project_version") != "0.24.0":
        fail("invalid S2-D migration manifest identity")
    if manifest.get("target_schema_sha256") != TARGET_SHA:
        fail("S2-D manifest target schema hash mismatch")
    if manifest.get("source_table_count") != 25 or set(manifest.get("source_tables", [])) != set(source_from_code):
        fail("S2-D manifest does not cover all 25 legacy source tables")
    if manifest.get("target_table_count") != 26 or set(manifest.get("target_tables", [])) != set(target_tables):
        fail("S2-D manifest does not cover all 26 target tables")
    if set(manifest.get("folded_legacy_tables", [])) != FOLDED:
        fail("S2-D folded legacy-table set changed")
    if manifest.get("legacy_transformations") != target["legacy_transformations"]:
        fail("S2-D legacy transformations diverged from S2-A freeze")

    staged_sources: list[str] = []
    for stage in manifest.get("load_stages", []):
        staged_sources.extend(stage.get("sources", []))
    if len(staged_sources) != 25 or set(staged_sources) != set(source_from_code):
        fail("S2-D load stages must cover each legacy source table exactly once")
    if manifest.get("row_audit_requirements", {}).get("no_silent_drop") is not True:
        fail("S2-D must prohibit silent row drops")
    if manifest.get("row_audit_requirements", {}).get("no_silent_duplicate_identity") is not True:
        fail("S2-D must prohibit silent teacher identity duplication")
    if manifest.get("storage_boundary", {}).get("file_bytes_migrated_in_s2_d") is not False:
        fail("S2-D must not migrate storage bytes")
    if manifest.get("security_boundary", {}).get("auth_users_mutated_in_s2_d") is not False:
        fail("S2-D must not mutate auth.users")
    if manifest.get("security_boundary", {}).get("rls_changed_in_s2_d") is not False:
        fail("S2-D must not change RLS")
    if "dry run only" not in manifest.get("readiness_gate", {}).get("meaning_of_pass", "").lower():
        fail("S2-D PASS meaning must be limited to data-migration dry-run readiness")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-D" or contract.get("project_version") != "0.24.0":
        fail("invalid S2-D contract identity")
    for key in ("sql_migration_added", "schema_changes_allowed", "rls_changes_allowed", "runtime_switch_allowed", "sqlite_data_migration_executed", "storage_bytes_migration_executed", "auth_user_mutation_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-D")
    if contract.get("target_table_count") != 26 or contract.get("source_table_count") != 25:
        fail("S2-D source/target table counts changed")
    if contract.get("expected_public_policy_count") != 69:
        fail("S2-D expected policy count changed")
    if contract.get("expected_updated_at_trigger_count") != 22:
        fail("S2-D expected updated_at trigger count changed")
    if set(contract.get("year_scoped_tables_checked", [])) != YEAR_SCOPED:
        fail("S2-D year-scoped acceptance coverage changed")
    if set(contract.get("roles_checked", [])) != ROLES:
        fail("S2-D role acceptance coverage changed")

    live_raw = LIVE.read_text(encoding="utf-8")
    live = compact(live_raw)
    required = (
        "pass: s2-d database acceptance and migration readiness",
        "expected 26 target tables",
        "expected rls on all 26 target tables",
        "expected 69 public policies",
        "expected 22 updated_at triggers",
        "clock_timestamp()",
        "historical teacher-year optional attributes",
        "duplicate current academic year accepted",
        "duplicate token_hash accepted",
        "second event cover accepted",
        "cross-school teacher/event link accepted",
        "invalid achievement bucket arithmetic accepted",
        "metric outcome without measured_at accepted",
        "invalid storage provider accepted",
        "document.request_id did not set null",
        "event children did not cascade",
        "referenced teacher deletion was not restricted",
        "cross-tenant rows leaked from table",
        "historical-year row missing from",
        "owner update/updated_at trigger did not advance",
        "viewer received write access",
        "teacher self-only directory rule failed",
        "lead_teacher received school-wide write power",
        "admin sensitive upload-request read failed",
        "suspended membership can still read school",
        "set local role authenticated",
        "rollback;",
    )
    for fragment in required:
        if compact(fragment) not in live:
            fail(f"S2-D live acceptance missing: {fragment}")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", live, re.I):
        fail("S2-D live acceptance must never mutate auth.users")
    if "storage.objects" in live or "storage.buckets" in live:
        fail("S2-D live acceptance must not mutate Supabase Storage")
    if live_raw.count("begin;") < 1 or live_raw.lower().count("rollback;") != 1:
        fail("S2-D live acceptance must be one rollback-protected transaction")

    # Validate literal INSERT/UPDATE column names against the frozen target contract.
    target_columns = {item["name"]: set(item["columns"]) for item in target["tables"]}
    for match in re.finditer(r"insert\s+into\s+public\.([a-z_][a-z0-9_]*)\s*\((.*?)\)\s*(?:values|select)", live_raw, re.I | re.S):
        table = match.group(1).lower()
        columns = [column.strip().lower() for column in match.group(2).split(",")]
        if table not in target_columns:
            fail(f"S2-D live acceptance inserts into unknown target table: {table}")
        invalid = [column for column in columns if column not in target_columns[table]]
        if invalid:
            fail(f"S2-D live acceptance has invalid INSERT columns on {table}: {invalid}")
    for match in re.finditer(r"update\s+public\.([a-z_][a-z0-9_]*)\s+set\s+([a-z_][a-z0-9_]*)\s*=", live_raw, re.I):
        table, column = match.group(1).lower(), match.group(2).lower()
        if table not in target_columns or column not in target_columns[table]:
            fail(f"S2-D live acceptance has invalid UPDATE column: {table}.{column}")

    wf = WORKFLOW.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW.read_text(encoding="utf-8")
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_d.py" not in wf:
        fail("CI does not execute S2-D guard")

    print("PASS: Marsad Phase S2-D database acceptance and migration readiness contract")
    print("INFO: source_tables=25 target_tables=26 policies=69 updated_at_triggers=22")
    print("INFO: acceptance_only=1 sql_migration=0 runtime_switch=0 storage_bytes=0")
    print("INFO: next_gate=controlled SQLite data-migration dry run")


if __name__ == "__main__":
    main()
