from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
LIVE = ROOT / "supabase" / "tests" / "s2_d_live_acceptance.sql"
CONTRACT = ROOT / "supabase" / "schema" / "s2_d_fix1_acceptance_contract.json"
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
    for path in (PACKAGE, LIVE, CONTRACT, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists():
            fail(f"missing S2-D Fix 1 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    raw_version = package.get("version", "0.0.0")
    try:
        version = tuple(int(part) for part in raw_version.split("."))
    except ValueError:
        fail(f"invalid package version: {raw_version}")
    if version < (0, 24, 1):
        fail("S2-D Fix 1 requires package version >= 0.24.1")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations[:len(EXPECTED_MIGRATIONS)] != EXPECTED_MIGRATIONS:
        fail("S2-D Fix 1 is acceptance-only and must not add/change migration filenames")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-D Fix 1" or contract.get("project_version") != "0.24.1":
        fail("invalid S2-D Fix 1 contract identity")
    for key in (
        "schema_changes_allowed",
        "rls_changes_allowed",
        "sql_migration_added",
        "runtime_switch_allowed",
        "sqlite_data_migration_executed",
        "storage_bytes_migration_executed",
        "auth_user_mutation_allowed",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("temporary_fixture_cleanup_required") is not True:
        fail("temporary fixture cleanup must be required")
    if contract.get("expected_teacher_document_count") != 2 or contract.get("expected_lead_teacher_document_count") != 2:
        fail("role document expectations changed")

    live_raw = LIVE.read_text(encoding="utf-8")
    live_sha = hashlib.sha256(LIVE.read_bytes()).hexdigest()
    if contract.get("live_acceptance_sha256") != live_sha:
        fail("live acceptance hash does not match S2-D Fix 1 contract")

    proof = "document.request_id did not SET NULL"
    cleanup = "delete from public.documents where id=v_doc;"
    cleanup_check = "temporary SET NULL document cleanup failed"
    teacher = "teacher own document visibility failed"
    lead = "lead_teacher private document read failed"
    for fragment in (proof, cleanup, cleanup_check, teacher, lead, "PASS: S2-D database acceptance and migration readiness", "rollback;"):
        if fragment.lower() not in live_raw.lower():
            fail(f"live acceptance missing required fragment: {fragment}")

    pos_proof = live_raw.lower().index(proof.lower())
    pos_cleanup = live_raw.lower().index(cleanup.lower())
    pos_teacher = live_raw.lower().index(teacher.lower())
    if not (pos_proof < pos_cleanup < pos_teacher):
        fail("temporary SET NULL document must be cleaned after proof and before role visibility assertions")

    if "select count(*) from public.documents where school_id=s_a) <> 2" not in live_raw:
        fail("teacher/lead document visibility baseline no longer expects the two canonical documents")

    wf = WORKFLOW.read_bytes()
    visible = VISIBLE_WORKFLOW.read_bytes()
    if wf != visible:
        fail("visible workflow copy is not byte-identical")
    wf_text = wf.decode("utf-8")
    if "python scripts/check_supabase_s2_d_fix1.py" not in wf_text:
        fail("CI does not execute S2-D Fix 1 guard")

    print("PASS: Marsad S2-D Fix 1 acceptance fixture correction")
    print("INFO: schema_changes=0 rls_changes=0 migrations_added=0 runtime_switch=0")
    print("INFO: temporary_set_null_document_cleanup=1 canonical_teacher_documents=2")


if __name__ == "__main__":
    main()
