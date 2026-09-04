from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s2_e2_tenant_bootstrap_contract.json"
BOOTSTRAP = ROOT / "supabase" / "bootstrap" / "s2_e2_tenant_bootstrap_template.sql"
ACCEPTANCE = ROOT / "supabase" / "tests" / "s2_e2_tenant_rls_acceptance_template.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"
EXPECTED_MIGRATIONS = [
    "20260901120000_s2_b1_core_identity_tenancy.sql",
    "20260901190000_s2_b2_teachers_domain.sql",
    "20260901210000_s2_b3_operational_domains.sql",
    "20260902080000_s2_b4_content_intake_domains.sql",
    "20260902090000_s2_b5_schema_hardening.sql",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql",
    "20260903100000_s2_c1_security_foundation.sql",
    "20260903123000_s2_c2_domain_rls_baseline.sql",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    for path in (PACKAGE, CONTRACT, BOOTSTRAP, ACCEPTANCE, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S2-E2 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    try:
        version_tuple = tuple(int(part) for part in package.get("version", "0.0.0").split("."))
    except ValueError:
        fail("invalid package version")
    if version_tuple < (0, 26, 0):
        fail("S2-E2 requires package version >= 0.26.0")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS:
        fail("S2-E2 is tenant bootstrap data only and must not alter migration history")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-E2" or contract.get("project_version") != "0.26.0":
        fail("invalid S2-E2 contract identity")
    for key in (
        "schema_changes_allowed",
        "rls_changes_allowed",
        "runtime_switch_allowed",
        "auth_user_mutation_allowed",
        "domain_seed_data_allowed",
        "school_settings_seed_allowed",
        "sql_schema_migration_added",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("tenant_bootstrap_commit_allowed") is not True:
        fail("tenant bootstrap commit must be explicitly allowed")
    if contract.get("bootstrap_scope") != ["schools", "profiles", "school_memberships", "academic_years"]:
        fail("S2-E2 bootstrap scope drifted")
    year = contract.get("current_academic_year", {})
    if year != {"label": "2026/2027", "start_year": 2026, "end_year": 2027, "is_current": True}:
        fail("S2-E2 academic year contract drifted")
    if contract.get("privacy", {}).get("owner_email_in_repository") is not False:
        fail("owner email must never be committed")
    if contract.get("privacy", {}).get("live_personalized_sql_committed") is not False:
        fail("personalized live bootstrap must stay outside repository")
    if contract.get("safety", {}).get("acceptance_sql_must_rollback") is not True:
        fail("S2-E2 acceptance must rollback")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    if "python scripts/check_supabase_s2_e2.py" not in WORKFLOW.read_text(encoding="utf-8"):
        fail("CI does not execute S2-E2 guard")

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    lower_bootstrap = bootstrap.lower()
    for placeholder in ("__OWNER_EMAIL__", "__SCHOOL_NAME__"):
        if placeholder not in bootstrap:
            fail(f"bootstrap template missing privacy placeholder {placeholder}")
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", bootstrap, flags=re.IGNORECASE):
        fail("bootstrap template contains a real-looking email address")
    for fragment in (
        "PASS: S2-E2 production tenant bootstrap",
        "insert into public.profiles",
        "insert into public.schools",
        "insert into public.school_memberships",
        "insert into public.academic_years",
        "'owner'",
        "'active'",
        "'2026/2027'",
        "commit;",
    ):
        if fragment.lower() not in lower_bootstrap:
            fail(f"bootstrap template missing {fragment}")
    for forbidden in (
        "insert into auth.users",
        "update auth.users",
        "delete from auth.users",
        "insert into public.school_settings",
        "insert into public.teachers",
        "insert into public.meetings",
        "insert into public.documents",
        "insert into public.events",
        "create table",
        "alter table",
        "create policy",
        "drop policy",
    ):
        if forbidden in lower_bootstrap:
            fail(f"bootstrap template contains forbidden operation: {forbidden}")
    for safety_text in (
        "duplicate schools already exist",
        "owner membership exists with role/status",
        "another academic year is already current",
        "existing school is inactive",
    ):
        if safety_text.lower() not in lower_bootstrap:
            fail(f"bootstrap template lost safety gate: {safety_text}")

    acceptance = ACCEPTANCE.read_text(encoding="utf-8")
    lower_acceptance = acceptance.lower().strip()
    for placeholder in ("__OWNER_EMAIL__", "__SCHOOL_NAME__"):
        if placeholder not in acceptance:
            fail(f"acceptance template missing privacy placeholder {placeholder}")
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", acceptance, flags=re.IGNORECASE):
        fail("acceptance template contains a real-looking email address")
    if not lower_acceptance.startswith("-- marsad al-injazat"):
        fail("acceptance SQL header drifted")
    if not lower_acceptance.endswith("rollback;"):
        fail("S2-E2 acceptance must end with ROLLBACK")
    if re.search(r"(^|\s)commit\s*;", lower_acceptance):
        fail("COMMIT is forbidden in S2-E2 acceptance")
    for fragment in (
        "PASS: S2-E2 tenant RLS acceptance",
        "set local role authenticated",
        "request.jwt.claim.sub",
        "private.has_school_role",
        "owner cannot read own school",
        "non-member can read the real school",
        "update public.schools set name = name",
    ):
        if fragment.lower() not in lower_acceptance:
            fail(f"acceptance template missing {fragment}")

    print("PASS: Marsad S2-E2 production tenant bootstrap contract")
    print("INFO: schema_changes=0 rls_changes=0 runtime_switch=0 domain_seed_rows=0")
    print("INFO: bootstrap_scope=school+profile_projection+owner_membership+academic_year")
    print("INFO: owner_email_committed=0 school_settings_seeded=0 acceptance_rollback=1")


if __name__ == "__main__":
    main()
