from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "package.json"
CLIENT_FILE = ROOT / "src" / "lib" / "supabase.ts"
ENV_EXAMPLE = ROOT / ".env.example"
CONFIG_FILE = ROOT / "supabase" / "config.toml"
SEED_FILE = ROOT / "supabase" / "seed.sql"
LEGACY_API_FILE = ROOT / "src" / "lib" / "api.ts"
SRC_DIR = ROOT / "src"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    required = [PACKAGE_FILE, CLIENT_FILE, ENV_EXAMPLE, CONFIG_FILE, SEED_FILE]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"S1 foundation files are missing: {missing}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    version = package.get("version", "0.0.0")
    try:
        version_tuple = tuple(int(part) for part in version.split(".")[:3])
    except ValueError:
        fail(f"invalid package version: {version}")
    if version_tuple < (0, 15, 0):
        fail("Supabase foundation requires package version >= 0.15.0")
    if package.get("dependencies", {}).get("@supabase/supabase-js") != "2.112.4":
        fail("@supabase/supabase-js must stay pinned to 2.112.4 in S1")
    if package.get("devDependencies", {}).get("supabase") != "2.116.0":
        fail("Supabase CLI must stay pinned to 2.116.0 in S1")
    if package.get("engines", {}).get("node") != ">=22":
        fail("S1 must require Node >=22")

    client_text = CLIENT_FILE.read_text(encoding="utf-8")
    if "VITE_SUPABASE_URL" not in client_text or "VITE_SUPABASE_PUBLISHABLE_KEY" not in client_text:
        fail("browser client is not wired to the approved Supabase environment variables")
    if "createClient" not in client_text or "SUPABASE_CONFIGURED" not in client_text:
        fail("Supabase client helper contract is incomplete")

    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    if "VITE_SUPABASE_URL=" not in env_text or "VITE_SUPABASE_PUBLISHABLE_KEY=" not in env_text:
        fail(".env.example does not document the browser-safe Supabase variables")

    forbidden_patterns = {
        "service-role": r"service[_-]?role",
        "secret-key-name": r"supabase[_-]?secret",
        "vite-secret": r"VITE_[A-Z0-9_]*(?:SECRET|SERVICE_ROLE)",
        "literal-secret-key": r"sb_secret_[A-Za-z0-9_-]+",
    }
    secret_hits: list[str] = []
    for path in SRC_DIR.rglob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                secret_hits.append(f"{path.relative_to(ROOT)}:{label}")
    if secret_hits:
        fail(f"frontend contains forbidden Supabase secret/service-role material: {secret_hits}")

    # S1 is foundation-only. No production page or legacy API path may consume Supabase yet.
    import_hits: list[str] = []
    for path in SRC_DIR.rglob("*.ts*"):
        if path == CLIENT_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"from\s+['\"][^'\"]*supabase['\"]", text):
            import_hits.append(str(path.relative_to(ROOT)))
    if import_hits:
        fail(f"S1 must not switch runtime data paths to Supabase yet: {import_hits}")

    if not LEGACY_API_FILE.exists() or "VITE_PREVIEW_MODE" not in LEGACY_API_FILE.read_text(encoding="utf-8"):
        fail("legacy runtime boundary changed unexpectedly during S1")

    config_text = CONFIG_FILE.read_text(encoding="utf-8")
    if 'project_id = "marsad-alinjazat"' not in config_text:
        fail("supabase/config.toml project_id is missing")

    migration_files = [p for p in (ROOT / "supabase" / "migrations").glob("*.sql") if p.is_file()]
    if migration_files:
        fail(f"S1 must not migrate application tables yet: {[p.name for p in migration_files]}")

    print("PASS: Marsad Phase S1 Supabase foundation contract")
    print("INFO: runtime_source=FastAPI/SQLite supabase_runtime_consumers=0 migrations=0")
    print("INFO: browser_key=VITE_SUPABASE_PUBLISHABLE_KEY forbidden_frontend_secrets=0")


if __name__ == "__main__":
    main()
