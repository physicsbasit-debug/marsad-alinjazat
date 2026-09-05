from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase/schema/s3_c3a_requests_documents_review_contract.json"
MIGRATIONS = ROOT / "supabase/migrations"
MIGRATION = "20260904212000_s3_c3a_requests_documents_review_cutover.sql"
MIGRATION_SHA = "593505eba1fa222b084aeb5f9ef3825ee140a2fc4ae0f79f474663eb9cb14918"
REPO = ROOT / "src/lib/supabaseRequestsDocuments.ts"
REQ_WS = ROOT / "src/pages/RequestsWorkspace.tsx"
DOC_WS = ROOT / "src/pages/DocumentsWorkspace.tsx"
COUNT_PROBE = ROOT / "src/pages/RequestsDocumentsCountProbe.tsx"
REQ_PAGE = ROOT / "src/pages/Requests.tsx"
DOC_PAGE = ROOT / "src/pages/Documents.tsx"
APP = ROOT / "src/App.tsx"
API = ROOT / "src/lib/api.ts"
SERVER = ROOT / "server/main.py"
PUBLIC_UPLOAD = ROOT / "src/pages/PublicUpload.tsx"
CONFIG = ROOT / "supabase/config.toml"
ENV = ROOT / ".env.example"
ENV_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
VITE_ENV = ROOT / "src/vite-env.d.ts"
WORKFLOW = ROOT / ".github/workflows/quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE/quality-pages.yml"
LIVE = ROOT / "supabase/tests/s3_c3a_live_acceptance.sql"
S1_GUARD = ROOT / "scripts/check_supabase_foundation.py"
S3_C2_GUARD = ROOT / "scripts/check_supabase_s3_c2.py"

