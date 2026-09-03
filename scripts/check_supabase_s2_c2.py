from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
MIGRATIONS = ROOT / "supabase" / "migrations"
CONTRACT = ROOT / "supabase" / "schema" / "s2_c2_domain_rls_contract.json"
LIVE = ROOT / "supabase" / "tests" / "s2_c2_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
C2 = "20260903123000_s2_c2_domain_rls_baseline.sql"
C2_SHA = "85d8325bcbe42ada1446b78c62950448fc33c74229bf71a783fed5f8ad474d32"
HISTORICAL = {'20260901120000_s2_b1_core_identity_tenancy.sql': '53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2', '20260901190000_s2_b2_teachers_domain.sql': '65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b', '20260901210000_s2_b3_operational_domains.sql': 'b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0', '20260902080000_s2_b4_content_intake_domains.sql': '33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91', '20260902090000_s2_b5_schema_hardening.sql': '1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474', '20260903080000_s2_b5_fix1_updated_at_clock.sql': '1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b', '20260903100000_s2_c1_security_foundation.sql': '738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f'}
DOMAIN = {'meeting_attendees', 'achievement_action_metrics', 'activities', 'event_teacher_links', 'teachers', 'supervision_visits', 'event_media', 'events', 'curriculum_units', 'achievement_assessment_standards', 'achievement_actions', 'documents', 'supervision_actions', 'teacher_profiles', 'meeting_decisions', 'teacher_cv_items', 'meetings', 'upload_requests', 'teacher_years', 'curriculum_plans', 'achievement_assessments'}
LOCKED = {'event_media', 'upload_requests', 'activities', 'teacher_years', 'documents'}
WRITE_OPS = {'teachers': {'update', 'insert'}, 'teacher_profiles': {'update', 'insert'}, 'teacher_cv_items': {'delete', 'insert'}, 'events': {'update', 'insert'}, 'event_teacher_links': {'delete', 'insert'}, 'meetings': {'update', 'insert'}, 'meeting_attendees': {'delete', 'insert'}, 'meeting_decisions': {'delete', 'update', 'insert'}, 'curriculum_plans': {'update', 'insert'}, 'curriculum_units': {'delete', 'update', 'insert'}, 'supervision_visits': {'update', 'insert'}, 'supervision_actions': {'delete', 'update', 'insert'}, 'achievement_assessments': {'update', 'insert'}, 'achievement_assessment_standards': {'update', 'insert'}, 'achievement_actions': {'delete', 'update', 'insert'}, 'achievement_action_metrics': {'delete', 'update', 'insert'}}
EXPECTED_SEQUENCES = {'achievement_assessments_id_seq', 'events_id_seq', 'meeting_decisions_id_seq', 'supervision_actions_id_seq', 'curriculum_units_id_seq', 'teacher_cv_items_id_seq', 'supervision_visits_id_seq', 'teachers_id_seq', 'achievement_actions_id_seq', 'meetings_id_seq', 'curriculum_plans_id_seq'}


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
    for path in (PACKAGE, CONTRACT, LIVE, WORKFLOW, VISIBLE_WORKFLOW, MIGRATIONS / C2):
        if not path.exists():
            fail(f"missing S2-C2 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if parse_version(package.get("version", "0.0.0")) < (0, 23, 0):
        fail("S2-C2 requires package version >= 0.23.0")

    for name, sha in HISTORICAL.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical live migration changed: {name}")
    if hashlib.sha256((MIGRATIONS / C2).read_bytes()).hexdigest() != C2_SHA:
        fail("S2-C2 migration hash mismatch")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected_prefix = list(HISTORICAL) + [C2]
    if migrations[:len(expected_prefix)] != expected_prefix:
        fail(f"migration order mismatch: {migrations}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-C2" or contract.get("project_version") != "0.23.0":
        fail("invalid S2-C2 contract identity")
    if contract.get("migration") != C2 or contract.get("migration_sha256") != C2_SHA:
        fail("S2-C2 contract migration identity/hash mismatch")
    if contract.get("domain_table_count") != 21 or contract.get("new_policy_count") != 58:
        fail("S2-C2 domain/policy count changed")
    if set(contract.get("direct_browser_write_locked_tables", [])) != LOCKED:
        fail("S2-C2 locked write table set changed")
    if contract.get("domain_write_roles") != ["owner", "admin"]:
        fail("S2-C2 browser write roles must remain owner/admin only")
    if contract.get("lead_teacher_browser_writes_enabled") is not False:
        fail("lead_teacher school-wide writes must remain deferred")
    for key in ("public_upload_enabled","storage_policies_enabled","activity_browser_writes_enabled","runtime_switch_allowed","sqlite_data_migration_allowed","storage_bytes_migration_allowed","auth_user_mutation_allowed","service_secret_in_browser_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S2-C2")

    raw = (MIGRATIONS / C2).read_text(encoding="utf-8")
    sql = compact(raw)
    for fragment in (
        "create or replace function private.can_access_teacher_record(p_school_id uuid, p_teacher_id bigint)",
        "sm.role in ('owner', 'admin', 'lead_teacher')",
        "sm.role = 'teacher' and sm.teacher_id = p_teacher_id",
        "grant execute on function private.can_access_teacher_record(uuid, bigint) to authenticated",
    ):
        if compact(fragment) not in sql:
            fail(f"S2-C2 migration missing: {fragment}")

    if re.search(r"grant\s+[^;]+\s+to\s+anon\b", sql, re.I):
        fail("S2-C2 must not grant access to anon")
    if re.search(r"grant\s+(?:insert|update)\s+on\s+(?:table\s+)?public\.", sql, re.I):
        fail("S2-C2 INSERT/UPDATE must be column-scoped, never broad table grants")
    if "storage.objects" in sql or "storage.buckets" in sql or re.search(r"create\s+policy\s+[^;]+on\s+storage\.", sql, re.I):
        fail("storage policies are outside S2-C2")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", sql, re.I):
        fail("S2-C2 must not mutate auth users")
    if "raw_user_meta_data ->> 'role'" in sql:
        fail("user_metadata must not control authorization")
    if re.search(r"create\s+table\s+public\.", sql, re.I):
        fail("S2-C2 must not create public domain tables")

    enabled = set(re.findall(r"alter\s+table\s+public\.([a-z_][a-z0-9_]*)\s+enable\s+row\s+level\s+security", sql, re.I))
    if enabled != DOMAIN:
        fail(f"RLS enablement must cover exactly 21 domain tables: {sorted(enabled)}")

    policies = re.findall(r"create\s+policy\s+([a-z_][a-z0-9_]*)\s+on\s+public\.([a-z_][a-z0-9_]*)\s+for\s+(select|insert|update|delete)", sql, re.I)
    if len(policies) != 58:
        fail(f"expected 58 C2 policies, got {len(policies)}")
    select_tables = {table.lower() for _,table,op in policies if op.lower()=="select"}
    if select_tables != DOMAIN:
        fail("each domain table must have exactly one SELECT policy")
    actual_ops: dict[str,set[str]] = {name:set() for name in DOMAIN}
    for _,table,op in policies:
        op=op.lower(); table=table.lower()
        if op != "select": actual_ops[table].add(op)
    expected_ops = {k:set(v) for k,v in WRITE_OPS.items()}
    if {k:v for k,v in actual_ops.items() if v} != expected_ops:
        fail(f"write policy operation matrix changed: {actual_ops}")

    for table in LOCKED:
        if re.search(rf"grant\s+(?:insert|update|delete)[^;]*public\.{table}\b", sql, re.I):
            fail(f"locked table received browser write grant: {table}")

    seqs = set(re.findall(r"grant\s+usage\s+on\s+sequence\s+public\.([a-z_][a-z0-9_]*)\s+to\s+authenticated", sql, re.I))
    if seqs != EXPECTED_SEQUENCES:
        fail(f"identity sequence grant surface changed: {sorted(seqs)}")

    live = compact(LIVE.read_text(encoding="utf-8"))
    for fragment in (
        "pass: s2-c2 domain rls baseline acceptance",
        "expected 58 s2-c2 domain policies",
        "teacher private visibility expected 1",
        "viewer saw private teacher directory",
        "teacher saw manager-sensitive upload request",
        "lead_teacher received school-wide write power",
        "browser forged audit activity",
        "direct document metadata insert unexpectedly succeeded",
        "cross-school event insert unexpectedly succeeded",
        "set local role authenticated",
        "rollback;",
    ):
        if compact(fragment) not in live:
            fail(f"S2-C2 live acceptance missing: {fragment}")
    if re.search(r"(?:insert\s+into|update|delete\s+from)\s+auth\.", live, re.I):
        fail("S2-C2 live acceptance must not mutate auth.users")

    wf = WORKFLOW.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW.read_text(encoding="utf-8")
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_c2.py" not in wf:
        fail("CI does not execute S2-C2 guard")

    print("PASS: Marsad Phase S2-C2 domain RLS baseline contract")
    print("INFO: domain_tables=21 new_policies=58 total_policies=69 locked_writes=5")
    print("INFO: writes=owner/admin lead_teacher_write=0 anon_grants=0 storage_policies=0 runtime_switch=0")


if __name__ == "__main__":
    main()
