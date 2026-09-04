from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "package.json"
CLIENT_FILE = ROOT / "src" / "lib" / "supabase.ts"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_EXAMPLE_VISIBLE = ROOT / "ENV_EXAMPLE_VISIBLE.txt"
CONFIG_FILE = ROOT / "supabase" / "config.toml"
SEED_FILE = ROOT / "supabase" / "seed.sql"
LEGACY_API_FILE = ROOT / "src" / "lib" / "api.ts"
SRC_DIR = ROOT / "src"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    required = [PACKAGE_FILE, CLIENT_FILE, CONFIG_FILE, SEED_FILE]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"S1 foundation files are missing: {missing}")

    if ENV_EXAMPLE.exists():
        env_contract_file = ENV_EXAMPLE
        if ENV_EXAMPLE_VISIBLE.exists():
            hidden_text = ENV_EXAMPLE.read_text(encoding="utf-8")
            visible_text = ENV_EXAMPLE_VISIBLE.read_text(encoding="utf-8")
            if hidden_text != visible_text:
                fail(".env.example and ENV_EXAMPLE_VISIBLE.txt must stay identical when both exist")
    elif ENV_EXAMPLE_VISIBLE.exists():
        # Mobile/browser uploads may omit dotfiles. The visible mirror is an approved
        # source-of-truth fallback and must satisfy the exact same security contract.
        env_contract_file = ENV_EXAMPLE_VISIBLE
    else:
        fail("S1 foundation environment template is missing: expected .env.example or ENV_EXAMPLE_VISIBLE.txt")

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

    env_text = env_contract_file.read_text(encoding="utf-8")
    if "VITE_SUPABASE_URL=" not in env_text or "VITE_SUPABASE_PUBLISHABLE_KEY=" not in env_text:
        fail(f"{env_contract_file.name} does not document the browser-safe Supabase variables")
    active_env_lines = [line for line in env_text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    for line in active_env_lines:
        if re.search(r"(?:SERVICE[_-]?ROLE|SUPABASE[_-]?SECRET|sb_secret_)", line, re.IGNORECASE):
            fail(f"{env_contract_file.name} must not define server-only Supabase secrets")

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

    # S1 originally allowed no Supabase consumers. Later phases may add explicitly
    # approved read-only diagnostic/repository files while the operational API boundary stays Legacy.
    approved_supabase_consumers: set[str] = set()
    if version_tuple >= (0, 27, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseSession.ts",
            "src/pages/AuthDiagnostic.tsx",
        })
    if version_tuple >= (0, 28, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseTeachers.ts",
            "src/pages/TeachersReadDiagnostic.tsx",
        })
    if version_tuple >= (0, 29, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseTeachersWrite.ts",
        })
    if version_tuple >= (0, 30, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseTeacherProfile.ts",
            "src/pages/TeachersWorkspace.tsx",
        })
    if version_tuple >= (0, 31, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseTeacherRelated.ts",
        })
    if version_tuple >= (0, 32, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseSupervision.ts",
            "src/pages/SupervisionWorkspace.tsx",
        })
    if version_tuple >= (0, 33, 0):
        approved_supabase_consumers.update({
            "src/lib/supabaseRequestsDocuments.ts",
            "src/pages/RequestsWorkspace.tsx",
            "src/pages/DocumentsWorkspace.tsx",
            "src/pages/RequestsDocumentsCountProbe.tsx",
        })
    import_hits: list[str] = []
    for path in SRC_DIR.rglob("*.ts*"):
        if path == CLIENT_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'from\s+[\'\"][^\'\"]*supabase[\'\"]', text):
            relative = str(path.relative_to(ROOT))
            if relative not in approved_supabase_consumers:
                import_hits.append(relative)
    if import_hits:
        fail(f"Supabase escaped the approved staged diagnostic/repository boundary: {import_hits}")

    if not LEGACY_API_FILE.exists() or "VITE_PREVIEW_MODE" not in LEGACY_API_FILE.read_text(encoding="utf-8"):
        fail("legacy runtime boundary changed unexpectedly during S1")

    config_text = CONFIG_FILE.read_text(encoding="utf-8")
    if 'project_id = "marsad-alinjazat"' not in config_text:
        fail("supabase/config.toml project_id is missing")

    migration_files = sorted(p.name for p in (ROOT / "supabase" / "migrations").glob("*.sql") if p.is_file())
    # S1 itself shipped with zero migrations. Later phases are allowed to add
    # migrations while this historical foundation check continues to verify
    # client boundaries and secret hygiene.
    if version_tuple < (0, 17, 0) and migration_files:
        fail(f"pre-S2-B projects must not contain application migrations yet: {migration_files}")

    print("PASS: Marsad Phase S1 Supabase foundation contract")
    print(f"INFO: runtime_source=FastAPI/SQLite approved_supabase_diagnostic_consumers={len(approved_supabase_consumers)} migrations={len(migration_files)}")
    print("INFO: browser_key=VITE_SUPABASE_PUBLISHABLE_KEY forbidden_frontend_secrets=0")
    print(f"INFO: env_template_source={env_contract_file.name}")


if __name__ == "__main__":
    main()
