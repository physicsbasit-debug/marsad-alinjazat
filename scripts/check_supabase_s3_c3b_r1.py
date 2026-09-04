from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
APP = ROOT / "src/App.tsx"
ROUTE = ROOT / "src/lib/publicUploadRoute.ts"
REPO = ROOT / "src/lib/supabaseRequestsDocuments.ts"
WORKFLOW = ROOT / ".github/workflows/quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE/quality-pages.yml"
APPLY = ROOT / "PHASE_S3_C3B_R1_APPLY_AR.txt"
DOC = ROOT / "GITHUB_PAGES_PUBLIC_UPLOAD_ROUTING_AR.md"

PROTECTED_HASHES = {
    ROOT / "server/main.py": "08988ebf9b23cdde7e712d02c5863c6beb14a0342f8e9286af04c06114a6a444",
    ROOT / "supabase/migrations/20260904223000_s3_c3b_public_intake_storage.sql": "b04095b94b21ba4c7ead56143b7b55db8812c83a7455e4288961dab3b3315c6c",
    ROOT / "supabase/functions/marsad-public-upload/index.ts": "e99b38662d3e19fde831b9d429d83948007566054406d24a21eb60b38790e2f9",
    ROOT / "supabase/config.toml": "b93eff36ec1d976fa89d7467b9e1c21c5d9534a93ed2c197940b85c2d089e54c",
    ROOT / "src/lib/supabasePublicUpload.ts": "ac9d51896ce1def66e09a66ddd192ba068cfb18d5cced8ccb7481ecb93c03505",
    ROOT / "src/pages/PublicUpload.tsx": "a2119d76d3420b92c826d3cbd068ffd481c296df1d2db47e5b2195a674e40e11",
    ROOT / "supabase/tests/s3_c3b_live_acceptance.sql": "bf03b3f091324b902278dec2ac2f811d8cd12f5f99cb8a31afacff6a00d64ac8",
    ROOT / "scripts/check_supabase_s3_c3b.py": "ba8183e14cdb79fb6539ed0570e96c30e961ea31c387d25b74e19e90d277fa73",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [PACKAGE, APP, ROUTE, REPO, WORKFLOW, VISIBLE_WORKFLOW, APPLY, DOC]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            fail(f"missing S3-C3B R1 artifact: {path.relative_to(ROOT)}")

    version = tuple(int(x) for x in json.loads(PACKAGE.read_text()).get("version", "0.0.0").split("."))
    if version < (0, 34, 1):
        fail("S3-C3B R1 requires package version >= 0.34.1")

    for path, expected in PROTECTED_HASHES.items():
        if not path.exists() or sha(path) != expected:
            fail(f"protected S3-C3B artifact changed: {path.relative_to(ROOT)}")

    migrations = sorted(path.name for path in (ROOT / "supabase/migrations").glob("*.sql") if path.is_file())
    if not migrations or migrations[-1] != "20260904223000_s3_c3b_public_intake_storage.sql":
        fail("routing correction must not add a database migration")

    route = ROUTE.read_text()
    for fragment in (
        "new URLSearchParams(search).get('upload')",
        "relativePath.match(/^\\/?upload\\/([^/]+)\\/?$/)",
        "decodeURIComponent(encodedToken)",
        "uploadUrl.searchParams.set('upload', token)",
    ):
        if fragment not in route:
            fail(f"public upload route helper missing: {fragment}")

    app = APP.read_text()
    if "resolvePublicUploadToken" not in app:
        fail("App does not use the unified public upload route resolver")
    if "window.location.pathname" not in app or "window.location.search" not in app:
        fail("App public upload resolver does not receive pathname and query string")

    repo = REPO.read_text()
    if "buildPublicUploadUrl(token, window.location.origin, import.meta.env.BASE_URL || '/')" not in repo:
        fail("new upload links are not built through the GitHub Pages-safe route helper")
    if "new URL(`upload/${encodeURIComponent(token)}`" in repo:
        fail("legacy path-only URL generation returned")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    workflow = WORKFLOW.read_text()
    if "python scripts/check_supabase_s3_c3b_r1.py" not in workflow:
        fail("workflow does not execute S3-C3B R1 guard")
    if "cp dist/index.html dist/404.html" not in workflow:
        fail("GitHub Pages SPA 404 fallback is missing")
    if workflow.index("python scripts/check_supabase_s3_c3b.py") > workflow.index("python scripts/check_supabase_s3_c3b_r1.py"):
        fail("S3-C3B R1 guard must run after the base S3-C3B guard")

    # Execute the actual TypeScript helper under Node 22's type stripping so the
    # generated URL and both token-reading modes are behaviorally verified.
    probe = """
import { buildPublicUploadUrl, resolvePublicUploadToken } from './src/lib/publicUploadRoute.ts';
const token = 'abc_DEF-123';
const base = '/marsad-alinjazat/';
const origin = 'https://physicsbasit-debug.github.io';
const generated = buildPublicUploadUrl(token, origin, base);
if (generated !== 'https://physicsbasit-debug.github.io/marsad-alinjazat/?upload=abc_DEF-123') {
  throw new Error(`unexpected generated URL: ${generated}`);
}
if (resolvePublicUploadToken('/marsad-alinjazat/', '?upload=abc_DEF-123', base) !== token) {
  throw new Error('query-token resolution failed');
}
if (resolvePublicUploadToken('/marsad-alinjazat/upload/abc_DEF-123', '', base) !== token) {
  throw new Error('legacy-path token resolution failed');
}
if (resolvePublicUploadToken('/marsad-alinjazat/', '', base) !== null) {
  throw new Error('root path incorrectly resolved as public upload');
}
"""
    try:
        completed = subprocess.run(
            ["node", "--experimental-strip-types", "--input-type=module", "-e", probe],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"route behavior probe could not run: {exc}")
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        fail(f"route behavior probe failed: {details}")

    print("PASS: Marsad S3-C3B R1 GitHub Pages public upload routing")
    print("INFO: new_links=query_param old_links=spa_404_fallback path_compat=1")
    print("INFO: database_changes=0 edge_changes=0 storage_changes=0")


if __name__ == "__main__":
    main()