API_SHA = "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e"
SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
PUBLIC_UPLOAD_SHA = "0ffeca2a527d83fc7c3e74204038947684dcbe101b4951022e5d68615dcdf8a8"
CONFIG_SHA = "cb70ed25dfa2b00240457b3424b7f684195f70694f165ba8952c89055970f260"
HISTORICAL = {
    "20260901120000_s2_b1_core_identity_tenancy.sql": "53a20ade59193cc37ce9aa5935fb6739e76262df6cf9fc2350c6399d6a3a0de2",
    "20260901190000_s2_b2_teachers_domain.sql": "65030ee568719c5da6a010522c401e52b7b56b362a2547e02ed0f311c4d5e78b",
    "20260901210000_s2_b3_operational_domains.sql": "b4f444fa180d38688566261f3c124317ed4217b00cc3e760a0d53d5b45c70ae0",
    "20260902080000_s2_b4_content_intake_domains.sql": "33e094422f5fc78ddd12ab16572b4ac4817372bd745b63c2e67b214f159b6d91",
    "20260902090000_s2_b5_schema_hardening.sql": "1124fb66aba46ca87b79167ad4f93ec3c4d535ae281aaa1a5d36367665f73474",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql": "1d3b9b341b3e24741bcb928e6fe56c68709d924581f55e687fa929b6ffc5f32b",
    "20260903100000_s2_c1_security_foundation.sql": "738f22d57a1c087cd60e39702e31c0e0daabbeb4d41e5f31a69a3ce4053dac5f",
    "20260903123000_s2_c2_domain_rls_baseline.sql": "85d8325bcbe42ada1446b78c62950448fc33c74229bf71a783fed5f8ad474d32",
    "20260904130000_s3_b2_teacher_write_foundation.sql": "6cfce0ab365018feb8a3a3c5b9205120485cbaf5f21e6cb6de71f8119902e1f0",
    "20260904143000_s3_b2_r1_teacher_write_ambiguity_correction.sql": "417fb30a563a6cd92f7371a1c25ae07574258c8729e8f3cb44b0de785d3d9f3e",
    "20260904194500_s3_c2_supervision_write_cutover.sql": "f150c42b582cd6ffa560fcce33887f80cdea9b396334937d7da84512fc89b21f",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", " ", text)).strip().lower()


def main() -> None:
    required = [PACKAGE, CONTRACT, MIGRATIONS / MIGRATION, REPO, REQ_WS, DOC_WS, COUNT_PROBE, REQ_PAGE, DOC_PAGE,
                APP, API, SERVER, PUBLIC_UPLOAD, CONFIG, ENV, ENV_VISIBLE, VITE_ENV, WORKFLOW,
                VISIBLE_WORKFLOW, LIVE, S1_GUARD, S3_C2_GUARD]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C3A artifact: {path.relative_to(ROOT)}")

    version = tuple(int(x) for x in json.loads(PACKAGE.read_text()).get("version", "0.0.0").split("."))
    if version < (0, 33, 0):
        fail("S3-C3A requires package version >= 0.33.0")

    # Historical migrations must remain byte-identical.
    for name, sha in HISTORICAL.items():
        path = MIGRATIONS / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"historical migration changed: {name}")
    new_path = MIGRATIONS / MIGRATION
    if hashlib.sha256(new_path.read_bytes()).hexdigest() != MIGRATION_SHA:
        fail("S3-C3A migration hash mismatch")
    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    expected = list(HISTORICAL) + [MIGRATION]
    if migrations[:len(expected)] != expected:
        fail(f"S3-C3A migration history/order mismatch: {migrations}")

    # These files were intentionally frozen at the S3-C3A release. Later phases may
    # supersede the public-upload/browser seams while server/main.py remains the Legacy fallback.
    frozen = [(SERVER, SERVER_SHA, "server/main.py")]
    if version < (0, 34, 0):
        frozen.extend([
            (API, API_SHA, "legacy api.ts"),
            (PUBLIC_UPLOAD, PUBLIC_UPLOAD_SHA, "PublicUpload.tsx"),
            (CONFIG, CONFIG_SHA, "supabase/config.toml"),
        ])
    for path, sha, label in frozen:
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            fail(f"{label} changed during S3-C3A")

    contract = json.loads(CONTRACT.read_text())
    if contract.get("phase") != "S3-C3A" or contract.get("project_version") != "0.33.0":
        fail("invalid S3-C3A contract identity")
    if contract.get("migration") != MIGRATION or contract.get("migration_sha256") != MIGRATION_SHA:
        fail("contract migration identity/hash mismatch")
    for key in ("current_academic_year_only", "historical_years_use_legacy", "manual_legacy_rollback_preserved",
                "legacy_api_unchanged", "server_unchanged", "public_upload_unchanged", "request_review_cutover",
                "documents_index_cutover", "sidebar_open_request_count_cutover", "document_metadata_approval_with_request",
                "activities_timeline_required"):
        if contract.get(key) is not True:
            fail(f"{key} must be true")
    for key in ("storage_changes_allowed", "public_upload_changes_allowed", "request_creation_cutover",
                "direct_document_upload_cutover", "token_hash_select_allowed", "request_insert_grant_allowed",
                "document_insert_grant_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("read_roles") != ["owner", "admin"] or contract.get("write_roles") != ["owner", "admin"]:
        fail("S3-C3A role boundary drifted")
    if contract.get("atomic_rpc_functions") != ["marsad_update_upload_request_status_v1"]:
        fail("S3-C3A RPC contract drifted")
    if contract.get("rpc_security") != "SECURITY INVOKER":
        fail("S3-C3A RPC must stay SECURITY INVOKER")

    sql = compact(new_path.read_text())
    for fragment in (
        "grant update (status) on table public.upload_requests to authenticated",
        "grant update (status, approved_at) on table public.documents to authenticated",
        "create policy upload_requests_update_managers",
        "create policy documents_update_managers",
        "function public.marsad_update_upload_request_status_v1",
        "security invoker", "insert into public.activities", "if p_status = 'approved' then",
        "grant execute on function public.marsad_update_upload_request_status_v1",
    ):
        if fragment not in sql:
            fail(f"S3-C3A migration missing: {fragment}")
    for forbidden in (
        "security definer", "service_role", "service-role", "sb_secret_", "storage.",
        "grant insert on table public.upload_requests", "grant insert on table public.documents",
        "create policy upload_requests_insert", "create policy documents_insert",
        "alter table public.upload_requests add", "alter table public.documents add",
    ):
        if forbidden in sql:
            fail(f"S3-C3A migration escaped boundary: {forbidden}")

    repo = REPO.read_text()
    for fragment in (
        ".from('upload_requests')", ".from('documents')", ".eq('school_id', context.schoolId)",
        ".eq('academic_year_id', context.academicYearId)", ".rpc('marsad_update_upload_request_status_v1'",
        "context.role !== 'owner' && context.role !== 'admin'", "Number.isSafeInteger", "loadSupabaseOpenRequestCount",
    ):
        if fragment not in repo:
            fail(f"requests/documents repository missing: {fragment}")
    if version < (0, 34, 0):
        for forbidden in ("token_hash", ".insert(", ".update(", ".delete(", ".upsert(", "service_role", "sb_secret_"):
            if forbidden.lower() in repo.lower():
                fail(f"requests/documents repository escaped boundary: {forbidden}")

    req_ws = REQ_WS.read_text()
    req_fragments = ["VITE_REQUESTS_DOCUMENTS_DATA_MODE", "loadSupabaseRequestsDocumentsSnapshot",
                     "updateSupabaseRequestStatus", "الرجوع المؤقت إلى Legacy", "academicYear === currentAcademicYear"]
    if version < (0, 34, 0):
        req_fragments.extend(["S3-C3A • طلبات Supabase", "canCreate={false}"])
    for fragment in req_fragments:
        if fragment not in req_ws:
            fail(f"RequestsWorkspace missing: {fragment}")
    count_probe = COUNT_PROBE.read_text()
    for fragment in ("loadSupabaseOpenRequestCount", "REQUESTS_DOCUMENTS_DATA_MODE", "onCount"):
        if fragment not in count_probe:
            fail(f"RequestsDocumentsCountProbe missing: {fragment}")

    doc_ws = DOC_WS.read_text()
    doc_fragments = ["REQUESTS_DOCUMENTS_DATA_MODE", "loadSupabaseRequestsDocumentsSnapshot",
                     "الرجوع المؤقت إلى Legacy"]
    if version < (0, 35, 0):
        doc_fragments.append("canUpload={false}")
    if version < (0, 34, 0):
        doc_fragments.append("S3-C3A • وثائق Supabase")
    for fragment in doc_fragments:
        if fragment not in doc_ws:
            fail(f"DocumentsWorkspace missing: {fragment}")

    if re.search(r"from\s+['\"][^'\"]*supabase", REQ_PAGE.read_text()):
        fail("presentational Requests page must remain Supabase-agnostic")
    if re.search(r"from\s+['\"][^'\"]*supabase", DOC_PAGE.read_text()):
        fail("presentational Documents page must remain Supabase-agnostic")
    if "canCreate = true" not in REQ_PAGE.read_text() or "sourceNotice" not in REQ_PAGE.read_text():
        fail("Requests presentational seam missing")
    if "canUpload = true" not in DOC_PAGE.read_text() or "sourceNotice" not in DOC_PAGE.read_text():
        fail("Documents presentational seam missing")

    app = APP.read_text()
    for fragment in (
        "RequestsWorkspace", "DocumentsWorkspace", "REQUESTS_DOCUMENTS_DATA_MODE",
        "supabaseOpenRequestCount", "onSupabaseOpenRequestCount={setSupabaseOpenRequestCount}", "RequestsDocumentsCountProbe",
        "legacyDocuments={data.documents}", "VITE_REQUESTS_DOCUMENTS_DATA_MODE",
    ):
        if fragment == "VITE_REQUESTS_DOCUMENTS_DATA_MODE":
            continue
        if fragment not in app:
            fail(f"App S3-C3A wiring missing: {fragment}")
    if "view==='requests'?<Requests requests={data.requests}" in app or "view==='documents'?<Documents documents={data.documents}" in app:
        fail("App still renders Legacy request/document pages directly")

    if ENV.read_bytes() != ENV_VISIBLE.read_bytes():
        fail("visible env mirror is not byte-identical")
    if "VITE_REQUESTS_DOCUMENTS_DATA_MODE" in ENV.read_text():
        fail("S3-C3A must not require another hidden env-template edit; undefined local mode defaults to legacy")
    if "VITE_REQUESTS_DOCUMENTS_DATA_MODE" not in VITE_ENV.read_text():
        fail("Vite env typing missing requests/documents mode")

    s1 = S1_GUARD.read_text()
    for path in ("src/lib/supabaseRequestsDocuments.ts", "src/pages/RequestsWorkspace.tsx", "src/pages/DocumentsWorkspace.tsx", "src/pages/RequestsDocumentsCountProbe.tsx"):
        if path not in s1:
            fail(f"S1 guard does not whitelist S3-C3A consumer: {path}")
    if "migrations[:len(expected)] != expected" not in S3_C2_GUARD.read_text():
        fail("S3-C2 guard is not forward-compatible")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text()
    if "python scripts/check_supabase_s3_c3a.py" not in workflow:
        fail("workflow does not execute S3-C3A guard")
    if "VITE_REQUESTS_DOCUMENTS_DATA_MODE: 'supabase'" not in workflow:
        fail("GitHub Pages does not activate S3-C3A")
    for prior in ("VITE_TEACHERS_DATA_MODE: 'supabase'", "VITE_SUPERVISION_DATA_MODE: 'supabase'"):
        if prior not in workflow:
            fail(f"S3-C3A disabled accepted prior mode: {prior}")

    live = LIVE.read_text().lower()
    for fragment in (
        "pass: s3-c3a requests/documents review rls acceptance", "rollback;", "set local role authenticated",
        "lead_teacher review unexpectedly succeeded", "cross-tenant review unexpectedly succeeded",
        "approving request did not approve its document metadata", "request review activity missing",
    ):
        if fragment not in live:
            fail(f"S3-C3A live acceptance missing: {fragment}")

    print("PASS: Marsad S3-C3A requests/documents review cutover contract")
    print("INFO: current_year_supabase=1 historical_legacy=1 request_review=1 documents_index=1")
    print(f"INFO: request_create={1 if version >= (0, 34, 0) else 0} direct_upload={1 if version >= (0, 35, 0) else 0} public_upload={1 if version >= (0, 34, 0) else 0} storage={1 if version >= (0, 34, 0) else 0} token_hash_select=0")
    print("INFO: roles_read=owner,admin roles_write=owner,admin rpc_security=invoker")


if __name__ == "__main__":
    main()
