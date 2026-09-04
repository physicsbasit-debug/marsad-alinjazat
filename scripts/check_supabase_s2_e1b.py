from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s2_e1b_representative_dry_run_contract.json"
SQL = ROOT / "supabase" / "tests" / "s2_e1b_representative_dry_run.sql"
RECON = ROOT / "supabase" / "tests" / "s2_e1b_reconciliation.json"
REPORT = ROOT / "supabase" / "tests" / "s2_e1b_report.md"
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
    for path in (PACKAGE, CONTRACT, SQL, RECON, REPORT, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S2-E1B artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if package.get("version") != "0.25.1":
        fail("S2-E1B requires package version 0.25.1")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations != EXPECTED_MIGRATIONS:
        fail("S2-E1B must not add or alter schema migration history")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-E1B" or contract.get("project_version") != "0.25.1":
        fail("invalid S2-E1B contract identity")
    if contract.get("source_mode") != "deterministic_representative_fixture":
        fail("S2-E1B source mode drifted")
    if contract.get("source_table_count") != 25 or contract.get("target_table_count") != 26:
        fail("S2-E1B table counts drifted")
    if contract.get("fixture_source_row_count") != 26 or contract.get("target_expected_row_count") != 26:
        fail("S2-E1B fixture row counts drifted")
    for key in (
        "schema_changes_allowed",
        "rls_changes_allowed",
        "runtime_switch_allowed",
        "live_data_commit_allowed",
        "storage_bytes_migration_allowed",
        "auth_user_mutation_allowed",
        "sql_schema_migration_added",
    ):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("acceptance", {}).get("external_sqlite_snapshot_required") is not False:
        fail("S2-E1B must remain self-contained")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s2_e1b.py" not in workflow_text:
        fail("CI does not execute S2-E1B guard")

    sql = SQL.read_text(encoding="utf-8")
    lower = sql.lower().strip()
    if not lower.startswith("-- marsad al-injazat s2-e1"):
        fail("representative SQL header drifted")
    if not lower.endswith("rollback;"):
        fail("representative dry-run SQL must end with ROLLBACK")
    if re.search(r"(^|\s)commit\s*;", lower):
        fail("COMMIT is forbidden in representative dry-run SQL")
    for fragment in (
        "PASS: S2-E1 SQLite migration dry run",
        "insert into public.schools",
        "insert into public.teacher_years",
        "insert into public.event_media",
        "legacy_local",
        "google_drive",
        "S2-E1 reconciliation failed",
    ):
        if fragment.lower() not in lower:
            fail(f"representative SQL missing {fragment}")
    if "TOPSECRET" in sql or "google_refresh_token" in sql:
        fail("legacy secret material leaked into representative SQL")

    committed = json.loads(RECON.read_text(encoding="utf-8"))
    if committed.get("status") != "READY_FOR_SUPABASE_DRY_RUN":
        fail("committed reconciliation is not READY")
    if committed.get("source", {}).get("source_table_count") != 25:
        fail("committed reconciliation source table count drifted")
    if committed.get("source", {}).get("foreign_key_violations") != 0:
        fail("representative fixture has foreign-key violations")
    if committed.get("source_audit", {}).get("settings", {}).get("excluded_rows") != 1:
        fail("representative fixture no longer exercises secret exclusion")
    if committed.get("folded_relations", {}).get("event_media_meta", {}).get("unmatched_links") != 0:
        fail("event_media_meta fold is unmatched")
    if committed.get("transform_metrics", {}).get("storage_file_id_folded_to_storage_path", 0) < 1:
        fail("storage_file_id fold is no longer exercised")
    expected_counts = committed.get("target_expected_counts", {})
    if len(expected_counts) != 26 or sum(expected_counts.values()) != 26:
        fail("representative target reconciliation must cover 26 target tables / 26 expected rows")
    if expected_counts.get("profiles") != 0 or expected_counts.get("school_memberships") != 0:
        fail("Auth profiles/memberships must remain outside SQLite migration")
    if expected_counts.get("teacher_years") != 2 or expected_counts.get("academic_years") != 2:
        fail("current + historical year coverage drifted")

    report_text = REPORT.read_text(encoding="utf-8")
    for fragment in (
        "Source tables: **25/25**",
        "Target tables represented in dry run: **24/26**",
        "Secret settings excluded with audit trail: **1**",
        "Storage bytes moved: **No**",
        "Live commit: **No**",
        "PASS: S2-E1 SQLite migration dry run",
    ):
        if fragment not in report_text:
            fail(f"representative report missing {fragment}")

    # Regenerate the same logical fixture in CI and compare semantic reconciliation.
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_supabase_s2_e1 import create_fixture  # noqa: PLC0415
    from marsad_sqlite_migration_compiler import compile_database  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="marsad-s2e1b-") as temp:
        temp_root = Path(temp)
        db = create_fixture(temp_root / "fixture")
        generated = compile_database(db, temp_root / "out", "مدرسة مرصد الاختبار التمثيلي", "2026/2027")

    semantic_keys = (
        "source_audit",
        "folded_relations",
        "academic_years",
        "transform_metrics",
        "target_expected_counts",
        "boundaries",
    )
    for key in semantic_keys:
        if generated.get(key) != committed.get(key):
            fail(f"regenerated fixture semantic output drifted: {key}")
    if generated.get("status") != committed.get("status"):
        fail("regenerated fixture readiness status drifted")
    if generated.get("dry_run", {}).get("current_academic_year") != "2026/2027":
        fail("representative academic year drifted")

    print("PASS: Marsad S2-E1B representative legacy dry-run pack")
    print("INFO: source_tables=25 target_tables=26 fixture_rows=26 target_rows=26")
    print("INFO: external_sqlite=0 schema_changes=0 rls_changes=0 live_commit=0")


if __name__ == "__main__":
    main()
