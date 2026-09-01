from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "package.json"
TARGET_CONTRACT = ROOT / "supabase" / "schema" / "target_schema_v1.json"
PHASE_CONTRACT = ROOT / "supabase" / "schema" / "s2_b1_core_identity_contract.json"
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW_FILE = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

EXPECTED_MIGRATION = "20260901120000_s2_b1_core_identity_tenancy.sql"
EXPECTED_TABLES = {"schools", "profiles", "school_memberships", "academic_years"}
EXPECTED_TARGET_SHA256 = "84ba44b8104d09d62095c4af00a40d413ddc78fb1b2b251af1487d439368ecda"
EXPECTED_B1_SHA256 = "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def compact(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def table_body(sql: str, table: str) -> str:
    match = re.search(
        rf"create\s+table\s+public\.{re.escape(table)}\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        fail(f"missing CREATE TABLE public.{table}")
    return compact(match.group(1))


def require_all(haystack: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if compact(needle) not in haystack]
    if missing:
        fail(f"{label} is missing required SQL fragments: {missing}")


def main() -> None:
    for path in (PACKAGE_FILE, TARGET_CONTRACT, PHASE_CONTRACT, WORKFLOW_FILE, VISIBLE_WORKFLOW_FILE):
        if not path.exists():
            fail(f"required S2-B1 file is missing: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    version = package.get("version", "0.0.0")
    try:
        version_tuple = tuple(int(part) for part in version.split(".")[:3])
    except ValueError:
        fail(f"invalid package version: {version}")
    if version_tuple < (0, 17, 0):
        fail("S2-B1 requires package version >= 0.17.0")

    target_sha = hashlib.sha256(TARGET_CONTRACT.read_bytes()).hexdigest()
    if target_sha != EXPECTED_TARGET_SHA256:
        fail("S2-A frozen target schema changed during S2-B1")

    phase_contract = json.loads(PHASE_CONTRACT.read_text(encoding="utf-8"))
    if phase_contract.get("contract_version") != "1.0.0" or phase_contract.get("phase") != "S2-B1":
        fail("S2-B1 phase contract identity is invalid")
    if phase_contract.get("project_version") != "0.17.0":
        fail("S2-B1 phase contract must be stamped v0.17.0")
    if phase_contract.get("frozen_schema_contract_sha256") != EXPECTED_TARGET_SHA256:
        fail("S2-B1 contract is not pinned to the approved S2-A schema")
    if phase_contract.get("runtime_switch_allowed") is not False:
        fail("S2-B1 must not switch the runtime to Supabase")
    if phase_contract.get("data_migration_allowed") is not False:
        fail("S2-B1 must not migrate SQLite application data")
    if phase_contract.get("rls_allowed") is not False:
        fail("RLS implementation belongs to S2-C, not S2-B1")
    if phase_contract.get("deny_by_default_until_s2_c") is not True:
        fail("S2-B1 must be deny-by-default until RLS arrives")

    migrations = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    if EXPECTED_MIGRATION not in migrations:
        fail(f"approved S2-B1 migration is missing; got {migrations}")
    if phase_contract.get("migration") != EXPECTED_MIGRATION:
        fail("S2-B1 phase contract migration filename changed")

    migration_path = MIGRATIONS_DIR / EXPECTED_MIGRATION
    if hashlib.sha256(migration_path.read_bytes()).hexdigest() != EXPECTED_B1_SHA256:
        fail("approved S2-B1 migration changed after its live acceptance")
    raw_sql = migration_path.read_text(encoding="utf-8")
    sql = compact(raw_sql)

    created_tables = set(re.findall(r"create\s+table\s+public\.([a-z_][a-z0-9_]*)", sql))
    if created_tables != EXPECTED_TABLES:
        fail(f"S2-B1 may create only the four core tables; got {sorted(created_tables)}")

    forbidden = {
        "RLS enablement": r"enable\s+row\s+level\s+security",
        "RLS policy": r"create\s+policy",
        "runtime RPC": r"create\s+(?:or\s+replace\s+)?function",
        "application data insert": r"insert\s+into",
        "application data update": r"update\s+public\.",
        "application data delete": r"delete\s+from",
        "teachers table": r"create\s+table\s+public\.teachers\b",
        "storage object mutation": r"storage\.objects",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, sql, flags=re.IGNORECASE):
            fail(f"forbidden S2-B1 SQL detected: {label}")

    schools = table_body(raw_sql, "schools")
    require_all(
        schools,
        [
            "id uuid primary key default gen_random_uuid()",
            "name text not null",
            "is_active boolean not null default true",
            "created_at timestamptz not null default now()",
            "updated_at timestamptz not null default now()",
            "check (btrim(name) <> '')",
        ],
        "schools",
    )

    profiles = table_body(raw_sql, "profiles")
    require_all(
        profiles,
        [
            "id uuid primary key references auth.users(id) on delete cascade",
            "display_name text",
            "created_at timestamptz not null default now()",
            "updated_at timestamptz not null default now()",
        ],
        "profiles",
    )

    memberships = table_body(raw_sql, "school_memberships")
    require_all(
        memberships,
        [
            "school_id uuid not null references public.schools(id) on delete cascade",
            "user_id uuid not null references public.profiles(id) on delete cascade",
            "teacher_id bigint",
            "role text not null",
            "status text not null default 'active'",
            "primary key (school_id, user_id)",
            "role in ('owner', 'admin', 'lead_teacher', 'teacher', 'viewer')",
            "status in ('active', 'invited', 'suspended')",
        ],
        "school_memberships",
    )
    teacher_line = next((line.strip().lower() for line in raw_sql.splitlines() if line.strip().lower().startswith("teacher_id bigint")), "")
    if "references" in teacher_line:
        fail("teacher_id FK must remain deferred until S2-B2 creates public.teachers")

    academic = table_body(raw_sql, "academic_years")
    require_all(
        academic,
        [
            "id bigint generated by default as identity primary key",
            "school_id uuid not null references public.schools(id) on delete cascade",
            "label text not null",
            "start_year smallint not null",
            "end_year smallint not null",
            "is_current boolean not null default false",
            "check (end_year = start_year + 1)",
            "check (label ~ '^[0-9]{4}/[0-9]{4}$')",
            "label = start_year::text || '/' || end_year::text",
            "unique (school_id, label)",
            "unique (school_id, id)",
        ],
        "academic_years",
    )

    if "create unique index uq_academic_years_one_current_per_school on public.academic_years (school_id) where is_current" not in sql:
        fail("academic_years must enforce one current year per school with a partial unique index")
    if "create index idx_school_memberships_user_id on public.school_memberships (user_id)" not in sql:
        fail("school membership user lookup index is missing")
    if "create index idx_school_memberships_teacher_id on public.school_memberships (teacher_id) where teacher_id is not null" not in sql:
        fail("school membership teacher lookup index is missing")

    for table in sorted(EXPECTED_TABLES):
        revoke = f"revoke all on table public.{table} from public, anon, authenticated"
        if revoke not in sql:
            fail(f"deny-by-default revoke is missing for {table}")
    if "revoke all on sequence public.academic_years_id_seq from public, anon, authenticated" not in sql:
        fail("academic_years identity sequence is not denied to browser roles")

    if not sql.startswith("begin;") or not sql.endswith("commit;"):
        fail("S2-B1 migration must be wrapped in one explicit transaction")

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW_FILE.read_text(encoding="utf-8")
    if workflow != visible:
        fail("visible workflow copy is not byte-identical to .github workflow")
    if "python scripts/check_supabase_s2_b1.py" not in workflow:
        fail("CI does not execute the S2-B1 migration contract")

    print("PASS: Marsad Phase S2-B1 core identity and tenancy migration contract")
    print(f"INFO: migration_files={len(migrations)} s2_b1_created_tables=4 runtime_switch=0 data_migration=0 rls=0")
    print("INFO: deny_by_default=PASS teacher_fk_contract=S2-B2 frozen_schema=PASS")


if __name__ == "__main__":
    main()
