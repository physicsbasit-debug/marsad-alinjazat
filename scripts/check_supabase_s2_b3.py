from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "package.json"
TARGET_CONTRACT = ROOT / "supabase" / "schema" / "target_schema_v1.json"
PHASE_CONTRACT = ROOT / "supabase" / "schema" / "s2_b3_operational_contract.json"
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
LIVE_ACCEPTANCE = ROOT / "supabase" / "tests" / "s2_b3_live_acceptance.sql"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW_FILE = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

B1_MIGRATION = "20260901120000_s2_b1_core_identity_tenancy.sql"
B2_MIGRATION = "20260901190000_s2_b2_teachers_domain.sql"
B3_MIGRATION = "20260901210000_s2_b3_operational_domains.sql"
EXPECTED_TARGET_SHA256 = "84ba44b8104d09d62095c4af00a40d413ddc78fb1b2b251af1487d439368ecda"
EXPECTED_B1_SHA256 = "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2"
EXPECTED_B2_SHA256 = "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b"
EXPECTED_B3_SHA256 = "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0"
EXPECTED_TABLES = {
    "meetings", "meeting_attendees", "meeting_decisions",
    "curriculum_plans", "curriculum_units",
    "supervision_visits", "supervision_actions",
    "achievement_assessments", "achievement_assessment_standards",
    "achievement_actions", "achievement_action_metrics",
}


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
    required = [PACKAGE_FILE, TARGET_CONTRACT, PHASE_CONTRACT, LIVE_ACCEPTANCE, WORKFLOW_FILE, VISIBLE_WORKFLOW_FILE]
    for path in required:
        if not path.exists():
            fail(f"required S2-B3 file missing: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    if package.get("version") != "0.19.0":
        fail("S2-B3 package version must be 0.19.0")

    if hashlib.sha256(TARGET_CONTRACT.read_bytes()).hexdigest() != EXPECTED_TARGET_SHA256:
        fail("S2-A frozen target schema changed during S2-B3")

    migration_paths = [MIGRATIONS_DIR / name for name in (B1_MIGRATION, B2_MIGRATION, B3_MIGRATION)]
    if not all(path.exists() for path in migration_paths):
        fail("S2-B1, S2-B2, and S2-B3 migrations must all exist")
    expected_hashes = [EXPECTED_B1_SHA256, EXPECTED_B2_SHA256, EXPECTED_B3_SHA256]
    for path, expected_hash in zip(migration_paths, expected_hashes):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            fail(f"migration changed unexpectedly: {path.name}")
    migrations = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    if migrations != [B1_MIGRATION, B2_MIGRATION, B3_MIGRATION]:
        fail(f"unexpected migration set for S2-B3: {migrations}")

    contract = json.loads(PHASE_CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-B3" or contract.get("project_version") != "0.19.0":
        fail("invalid S2-B3 phase contract identity")
    if contract.get("frozen_schema_contract_sha256") != EXPECTED_TARGET_SHA256:
        fail("S2-B3 contract is not pinned to S2-A")
    if contract.get("migration_sha256") != EXPECTED_B3_SHA256:
        fail("S2-B3 contract migration hash is wrong")
    if set(contract.get("new_tables", [])) != EXPECTED_TABLES:
        fail("S2-B3 contract table set changed")
    for key in ("runtime_switch_allowed", "data_migration_allowed", "rls_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-B3")
    if contract.get("deny_by_default_until_s2_c") is not True:
        fail("S2-B3 must remain deny-by-default")
    if contract.get("same_school_foreign_keys_required") is not True:
        fail("S2-B3 must enforce same-school foreign keys")

    target = json.loads(TARGET_CONTRACT.read_text(encoding="utf-8"))
    target_tables = {item["name"]: item for item in target["tables"]}
    missing_target = EXPECTED_TABLES - set(target_tables)
    if missing_target:
        fail(f"S2-A target schema lacks S2-B3 tables: {sorted(missing_target)}")

    raw = migration_paths[2].read_text(encoding="utf-8")
    sql = compact(raw)
    created = set(re.findall(r"create\s+table\s+public\.([a-z_][a-z0-9_]*)", sql))
    if created != EXPECTED_TABLES:
        fail(f"S2-B3 may create only operational-domain tables; got {sorted(created)}")

    for label, pattern in {
        "RLS enablement": r"enable\s+row\s+level\s+security",
        "RLS policy": r"create\s+policy",
        "runtime function": r"create\s+(?:or\s+replace\s+)?function",
        "application data insert": r"insert\s+into",
        "application data update": r"update\s+public\.",
        "application data delete": r"delete\s+from",
        "auth mutation": r"(?:insert\s+into|update|delete\s+from)\s+auth\.",
        "storage mutation": r"storage\.objects",
    }.items():
        if re.search(pattern, sql, flags=re.I):
            fail(f"forbidden S2-B3 SQL detected: {label}")

    # Every frozen target column must appear as a real column definition in the migration.
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

    required_fk_fragments = [
        "foreign key (school_id, academic_year_id) references public.academic_years (school_id, id) on delete restrict",
        "foreign key (school_id, meeting_id) references public.meetings (school_id, id) on delete cascade",
        "foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete cascade",
        "foreign key (school_id, responsible_teacher_id) references public.teachers (school_id, id) on delete set null (responsible_teacher_id)",
        "foreign key (school_id, owner_teacher_id) references public.teachers (school_id, id) on delete set null (owner_teacher_id)",
        "foreign key (school_id, plan_id) references public.curriculum_plans (school_id, id) on delete cascade",
        "foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete restrict",
        "foreign key (school_id, visit_id) references public.supervision_visits (school_id, id) on delete cascade",
        "foreign key (school_id, teacher_id) references public.teachers (school_id, id) on delete set null (teacher_id)",
        "foreign key (school_id, assessment_id) references public.achievement_assessments (school_id, id) on delete cascade",
        "foreign key (school_id, action_id) references public.achievement_actions (school_id, id) on delete cascade",
    ]
    for fragment in required_fk_fragments:
        require(sql, fragment, "same-school FK contract")

    for table in ("meetings", "curriculum_plans", "supervision_visits", "achievement_assessments", "achievement_actions"):
        require(table_body(raw, table), "unique (school_id, id)", f"{table} composite reference key")

    for fragment, label in [
        ("progress_percent between 0 and 100", "curriculum progress constraint"),
        ("mastered_count + near_mastery_count + intervention_count <= student_count", "assessment bucket total"),
        ("mastery_threshold_pct between 0 and 100", "mastery threshold"),
        ("direction in ('higher_better', 'lower_better')", "metric direction"),
        ("(outcome_value is null and measured_at is null) or (outcome_value is not null and measured_at is not null)", "metric measurement consistency"),
    ]:
        require(sql, fragment, label)

    required_indexes = [
        "idx_meetings_scope", "idx_meeting_attendees_meeting", "idx_meeting_attendees_teacher",
        "idx_meeting_decisions_meeting", "idx_meeting_decisions_responsible",
        "idx_curriculum_plans_scope", "idx_curriculum_plans_owner",
        "idx_curriculum_units_plan", "idx_curriculum_units_responsible",
        "idx_supervision_visits_scope", "idx_supervision_visits_teacher",
        "idx_supervision_actions_visit", "idx_supervision_actions_responsible",
        "idx_achievement_assessments_scope", "idx_achievement_assessments_teacher",
        "idx_achievement_assessment_standards_assessment",
        "idx_achievement_actions_assessment", "idx_achievement_actions_responsible",
        "idx_achievement_action_metrics_action",
    ]
    for index_name in required_indexes:
        if not re.search(rf"create\s+(?:unique\s+)?index\s+{re.escape(index_name)}\b", sql):
            fail(f"required FK/scope index missing: {index_name}")

    for table in sorted(EXPECTED_TABLES):
        require(sql, f"revoke all on table public.{table} from public, anon, authenticated", f"deny-by-default {table}")
    for seq in (
        "meetings_id_seq", "meeting_decisions_id_seq", "curriculum_plans_id_seq", "curriculum_units_id_seq",
        "supervision_visits_id_seq", "supervision_actions_id_seq", "achievement_assessments_id_seq",
        "achievement_actions_id_seq",
    ):
        require(sql, f"revoke all on sequence public.{seq} from public, anon, authenticated", f"deny-by-default {seq}")

    if not sql.startswith("begin;") or not sql.endswith("commit;"):
        fail("S2-B3 migration must use one explicit transaction")

    acceptance = compact(LIVE_ACCEPTANCE.read_text(encoding="utf-8"))
    for fragment in [
        "pass: s2-b3 live acceptance", "rollback;", "grantee in ('anon','authenticated')",
        "c.relrowsecurity", "exception when foreign_key_violation", "exception when check_violation",
        "on delete set null (responsible_teacher_id)",
    ]:
        require(acceptance, fragment, "S2-B3 live acceptance")
    for pattern, label in [
        (r"insert\s+into\s+auth\.", "auth mutation"),
        (r"update\s+auth\.", "auth mutation"),
        (r"delete\s+from\s+auth\.", "auth mutation"),
        (r"storage\.objects", "storage mutation"),
    ]:
        if re.search(pattern, acceptance, flags=re.I):
            fail(f"forbidden live-acceptance operation: {label}")

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW_FILE.read_text(encoding="utf-8")
    if workflow != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_b3.py" not in workflow:
        fail("CI does not execute S2-B3 contract")

    print("PASS: Marsad Phase S2-B3 operational domains migration contract")
    print("INFO: migrations=3 new_tables=11 domains=4 same_school_fk=PASS")
    print("INFO: runtime_switch=0 data_migration=0 rls=0 deny_by_default=PASS frozen_schema=PASS")


if __name__ == "__main__":
    main()
