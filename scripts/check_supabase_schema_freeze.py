from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "supabase" / "schema" / "target_schema_v1.json"
PACKAGE_FILE = ROOT / "package.json"
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW_FILE = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
LEGACY_DB_FILE = ROOT / "server" / "db.py"

EXPECTED_LEGACY = {
    "settings",
    "teachers",
    "upload_requests",
    "documents",
    "events",
    "event_media",
    "activities",
    "teacher_profiles",
    "teacher_cv_items",
    "event_teacher_links",
    "event_media_meta",
    "meetings",
    "meeting_attendees",
    "meeting_decisions",
    "curriculum_plans",
    "curriculum_units",
    "supervision_visits",
    "supervision_actions",
    "achievement_assessments",
    "achievement_assessment_standards",
    "achievement_actions",
    "achievement_action_metrics",
    "request_record_years",
    "event_record_years",
    "teacher_record_years",
}

EXPECTED_TARGET = {
    "schools",
    "profiles",
    "school_memberships",
    "academic_years",
    "school_settings",
    "teachers",
    "teacher_profiles",
    "teacher_years",
    "teacher_cv_items",
    "upload_requests",
    "documents",
    "events",
    "event_media",
    "event_teacher_links",
    "activities",
    "meetings",
    "meeting_attendees",
    "meeting_decisions",
    "curriculum_plans",
    "curriculum_units",
    "supervision_visits",
    "supervision_actions",
    "achievement_assessments",
    "achievement_assessment_standards",
    "achievement_actions",
    "achievement_action_metrics",
}

EXPECTED_NEW = {"schools", "profiles", "school_memberships", "academic_years"}
EXPECTED_REMOVED = {
    "teacher_record_years",
    "request_record_years",
    "event_record_years",
    "event_media_meta",
}

