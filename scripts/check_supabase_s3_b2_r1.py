from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s3_b2_r1_teacher_write_ambiguity_contract.json"
ORIGINAL = ROOT / "supabase" / "migrations" / "20260904130000_s3_b2_teacher_write_foundation.sql"
CORRECTION = ROOT / "supabase" / "migrations" / "20260904143000_s3_b2_r1_teacher_write_ambiguity_correction.sql"
LIVE = ROOT / "supabase" / "tests" / "s3_b2_r1_live_acceptance.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
ORIGINAL_SHA = "6cfce0ab365018feb8a3a3c5b9205120485cbaf5f21e6cb6de71f8119902e1f0"
CORRECTION_SHA = "417fb30a563a6cd92f7371a1c25ae07574258c8729e8f3cb44b0de785d3d9f3e"
LIVE_SHA = "c3c88f3a07b79d8a2b0e6b6f03e572b049a04c32f3b84016c4e67f748a9afd43"

def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")

def version_tuple(raw: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part) for part in raw.split("."))
    except ValueError:
        fail("invalid package version")
    if len(parts) != 3:
        fail("package version must be semantic x.y.z")
    return parts

def compact(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()

def main() -> None:
    for path in (PACKAGE, CONTRACT, ORIGINAL, CORRECTION, LIVE, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-B2R1 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if version_tuple(package.get("version", "0.0.0")) < (0, 29, 1):
        fail("S3-B2R1 requires package version >= 0.29.1")

    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != ORIGINAL_SHA:
        fail("historical S3-B2 migration changed")
    if hashlib.sha256(CORRECTION.read_bytes()).hexdigest() != CORRECTION_SHA:
        fail("S3-B2R1 correction migration hash mismatch")
    if hashlib.sha256(LIVE.read_bytes()).hexdigest() != LIVE_SHA:
        fail("S3-B2R1 live acceptance hash mismatch")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S3-B2R1" or contract.get("project_version") != "0.29.1":
        fail("invalid S3-B2R1 contract identity")
    if contract.get("correction_migration") != CORRECTION.name or contract.get("correction_migration_sha256") != CORRECTION_SHA:
        fail("correction migration identity drifted")
    for key in ("rls_changes_allowed", "grant_changes_allowed", "table_or_column_schema_changes_allowed", "operational_ui_cutover", "teacher_delete_enabled", "lead_teacher_write_enabled", "storage_changes_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false in S3-B2R1")
    if contract.get("function_signature_unchanged") is not True or contract.get("function_return_contract_unchanged") is not True:
        fail("function contract must remain unchanged")

    sql = compact(CORRECTION.read_text(encoding="utf-8"))
    required = (
        "create or replace function public.marsad_create_teacher_v1",
        "returns table(teacher_id bigint, linked_existing boolean)",
        "security invoker",
        "on conflict on constraint teacher_years_pkey do nothing",
        "return query select v_teacher_id, v_linked_existing",
    )
    for fragment in required:
        if compact(fragment) not in sql:
            fail(f"correction migration missing: {fragment}")
    forbidden = (
        "on conflict (school_id, academic_year_id, teacher_id)",
        "create table public.", "alter table public.", "create policy ", "drop policy ",
        "grant ", "revoke ", "security definer",
    )
    for fragment in forbidden:
        if fragment in sql:
            fail(f"correction migration contains forbidden scope: {fragment}")
    if "marsad_update_teacher_v1" in sql:
        fail("S3-B2R1 must not rewrite the unaffected update RPC")

    live = compact(LIVE.read_text(encoding="utf-8"))
    for fragment in (
        "pass: s3-b2r1 teacher write ambiguity correction",
        "on conflict on constraint teacher_years_pkey do nothing",
        "marsad_create_teacher_v1", "marsad_update_teacher_v1",
        "cross-tenant teacher create unexpectedly succeeded",
        "lead_teacher create unexpectedly succeeded",
        "root teacher delete unexpectedly succeeded",
        "rollback;",
    ):
        if compact(fragment) not in live:
            fail(f"S3-B2R1 live acceptance missing: {fragment}")
    if not live.endswith("rollback;"):
        fail("S3-B2R1 acceptance must end with ROLLBACK")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s3_b2_r1.py" not in workflow:
        fail("workflow does not execute S3-B2R1 guard")

    print("PASS: Marsad S3-B2R1 teacher write ambiguity correction contract")
    print("INFO: historical_s3_b2_immutable=1 correction_migration=1 schema=0 rls=0 grants=0")
    print("INFO: conflict_target=teacher_years_pkey operational_cutover=0")

if __name__ == "__main__":
    main()
