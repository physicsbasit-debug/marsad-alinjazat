import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_railway_config_uses_docker_and_readiness_healthcheck(self):
        config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
        self.assertEqual(config["build"]["builder"], "DOCKERFILE")
        self.assertEqual(config["build"]["dockerfilePath"], "Dockerfile")
        self.assertEqual(config["deploy"]["healthcheckPath"], "/api/ready")
        self.assertEqual(config["deploy"]["restartPolicyType"], "ON_FAILURE")

    def test_docker_image_builds_frontend_then_runs_fastapi_on_railway_port(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM node:22-alpine AS frontend", dockerfile)
        self.assertIn("RUN npm run build", dockerfile)
        self.assertIn("FROM python:3.12-slim AS runtime", dockerfile)
        self.assertIn("COPY --from=frontend /app/dist ./dist", dockerfile)
        self.assertIn("${PORT:-8000}", dockerfile)
        self.assertIn("uvicorn server.main:app", dockerfile)

    def test_dockerignore_excludes_runtime_data_and_secrets(self):
        ignored = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
        for required in {".env", "*.sqlite3", "data", "uploads", "node_modules", "dist"}:
            self.assertIn(required, ignored)


if __name__ == "__main__":
    unittest.main()
