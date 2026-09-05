from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
MIGRATIONS = ROOT / "supabase/migrations"
MIGRATION = "20260904223000_s3_c3b_public_intake_storage.sql"
MIGRATION_SHA = "b04095b94b21ba4c7ead56143b7b55db8812c83a7455e4288961dab3b3315c6c"
CONTRACT = ROOT / "supabase/schema/s3_c3b_public_intake_storage_contract.json"
EDGE = ROOT / "supabase/functions/marsad-public-upload/index.ts"
EDGE_SHA = "e99b38662d3e19fde831b9d429d83948007566054406d24a21eb60b38790e2f9"
CONFIG = ROOT / "supabase/config.toml"
REPO = ROOT / "src/lib/supabaseRequestsDocuments.ts"
API = ROOT / "src/lib/api.ts"
PUBLIC_BRIDGE = ROOT / "src/lib/supabasePublicUpload.ts"
PUBLIC_UPLOAD = ROOT / "src/pages/PublicUpload.tsx"
REQ_WS = ROOT / "src/pages/RequestsWorkspace.tsx"
DOC_WS = ROOT / "src/pages/DocumentsWorkspace.tsx"
DOC_PAGE = ROOT / "src/pages/Documents.tsx"
APP = ROOT / "src/App.tsx"
SERVER = ROOT / "server/main.py"
WORKFLOW = ROOT / ".github/workflows/quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE/quality-pages.yml"
LIVE = ROOT / "supabase/tests/s3_c3b_live_acceptance.sql"
APPLY = ROOT / "PHASE_S3_C3B_APPLY_AR.txt"
DOC = ROOT / "SUPABASE_PUBLIC_INTAKE_STORAGE_AR.md"
C3A_GUARD = ROOT / "scripts/check_supabase_s3_c3a.py"

SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
C3A_MIGRATION = "20260904212000_s3_c3a_requests_documents_review_cutover.sql"
C3A_MIGRATION_SHA = "593505eba1fa222b084aeb5f9ef3825ee140a2fc4ae0f79f474663eb9cb14918"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", " ", text)).strip().lower()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [PACKAGE, MIGRATIONS / MIGRATION, CONTRACT, EDGE, CONFIG, REPO, API, PUBLIC_BRIDGE, PUBLIC_UPLOAD,
                REQ_WS, DOC_WS, DOC_PAGE, APP, SERVER, WORKFLOW, VISIBLE_WORKFLOW, LIVE, APPLY, DOC, C3A_GUARD]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C3B artifact: {path.relative_to(ROOT)}")

    version = tuple(int(x) for x in json.loads(PACKAGE.read_text()).get("version", "0.0.0").split("."))
    if version < (0, 34, 0):
        fail("S3-C3B requires package version >= 0.34.0")

    if sha(SERVER) != SERVER_SHA:
        fail("Legacy server changed during S3-C3B")
    if sha(MIGRATIONS / C3A_MIGRATION) != C3A_MIGRATION_SHA:
        fail("S3-C3A migration changed during S3-C3B")
    if sha(MIGRATIONS / MIGRATION) != MIGRATION_SHA:
        fail("S3-C3B migration hash mismatch")
    # v0.34.2+ permits the bounded CORS-only Edge correction guarded by S3-C3B R2.
    if version < (0, 34, 2) and sha(EDGE) != EDGE_SHA:
        fail("S3-C3B Edge Function hash mismatch")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if MIGRATION not in migrations or migrations.index(MIGRATION) != migrations.index(C3A_MIGRATION) + 1:
        fail("S3-C3B migration must immediately follow S3-C3A")

    contract = json.loads(CONTRACT.read_text())
    expected_pairs = {
        "phase": "S3-C3B",
        "project_version": "0.34.0",
        "migration": MIGRATION,
        "migration_sha256": MIGRATION_SHA,
        "edge_function": "supabase/functions/marsad-public-upload/index.ts",
        "edge_function_sha256": EDGE_SHA,
        "bucket": "marsad-documents",
        "max_upload_bytes": 26214400,
        "token_random_bytes": 32,
        "token_storage": "sha256_only",
        "signed_url_seconds": 300,
        "registration_atomic_rpc": "marsad_register_public_upload_v1",
        "request_creation_rpc": "marsad_create_upload_request_v1",
    }
    for key, value in expected_pairs.items():
        if contract.get(key) != value:
            fail(f"contract mismatch: {key}")
    for key in ("current_academic_year_only", "historical_years_use_legacy", "manual_legacy_rollback_preserved",
                "legacy_server_unchanged", "request_creation_cutover", "public_upload_cutover", "supabase_storage_cutover",
                "orphan_cleanup_required", "workflow_visible_mirror_required", "live_acceptance_rollback_required"):
        if contract.get(key) is not True:
            fail(f"contract boolean must be true: {key}")
    for key in ("direct_document_upload_cutover", "bucket_public", "browser_secret_key_allowed", "browser_service_role_allowed"):
        if contract.get(key) is not False:
            fail(f"contract boolean must be false: {key}")
    if contract.get("manager_roles") != ["owner", "admin"]:
        fail("manager role boundary drifted")
    if contract.get("public_registration_rpc_roles") != ["service_role"]:
        fail("public registration RPC role boundary drifted")
    if contract.get("edge_verify_jwt") is not False:
        fail("public upload Edge Function must use verify_jwt=false")

    sql = compact((MIGRATIONS / MIGRATION).read_text())
    for fragment in (
        "insert into storage.buckets", "'marsad-documents'", "false", "26214400",
        "create policy marsad_documents_manager_select", "on storage.objects", "for select", "to authenticated",
        "function public.marsad_create_upload_request_v1", "security definer", "p_token_hash text",
        "request creation is limited to current academic year", "insert into public.activities",
        "function public.marsad_register_public_upload_v1", "security invoker", "storage path outside request scope",
        "grant execute on function public.marsad_register_public_upload_v1", "to service_role",
    ):
        if fragment not in sql:
            fail(f"S3-C3B migration missing: {fragment}")
    for forbidden in (
        "grant insert on table public.upload_requests to authenticated",
        "grant insert on table public.documents to authenticated",
        "create policy marsad_documents_public",
        "to anon using",
    ):
        if forbidden in sql:
            fail(f"S3-C3B migration escaped boundary: {forbidden}")

    config = CONFIG.read_text()
    if "[functions.marsad-public-upload]" not in config or "verify_jwt = false" not in config:
        fail("public Edge Function config/verify_jwt contract missing")

    edge = EDGE.read_text()
    for fragment in (
        "const BUCKET = 'marsad-documents'", "const MAX_BYTES = 25 * 1024 * 1024",
        "SUPABASE_SECRET_KEYS", "SUPABASE_SERVICE_ROLE_KEY", "sha256Hex(token)",
        ".storage.from(BUCKET).upload", ".rpc('marsad_register_public_upload_v1'",
        ".storage.from(BUCKET).remove([storagePath])", "status: 204",
    ):
        if fragment not in edge:
            fail(f"Edge Function missing: {fragment}")
    if version < (0, 34, 2) and "Access-Control-Allow-Origin" not in edge:
        fail("Edge Function missing legacy CORS origin header")
    if version >= (0, 34, 2) and "corsHeaders as supabaseCorsHeaders" not in edge:
        fail("S3-C3B R2 synchronized Supabase CORS headers missing")

    upload_pos = edge.find(".storage.from(BUCKET).upload")
    rpc_pos = edge.find(".rpc('marsad_register_public_upload_v1'")
    cleanup_pos = edge.find(".storage.from(BUCKET).remove([storagePath])")
    if not (0 <= upload_pos < rpc_pos < cleanup_pos):
        fail("orphan cleanup flow order is invalid")

    # Browser source must never contain server secrets or service-role credentials.
    browser_text = "\n".join(path.read_text(errors="ignore") for path in (ROOT / "src").rglob("*.ts*"))
    for forbidden in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEYS", "sb_secret_", "service_role"):
        if forbidden.lower() in browser_text.lower():
            fail(f"server credential leaked into browser source: {forbidden}")
    env_text = "\n".join(path.read_text(errors="ignore") for path in [ROOT / ".env.example", ROOT / "ENV_EXAMPLE_VISIBLE.txt"])
    for forbidden in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEYS", "sb_secret_"):
        if forbidden.lower() in env_text.lower():
            fail(f"server credential leaked into browser env template: {forbidden}")

    repo = REPO.read_text()
    for fragment in (
        "crypto.getRandomValues", "crypto.subtle.digest('SHA-256'", ".rpc('marsad_create_upload_request_v1'",
        ".from('marsad-documents')", ".createSignedUrl(document.storagePath, 300)",
        "context.role !== 'owner' && context.role !== 'admin'",
    ):
        if fragment not in repo:
            fail(f"requests/documents C3B repository missing: {fragment}")

    if sha(API) != "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e":
        fail("legacy api.ts changed during S3-C3B")
    public_bridge = PUBLIC_BRIDGE.read_text()
    for fragment in (
        ".functions.invoke('marsad-public-upload'", "getSupabasePublicUploadInfo",
        "uploadSupabasePublicFile", "body: form", "functionErrorMessage",
    ):
        if fragment not in public_bridge:
            fail(f"public Edge browser bridge missing: {fragment}")

    public_upload = PUBLIC_UPLOAD.read_text()
    for fragment in ("PUBLIC_UPLOAD_SUPABASE", "getSupabasePublicUploadInfo", "uploadSupabasePublicFile"):
        if fragment not in public_upload:
            fail(f"PublicUpload cutover missing: {fragment}")

    req_ws = REQ_WS.read_text()
    for fragment in ("createSupabaseUploadRequest", "canCreate", "S3-C3B • طلبات Supabase", "SupabaseRequestModal"):
        if fragment not in req_ws:
            fail(f"RequestsWorkspace C3B missing: {fragment}")
    doc_ws = DOC_WS.read_text()
    document_boundary_marker = "S3-C3C • وثائق Supabase" if version >= (0, 35, 0) else "S3-C3B • وثائق Supabase"
    for fragment in ("createSupabaseDocumentSignedUrl", "onOpenDocument={openDocument}", document_boundary_marker, "5 دقائق"):
        if fragment not in doc_ws:
            fail(f"DocumentsWorkspace C3B signed-open boundary missing: {fragment}")
    if "onOpenDocument?: (document: DocumentRecord) => Promise<void>" not in DOC_PAGE.read_text():
        fail("presentational Documents signed-open seam missing")
    if "إنشاء رابط الرفع متاح الآن من صفحة الطلبات عبر Supabase." not in APP.read_text():
        fail("App quick action did not acknowledge C3B request creation")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text()
    if "python scripts/check_supabase_s3_c3b.py" not in workflow:
        fail("workflow does not execute S3-C3B guard")
    if "VITE_REQUESTS_DOCUMENTS_DATA_MODE: 'supabase'" not in workflow:
        fail("GitHub Pages does not activate requests/documents Supabase mode")

    if "migrations[:len(expected)] != expected" not in C3A_GUARD.read_text():
        fail("S3-C3A guard is not forward-compatible")

    live = LIVE.read_text().lower()
    for fragment in (
        "pass: s3-c3b public intake and private storage acceptance", "rollback;",
        "private 25mb bucket contract missing", "request/token hash did not persist",
        "document metadata registration missing", "request did not transition to review",
        "public registration rpc exposed to browser roles",
    ):
        if fragment not in live:
            fail(f"S3-C3B live acceptance missing: {fragment}")
    if not live.rstrip().endswith("rollback;"):
        fail("S3-C3B live acceptance must end with ROLLBACK")

    print("PASS: Marsad S3-C3B public intake and private Storage contract")
    print("INFO: request_create=1 public_upload=1 private_storage=1 signed_url_seconds=300")
    print("INFO: token_raw_persisted=0 token_sha256_only=1 max_upload_mb=25 orphan_cleanup=1")
    print(f"INFO: direct_document_upload={1 if version >= (0, 35, 0) else 0} historical_legacy=1 browser_server_secret=0")


if __name__ == "__main__":
    main()
