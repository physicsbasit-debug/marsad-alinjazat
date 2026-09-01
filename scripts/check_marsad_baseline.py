from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_FILE = ROOT / "server" / "db.py"
MAIN_FILE = ROOT / "server" / "main.py"
API_FILE = ROOT / "src" / "lib" / "api.ts"
SRC_DIR = ROOT / "src"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW_FILE = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"

EXPECTED_TABLES = {
    "settings",
    "teachers",
    "upload_requests",
    "documents",
    "events",
    "event_media",
    "activities",
    "teacher_profiles",
    "teacher_cv_items",
    "event_teacher_links",
    "event_media_meta",
    "meetings",
    "meeting_attendees",
    "meeting_decisions",
    "curriculum_plans",
    "curriculum_units",
    "supervision_visits",
    "supervision_actions",
    "achievement_assessments",
    "achievement_assessment_standards",
    "achievement_actions",
    "achievement_action_metrics",
    "request_record_years",
    "event_record_years",
    "teacher_record_years",
}

REQUIRED_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/ready"),
    ("GET", "/api/bootstrap"),
    ("GET", "/api/reports/official"),
    ("GET", "/api/archive/years"),
    ("GET", "/api/archive/year"),
    ("GET", "/api/search"),
    ("POST", "/api/teachers"),
    ("GET", "/api/teachers/{teacher_id}/profile"),
    ("POST", "/api/events"),
    ("POST", "/api/events/{event_id}/media"),
    ("POST", "/api/meetings"),
    ("POST", "/api/plans"),
    ("POST", "/api/supervision/visits"),
    ("POST", "/api/achievement/assessments"),
    ("POST", "/api/requests"),
    ("GET", "/api/public/upload/{token}"),
    ("POST", "/api/public/upload/{token}"),
    ("POST", "/api/documents"),
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    db_text = DB_FILE.read_text(encoding="utf-8")
    main_text = MAIN_FILE.read_text(encoding="utf-8")
    api_text = API_FILE.read_text(encoding="utf-8")

    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-zA-Z0-9_]+)", db_text))
    missing_tables = EXPECTED_TABLES - tables
    if missing_tables:
        fail(f"legacy schema lost tables: {sorted(missing_tables)}")
    if len(tables) != 25:
        fail(f"expected 25 legacy tables before Supabase migration, found {len(tables)}")

    routes = {
        (method.upper(), path)
        for method, path in re.findall(
            r'@app\.(get|post|put|patch|delete)\("([^\"]+)"', main_text
        )
    }
    missing_routes = REQUIRED_ROUTES - routes
    if missing_routes:
        fail(f"required legacy routes disappeared: {sorted(missing_routes)}")
    if len(routes) != 63:
        fail(f"expected 63 legacy HTTP routes before Supabase migration, found {len(routes)}")

    direct_fetch_files: list[str] = []
    for path in SRC_DIR.rglob("*.ts*"):
        if path == API_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bfetch\s*\(", text):
            direct_fetch_files.append(str(path.relative_to(ROOT)))
    if direct_fetch_files:
        fail(f"frontend network calls bypass src/lib/api.ts: {direct_fetch_files}")

    if "VITE_PREVIEW_MODE" not in api_text or "requireBackend" not in api_text:
        fail("GitHub Pages preview guard contract is missing from src/lib/api.ts")

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    visible = VISIBLE_WORKFLOW_FILE.read_text(encoding="utf-8")
    if workflow != visible:
        fail("visible workflow copy is not byte-identical to .github workflow")
    if "python scripts/marsad_e2e_regression.py" not in workflow:
        fail("CI does not execute the HTTP E2E regression")

    print("PASS: Marsad S0 legacy baseline contract")
    print(f"INFO: tables={len(tables)} routes={len(routes)} frontend_network_boundary=src/lib/api.ts")


if __name__ == "__main__":
    main()
