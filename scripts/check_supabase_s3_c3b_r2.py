from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
EDGE = ROOT / "supabase/functions/marsad-public-upload/index.ts"
CONFIG = ROOT / "supabase/config.toml"
MIGRATIONS = ROOT / "supabase/migrations"
WORKFLOW = ROOT / ".github/workflows/quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE/quality-pages.yml"
C3B_GUARD = ROOT / "scripts/check_supabase_s3_c3b.py"
R1_GUARD = ROOT / "scripts/check_supabase_s3_c3b_r1.py"
APPLY = ROOT / "PHASE_S3_C3B_R2_APPLY_AR.txt"
DOC = ROOT / "EDGE_PUBLIC_UPLOAD_CORS_AR.md"

EDGE_SHA = "2de16a96ea97280dcf1b9470ab14c2133c7fb8c0deccf7aec579b87b4c681757"
MIGRATION = "20260904223000_s3_c3b_public_intake_storage.sql"
MIGRATION_SHA = "b04095b94b21ba4c7ead56143b7b55db8812c83a7455e4288961dab3b3315c6c"
PROTECTED_HASHES = {
    ROOT / "server/main.py": "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444",
    ROOT / "supabase/config.toml": "b93eff36ec1d976fa89d7467b9e1c21c5d9534a93ed2c197940b85c2d089e54c",
    ROOT / "src/lib/supabasePublicUpload.ts": "ac9d51896ce1def66e09a66ddd192ba068cfb18d5cced8ccb7481ecb93c03505",
    ROOT / "src/pages/PublicUpload.tsx": "a2119d76d3420b92c826d3cbd068ffd481c296df1d2db47e5b2195a674e40e11",
    ROOT / "supabase/tests/s3_c3b_live_acceptance.sql": "bf03b3f091324b902278dec2ac2f811d8cd12f5f99cb8a31afacff6a00d64ac8",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [PACKAGE, EDGE, CONFIG, WORKFLOW, VISIBLE_WORKFLOW, C3B_GUARD, R1_GUARD, APPLY, DOC]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C3B R2 artifact: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text())
    version = tuple(int(x) for x in package.get("version", "0.0.0").split("."))
    if version < (0, 34, 2):
        fail("S3-C3B R2 requires package version >= 0.34.2")
    if package.get("dependencies", {}).get("@supabase/supabase-js") != "2.112.4":
        fail("Supabase JS version drifted during CORS correction")

    if sha(EDGE) != EDGE_SHA:
        fail("S3-C3B R2 Edge Function hash mismatch")
    for path, expected in PROTECTED_HASHES.items():
        if sha(path) != expected:
            fail(f"protected artifact changed during CORS correction: {path.relative_to(ROOT)}")
    if sha(MIGRATIONS / MIGRATION) != MIGRATION_SHA:
        fail("S3-C3B migration changed during CORS correction")
    migrations = sorted(path.name for path in MIGRATIONS.glob("*.sql") if path.is_file())
    if not migrations or migrations[-1] != MIGRATION:
        fail("CORS correction must not add a database migration")

    edge = EDGE.read_text()
    required_edge = (
        "import { corsHeaders as supabaseCorsHeaders } from 'npm:@supabase/supabase-js@2.112.4/cors';",
        "...supabaseCorsHeaders",
        "'Access-Control-Allow-Methods': 'POST, OPTIONS'",
        "if (request.method === 'OPTIONS')",
        "status: 204",
        ".storage.from(BUCKET).upload",
        ".rpc('marsad_register_public_upload_v1'",
        ".storage.from(BUCKET).remove([storagePath])",
    )
    for fragment in required_edge:
        if fragment not in edge:
            fail(f"Edge CORS correction missing: {fragment}")
    forbidden = "'Access-Control-Allow-Headers': 'apikey, content-type, x-client-info'"
    if forbidden in edge:
        fail("old restrictive CORS allow-header list returned")

    config = CONFIG.read_text()
    if "[functions.marsad-public-upload]" not in config or "verify_jwt = false" not in config:
        fail("public Edge verify_jwt boundary changed")

    if "v0.34.2+ permits the bounded CORS-only Edge correction" not in C3B_GUARD.read_text():
        fail("base C3B guard is not forward-compatible with R2")
    if "future_mutable" not in R1_GUARD.read_text() or "version >= (0, 34, 2)" not in R1_GUARD.read_text():
        fail("R1 guard is not forward-compatible with R2")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text()
    if "python scripts/check_supabase_s3_c3b_r2.py" not in workflow:
        fail("workflow does not execute S3-C3B R2 guard")
    if workflow.index("python scripts/check_supabase_s3_c3b_r1.py") > workflow.index("python scripts/check_supabase_s3_c3b_r2.py"):
        fail("R2 guard must run after R1")

    print("PASS: Marsad S3-C3B R2 browser-to-Edge CORS correction")
    print("INFO: supabase_cors_sdk=1 authorization_header_supported=1 preflight=1")
    print("INFO: database_changes=0 storage_schema_changes=0 public_route_changes=0")
    print("INFO: edge_redeploy_required=1")


if __name__ == "__main__":
    main()