EXPECTED_YEAR_SCOPED = {
    "teacher_years",
    "upload_requests",
    "documents",
    "events",
    "meetings",
    "curriculum_plans",
    "supervision_visits",
    "achievement_assessments",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    if not CONTRACT_FILE.exists():
        fail("target schema contract is missing")

    contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))

    if contract.get("contract_version") != "1.0.0":
        fail("S2-A schema contract_version must be 1.0.0")
    if contract.get("phase") != "S2-A":
        fail("schema contract must identify Phase S2-A")
    if contract.get("project_version") != "0.16.0":
        fail("frozen S2-A schema contract must remain stamped v0.16.0")
    try:
        current_version = tuple(int(part) for part in package.get("version", "0.0.0").split(".")[:3])
    except ValueError:
        fail("package version is invalid")
    if current_version < (0, 16, 0):
        fail("current package cannot predate the frozen S2-A contract")

    tables = contract.get("tables") or []
    table_names = {item.get("name") for item in tables}
    if len(tables) != 26 or table_names != EXPECTED_TARGET:
        fail(f"target schema must contain exactly 26 frozen tables; got {len(tables)}")

    if contract.get("target", {}).get("target_table_count") != 26:
        fail("target_table_count must be 26")
    if contract.get("source", {}).get("legacy_table_count") != 25:
        fail("legacy_table_count must remain 25")
    if contract.get("target", {}).get("runtime_switch_allowed") is not False:
        fail("S2-A must not allow a runtime switch")
    if contract.get("target", {}).get("sql_migrations_allowed") is not False:
        fail("S2-A must not allow application SQL migrations")

    transformations = contract.get("legacy_transformations") or []
    legacy_names = [item.get("legacy") for item in transformations]
    if len(transformations) != 25 or set(legacy_names) != EXPECTED_LEGACY:
        fail("every one of the 25 legacy tables must have one explicit transformation rule")
    if len(legacy_names) != len(set(legacy_names)):
        fail("legacy transformation list contains duplicate source tables")

    new_names = {item.get("name") for item in contract.get("new_tables") or []}
    if new_names != EXPECTED_NEW:
        fail(f"new target tables changed unexpectedly: {sorted(new_names)}")
    removed_names = set(contract.get("removed_legacy_tables") or [])
    if removed_names != EXPECTED_REMOVED:
        fail(f"legacy tables marked for removal changed unexpectedly: {sorted(removed_names)}")

    table_map = {item["name"]: item for item in tables}
    for name, spec in table_map.items():
        columns = spec.get("columns") or []
        column_types = spec.get("column_types") or {}
        if set(columns) != set(column_types):
            fail(f"column type contract does not exactly cover {name}")
        if spec.get("tenant_owned"):
            if "school_id" not in columns:
                fail(f"tenant-owned table lacks direct school_id: {name}")
            if column_types.get("school_id") != "uuid":
                fail(f"tenant school_id must be uuid: {name}")
        if spec.get("year_scoped"):
            if "academic_year_id" not in columns:
                fail(f"year-scoped table lacks academic_year_id: {name}")
            if column_types.get("academic_year_id") != "bigint":
                fail(f"academic_year_id must be bigint: {name}")

    actual_year_scoped = {name for name, spec in table_map.items() if spec.get("year_scoped")}
    if actual_year_scoped != EXPECTED_YEAR_SCOPED:
        fail(f"year-scoped table set changed unexpectedly: {sorted(actual_year_scoped)}")

    if table_map["profiles"].get("pk") != "id uuid -> auth.users.id":
        fail("profiles must remain bound to auth.users primary key")
    membership_columns = set(table_map["school_memberships"].get("columns") or [])
    if "teacher_id" not in membership_columns:
        fail("school_memberships must preserve optional teacher account linkage")
    if table_map["teachers"].get("pk") != "id bigint identity":
        fail("teacher IDs must remain bigint identities for legacy/API parity")
    if table_map["teacher_years"].get("pk") != "(school_id,academic_year_id,teacher_id)":
        fail("teacher_years composite identity changed")
    if table_map["achievement_action_metrics"].get("column_types", {}).get("measured_at") != "date":
        fail("achievement metric measured_at must remain a calendar date")
    if table_map["meetings"].get("column_types", {}).get("meeting_time") != "time without time zone":
        fail("meeting_time must remain time without time zone")
    if table_map["achievement_assessments"].get("column_types", {}).get("mastery_threshold_pct") != "numeric(5,2)":
        fail("mastery threshold PostgreSQL type changed")

    teacher_columns = set(table_map["teachers"].get("columns") or [])
    annual_columns = set(table_map["teacher_years"].get("columns") or [])
    for annual in {"subject", "experience_years", "workload", "grades", "responsibilities"}:
        if annual not in annual_columns:
            fail(f"teacher annual field missing from teacher_years: {annual}")
    if {"subject", "experience_years", "workload"} & teacher_columns:
        fail("annual teacher state leaked back into persistent teacher identity")

    secret_rule = contract.get("target", {}).get("security_design", {}).get("secret_rule", "")
    if "no OAuth refresh token" not in secret_rule or "service-role" not in secret_rule:
        fail("public-settings secret exclusion rule is missing")

    migration_files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    # S2-A itself had no migrations. Once the package advances to S2-B, this
    # checker becomes a historical freeze guard: it keeps the target contract
    # immutable while later phase-specific checks validate the migrations.
    if current_version < (0, 17, 0) and migration_files:
        fail(f"S2-A package must remain migration-free: {migration_files}")

    # Legacy schema must still exist untouched as the parity oracle during S2-A.
    legacy_text = LEGACY_DB_FILE.read_text(encoding="utf-8")
    for table in EXPECTED_LEGACY:
        if f"CREATE TABLE IF NOT EXISTS {table}" not in legacy_text:
            fail(f"legacy parity table disappeared during S2-A: {table}")

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW_FILE.read_text(encoding="utf-8")
    if workflow != visible:
        fail("visible workflow copy is not byte-identical to .github workflow")
    if "python scripts/check_supabase_schema_freeze.py" not in workflow:
        fail("CI does not execute the S2-A schema-freeze contract")

    print("PASS: Marsad Phase S2-A PostgreSQL schema design freeze")
    print("INFO: legacy_tables=25 target_tables=26 mapped_legacy_tables=25")
    print(f"INFO: runtime=FastAPI/SQLite sql_migrations={len(migration_files)} supabase_runtime_switch=0")
    print("INFO: tenant_boundary=school_id year_dimension=academic_years teacher_identity_split=PASS")


if __name__ == "__main__":
    main()
