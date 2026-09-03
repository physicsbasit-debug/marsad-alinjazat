from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
FIX = "20260903080000_s2_b5_fix1_updated_at_clock.sql"
FIX_SHA = "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b"
B5 = "20260902090000_s2_b5_schema_hardening.sql"
B5_SHA = "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474"
CONTRACT = ROOT / "supabase" / "schema" / "s2_b5_fix1_updated_at_contract.json"
LIVE = ROOT / "supabase" / "tests" / "s2_b5_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"


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
    for path in (PACKAGE, CONTRACT, LIVE, WORKFLOW, VISIBLE_WORKFLOW, MIGRATIONS / FIX, MIGRATIONS / B5):
        if not path.exists():
            fail(f"missing S2-B5 Fix 1 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if parse_version(package.get("version", "0.0.0")) < (0, 21, 1):
        fail("S2-B5 Fix 1 requires package version >= 0.21.1")

    if hashlib.sha256((MIGRATIONS / B5).read_bytes()).hexdigest() != B5_SHA:
        fail("historical S2-B5 migration must remain byte-identical after live application")
    if hashlib.sha256((MIGRATIONS / FIX).read_bytes()).hexdigest() != FIX_SHA:
        fail("S2-B5 Fix 1 migration hash mismatch")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if FIX not in migrations or migrations.index(FIX) <= migrations.index(B5):
        fail("S2-B5 Fix 1 must be a new migration after historical S2-B5")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-B5-Fix1" or contract.get("project_version") != "0.21.1":
        fail("invalid S2-B5 Fix 1 contract identity")
    if contract.get("migration") != FIX or contract.get("migration_sha256") != FIX_SHA:
        fail("S2-B5 Fix 1 contract migration identity/hash mismatch")
    if contract.get("function_clock") != "clock_timestamp()":
        fail("S2-B5 Fix 1 contract must require clock_timestamp()")
    if contract.get("historical_s2_b5_migration_mutated") is not False:
        fail("historical S2-B5 migration must not be rewritten")
    for key in ("runtime_switch_allowed", "data_migration_allowed", "storage_bytes_migration_allowed", "auth_user_creation_allowed", "rls_policy_creation_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")

    sql = compact((MIGRATIONS / FIX).read_text(encoding="utf-8"))
    required = (
        "begin;",
        "create or replace function public.set_row_updated_at()",
        "returns trigger",
        "language plpgsql",
        "set search_path = pg_catalog",
        "new.updated_at := clock_timestamp()",
        "revoke all on function public.set_row_updated_at() from public, anon, authenticated",
        "commit;",
    )
    for fragment in required:
        if compact(fragment) not in sql:
            fail(f"Fix 1 migration missing: {fragment}")
    if "statement_timestamp()" in sql:
        fail("Fix 1 must not retain statement_timestamp()")
    for label, pattern in {
        "table DDL": r"(?:create|alter|drop)\s+table",
        "trigger DDL": r"(?:create|alter|drop)\s+trigger",
        "index DDL": r"(?:create|drop)\s+(?:unique\s+)?index",
        "RLS policy": r"create\s+policy",
        "RLS enablement": r"enable\s+row\s+level\s+security",
        "application data insert": r"insert\s+into",
        "application data update": r"update\s+public\.",
        "application data delete": r"delete\s+from",
        "SECURITY DEFINER": r"security\s+definer",
    }.items():
        if re.search(pattern, sql, re.I):
            fail(f"forbidden Fix 1 SQL detected: {label}")

    live = compact(LIVE.read_text(encoding="utf-8"))
    for fragment in (
        "pass: s2-b5 final schema acceptance",
        "clock_timestamp",
        "updated_at did not advance",
        "pg_sleep(0.02)",
        "rollback;",
    ):
        if compact(fragment) not in live:
            fail(f"live acceptance missing Fix 1 proof: {fragment}")

    wf = WORKFLOW.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW.read_text(encoding="utf-8")
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_b5_fix1.py" not in wf:
        fail("CI does not execute S2-B5 Fix 1 guard")

    print("PASS: Marsad Phase S2-B5 Fix 1 updated_at clock contract")
    print("INFO: historical_b5_unchanged=1 clock=clock_timestamp triggers_reused=22")
    print("INFO: tables_changed=0 triggers_changed=0 indexes_changed=0 runtime_switch=0")


if __name__ == "__main__":
    main()
