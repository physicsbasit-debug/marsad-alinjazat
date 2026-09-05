from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
EDGE = ROOT / "supabase/functions/marsad-direct-document-upload/index.ts"
PUBLIC_EDGE = ROOT / "supabase/functions/marsad-public-upload/index.ts"
CONFIG = ROOT / "supabase/config.toml"
MIGRATIONS = ROOT / "supabase/migrations"
BROWSER = ROOT / "src/lib/supabaseDocuments.ts"
DOC_PAGE = ROOT / "src/pages/Documents.tsx"
DOC_WS = ROOT / "src/pages/DocumentsWorkspace.tsx"
WORKFLOW = ROOT / ".github/workflows/quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE/quality-pages.yml"
CONTRACT = ROOT / "supabase/schema/s3_c3c_direct_document_upload_contract.json"
LIVE = ROOT / "supabase/tests/s3_c3c_live_acceptance.md"
APPLY = ROOT / "PHASE_S3_C3C_APPLY_AR.txt"
DOC = ROOT / "SUPABASE_DIRECT_DOCUMENT_UPLOAD_AR.md"

EDGE_SHA = "cb5bf9c06b05207503b873ece92b39ee25284e800af214e4ce25b337a41dc2d8"
PUBLIC_EDGE_SHA = "2de16a96ea97280dcf1b9470ab14c2133c7fb8c0deccf7aec579b87b4c681757"
CONFIG_SHA = "b93eff36ec1d976fa89d7467b9e1c21c5d9534a93ed2c197940b85c2d089e54c"
SERVER_SHA = "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444"
API_SHA = "587cd57dc148aae9107a0745c902b95ab7f34a878c185e8a70e21b50a66e9e4e"
C3B_MIGRATION = "20260904223000_s3_c3b_public_intake_storage.sql"
C3B_MIGRATION_SHA = "b04095b94b21ba4c7ead56143b7b55db8812c83a7455e4288961dab3b3315c6c"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [PACKAGE, EDGE, PUBLIC_EDGE, CONFIG, BROWSER, DOC_PAGE, DOC_WS, WORKFLOW,
                VISIBLE_WORKFLOW, CONTRACT, LIVE, APPLY, DOC]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C3C artifact: {path.relative_to(ROOT)}")

    version = tuple(int(x) for x in json.loads(PACKAGE.read_text()).get("version", "0.0.0").split("."))
    if version < (0, 35, 0):
        fail("S3-C3C requires package version >= 0.35.0")

    protected = {
        ROOT / "server/main.py": SERVER_SHA,
        ROOT / "src/lib/api.ts": API_SHA,
        PUBLIC_EDGE: PUBLIC_EDGE_SHA,
        CONFIG: CONFIG_SHA,
        MIGRATIONS / C3B_MIGRATION: C3B_MIGRATION_SHA,
    }
    for path, expected in protected.items():
        if sha(path) != expected:
            fail(f"protected pre-C3C artifact changed: {path.relative_to(ROOT)}")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if not migrations or migrations[-1] != C3B_MIGRATION:
        fail("S3-C3C must not add a database migration")

    if sha(EDGE) != EDGE_SHA:
        fail("S3-C3C Edge Function hash mismatch")

    contract = json.loads(CONTRACT.read_text())
    expected = {
        "phase": "S3-C3C",
        "project_version": "0.35.0",
        "edge_function": "supabase/functions/marsad-direct-document-upload/index.ts",
        "edge_function_name": "marsad-direct-document-upload",
        "edge_verify_jwt": True,
        "database_migration_required": False,
        "bucket": "marsad-documents",
        "bucket_public": False,
        "max_upload_bytes": 26214400,
        "current_academic_year_only": True,
        "manager_roles": ["owner", "admin"],
        "teacher_link_optional": True,
        "direct_document_status": "approved",
        "signed_url_seconds": 300,
        "browser_direct_documents_insert": False,
        "browser_direct_storage_insert": False,
        "browser_secret_key_allowed": False,
        "browser_service_role_allowed": False,
        "orphan_cleanup_required": True,
        "activity_record_required": True,
        "public_upload_flow_preserved": True,
        "legacy_fallback_preserved": True,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            fail(f"S3-C3C contract mismatch: {key}")

    edge = EDGE.read_text()
    for fragment in (
        "corsHeaders as supabaseCorsHeaders",
        "SUPABASE_PUBLISHABLE_KEYS",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SECRET_KEYS",
        "SUPABASE_SERVICE_ROLE_KEY",
        "auth.getUser(match[1])",
        ".from('school_memberships')",
        ".in('role', ['owner', 'admin'])",
        ".from('academic_years')",
        ".eq('is_current', true)",
        ".from('teacher_years')",
        ".storage.from(BUCKET).upload",
        ".from('documents')",
        "status: 'approved'",
        "approved_at: now",
        ".from('activities').insert",
        "rollbackCreatedDocument",
        ".storage.from(BUCKET).remove([storagePath])",
        "status: 204",
    ):
        if fragment not in edge:
            fail(f"S3-C3C Edge missing: {fragment}")
    if "const MAX_BYTES = 25 * 1024 * 1024" not in edge:
        fail("S3-C3C max file size drifted")
    if "`${schoolId}/${academicYearId}/direct/${objectName}`" not in edge:
        fail("S3-C3C storage path contract missing")

    # The direct function intentionally relies on Supabase's default verify_jwt=true.
    config = CONFIG.read_text()
    if "[functions.marsad-direct-document-upload]" in config and "verify_jwt = false" in config.split("[functions.marsad-direct-document-upload]", 1)[1].split("[", 1)[0]:
        fail("direct document Edge Function must not disable JWT verification")

    browser = BROWSER.read_text()
    for fragment in (
        "uploadSupabaseDirectDocument",
        ".functions.invoke('marsad-direct-document-upload'",
        "context.role !== 'owner' && context.role !== 'admin'",
        "form.append('schoolId', context.schoolId)",
        "form.append('academicYearId', String(context.academicYearId))",
    ):
        if fragment not in browser:
            fail(f"browser direct-upload bridge missing: {fragment}")
    for forbidden in ("SUPABASE_SECRET_KEYS", "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_", ".from('documents').insert", ".storage.from("):
        if forbidden.lower() in browser.lower():
            fail(f"browser escaped S3-C3C boundary: {forbidden}")

    page = DOC_PAGE.read_text()
    for fragment in (
        "onUploadDocument?: (input: DirectDocumentInput, file: File) => Promise<void>",
        "if(onUploadDocument){await onUploadDocument(input,file);}",
        "uploadAccept?: string",
    ):
        if fragment not in page:
            fail(f"Documents presentation seam missing: {fragment}")

    workspace = DOC_WS.read_text()
    for fragment in (
        "uploadSupabaseDirectDocument",
        "onUploadDocument={uploadDocument}",
        "canUpload",
        "S3-C3C • وثائق Supabase",
        "S3-C3C يتيح للإدارة رفع الوثائق مباشرة",
        "createSupabaseDocumentSignedUrl",
    ):
        if fragment not in workspace:
            fail(f"DocumentsWorkspace S3-C3C missing: {fragment}")
    if "canUpload={false}" in workspace:
        fail("direct document upload remains disabled in Supabase workspace")

    browser_tree = "\n".join(p.read_text(errors="ignore") for p in (ROOT / "src").rglob("*.ts*"))
    for forbidden in ("SUPABASE_SECRET_KEYS", "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_", "service_role"):
        if forbidden.lower() in browser_tree.lower():
            fail(f"server credential leaked into browser tree: {forbidden}")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text()
    if "python scripts/check_supabase_s3_c3c.py" not in workflow:
        fail("workflow does not execute S3-C3C guard")
    if workflow.index("python scripts/check_supabase_s3_c3b_r2.py") > workflow.index("python scripts/check_supabase_s3_c3c.py"):
        fail("S3-C3C guard must run after S3-C3B R2")

    live = LIVE.read_text()
    for fragment in ("owner", "admin", "approved", "Signed URL", "teacher", "25MB", "LIVE GREEN"):
        if fragment not in live:
            fail(f"S3-C3C live acceptance incomplete: {fragment}")

    print("PASS: Marsad S3-C3C direct document upload and management")
    print("INFO: edge_auth=user_jwt manager_roles=owner,admin current_year_only=1")
    print("INFO: direct_upload=1 private_storage=1 status=approved signed_url_seconds=300")
    print("INFO: database_migration=0 browser_server_secret=0 orphan_cleanup=1 activity_record=1")


if __name__ == "__main__":
    main()
