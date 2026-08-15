import os
import tempfile
import unittest

TEST_DATA_DIR = tempfile.mkdtemp(prefix="science-lead-test-db-")
os.environ["APP_DATA_DIR"] = TEST_DATA_DIR
os.environ["APP_UPLOADS_DIR"] = tempfile.mkdtemp(prefix="science-lead-test-uploads-")
os.environ["STORAGE_MODE"] = "local"
os.environ["APP_PUBLIC_URL"] = "http://testserver"
os.environ["APP_FRONTEND_URL"] = "http://testserver"

from fastapi.testclient import TestClient
from server.main import app


class ScienceLeadHubApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_bootstrap(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        boot = self.client.get("/api/bootstrap")
        self.assertEqual(boot.status_code, 200)
        self.assertGreaterEqual(len(boot.json()["teachers"]), 6)
        self.assertIn("dashboard", boot.json())

    def test_create_teacher_and_event(self):
        teacher = self.client.post("/api/teachers", json={
            "name": "معلم اختبار التكامل",
            "subject": "الفيزياء",
            "specialization": "فيزياء",
            "qualification": "بكالوريوس تربية",
            "experienceYears": 7,
            "workload": 18,
            "email": "teacher@example.edu",
            "phone": ""
        })
        self.assertEqual(teacher.status_code, 201)
        event = self.client.post("/api/events", json={
            "title": "فعالية اختبار التكامل",
            "eventType": "مبادرة",
            "eventDate": "2026-09-10",
            "location": "المدرسة",
            "audience": "الصف العاشر",
            "participantCount": 20,
            "goals": "هدف اختباري",
            "summary": "تنفيذ اختباري",
            "outcomes": "مخرجات",
            "recommendations": "توصية"
        })
        self.assertEqual(event.status_code, 201)

    def test_request_public_upload_review_approve_flow(self):
        created = self.client.post("/api/requests", json={
            "teacherId": 1,
            "requestType": "اختبار",
            "subject": "الفيزياء",
            "grade": "العاشر",
            "title": "اختبار تدفق الرفع",
            "deadline": "2026-09-22",
            "notes": "نسخة معتمدة",
            "allowedFiles": "PDF / Word / Excel"
        })
        self.assertEqual(created.status_code, 201)
        payload = created.json()
        token = payload["uploadUrl"].rsplit("/", 1)[-1]

        public = self.client.get(f"/api/public/upload/{token}")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["title"], "اختبار تدفق الرفع")

        uploaded = self.client.post(
            f"/api/public/upload/{token}",
            files={"file": ("exam.pdf", b"%PDF-1.4\nmock\n", "application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual(uploaded.json()["storageProvider"], "local")

        boot = self.client.get("/api/bootstrap").json()
        request = next(item for item in boot["requests"] if item["id"] == payload["id"])
        self.assertEqual(request["status"], "review")
        self.assertTrue(any(doc["requestId"] == payload["id"] for doc in boot["documents"]))

        approved = self.client.patch(f"/api/requests/{payload['id']}/status", json={"status": "approved"})
        self.assertEqual(approved.status_code, 200)
        boot2 = self.client.get("/api/bootstrap").json()
        request2 = next(item for item in boot2["requests"] if item["id"] == payload["id"])
        self.assertEqual(request2["status"], "approved")

    def test_invalid_extension_is_rejected(self):
        created = self.client.post("/api/requests", json={
            "teacherId": 1,
            "requestType": "ملف آخر",
            "subject": "العلوم",
            "grade": "الثامن",
            "title": "طلب امتداد غير مسموح",
            "allowedFiles": "PDF / Word / Excel"
        }).json()
        token = created["uploadUrl"].rsplit("/", 1)[-1]
        response = self.client.post(
            f"/api/public/upload/{token}",
            files={"file": ("bad.exe", b"MZ", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()
