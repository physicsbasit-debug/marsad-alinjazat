import os
import tempfile
import unittest

TEST_DATA_DIR = tempfile.mkdtemp(prefix="marsad-test-db-")
os.environ["APP_DATA_DIR"] = TEST_DATA_DIR
os.environ["APP_UPLOADS_DIR"] = tempfile.mkdtemp(prefix="marsad-test-uploads-")
os.environ["APP_EVENT_UPLOADS_DIR"] = tempfile.mkdtemp(prefix="marsad-test-event-uploads-")
os.environ["STORAGE_MODE"] = "local"
os.environ["APP_PUBLIC_URL"] = "http://testserver"
os.environ["APP_FRONTEND_URL"] = "http://testserver"

from fastapi.testclient import TestClient
from server.main import app


class MarsadAlInjazatApiTests(unittest.TestCase):
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

    def test_teacher_profile_and_cv_items_flow(self):
        profile = self.client.get("/api/teachers/1/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["teacher"]["id"], 1)
        self.assertIn("stats", profile.json())

        updated = self.client.patch("/api/teachers/1/profile", json={
            "name": "أحمد السالمي",
            "subject": "الفيزياء",
            "specialization": "فيزياء",
            "qualification": "بكالوريوس تربية",
            "experienceYears": 12,
            "workload": 18,
            "email": "ahmed@example.edu",
            "phone": "99112233",
            "employeeNumber": "SCI-001",
            "schoolJoinYear": 2018,
            "grades": "العاشر",
            "responsibilities": "تنسيق الفيزياء ومتابعة الاختبارات.",
            "professionalSummary": "معلم فيزياء يركز على جودة التعلم وتحسين التحصيل."
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["profile"]["employeeNumber"], "SCI-001")
        self.assertEqual(updated.json()["profile"]["schoolJoinYear"], 2018)

        item = self.client.post("/api/teachers/1/cv-items", json={
            "itemType": "course",
            "title": "التقويم من أجل التعلم",
            "organization": "برنامج تطوير مهني",
            "startYear": 2025,
            "endYear": 2025,
            "description": "برنامج تدريبي تطبيقي."
        })
        self.assertEqual(item.status_code, 201)
        item_id = item.json()["id"]

        profile_after = self.client.get("/api/teachers/1/profile")
        self.assertEqual(profile_after.status_code, 200)
        self.assertTrue(any(row["id"] == item_id and row["itemType"] == "course" for row in profile_after.json()["cvItems"]))

        invalid_years = self.client.post("/api/teachers/1/cv-items", json={
            "itemType": "experience",
            "title": "خبرة غير صالحة",
            "organization": "جهة",
            "startYear": 2026,
            "endYear": 2025,
            "description": ""
        })
        self.assertEqual(invalid_years.status_code, 422)

        removed = self.client.delete(f"/api/teachers/1/cv-items/{item_id}")
        self.assertEqual(removed.status_code, 200)
        profile_final = self.client.get("/api/teachers/1/profile").json()
        self.assertFalse(any(row["id"] == item_id for row in profile_final["cvItems"]))

    def test_teacher_profile_not_found_and_year_validation(self):
        missing = self.client.get("/api/teachers/999999/profile")
        self.assertEqual(missing.status_code, 404)

        bad_year = self.client.patch("/api/teachers/1/profile", json={
            "name": "أحمد السالمي",
            "subject": "الفيزياء",
            "specialization": "فيزياء",
            "qualification": "بكالوريوس تربية",
            "experienceYears": 12,
            "workload": 18,
            "email": "ahmed@example.edu",
            "phone": "",
            "employeeNumber": "",
            "schoolJoinYear": 1800,
            "grades": "العاشر",
            "responsibilities": "",
            "professionalSummary": ""
        })
        self.assertEqual(bad_year.status_code, 422)

        wrong_owner = self.client.delete("/api/teachers/2/cv-items/999999")
        self.assertEqual(wrong_owner.status_code, 404)

    def test_event_documentation_media_and_team_flow(self):
        created = self.client.post("/api/events", json={
            "title": "فعالية توثيق متكاملة", "eventType": "فعالية", "eventDate": "2026-10-20",
            "location": "المدرسة", "audience": "الصفوف 8-10", "participantCount": 35,
            "goals": "تعزيز التعلم العلمي", "summary": "محطات تعليمية متنوعة",
            "outcomes": "منتجات طلابية موثقة", "recommendations": "توسيع المشاركة", "teacherIds": [1, 2]
        })
        self.assertEqual(created.status_code, 201)
        event_id = created.json()["id"]

        detail = self.client.get(f"/api/events/{event_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual({teacher["id"] for teacher in detail.json()["teachers"]}, {1, 2})
        self.assertEqual(detail.json()["media"], [])

        image_bytes = b"\x89PNG\r\n\x1a\nmock-image"
        uploaded = self.client.post(
            f"/api/events/{event_id}/media",
            files={"file": ("evidence.png", image_bytes, "image/png")},
            data={"caption": "صورة توثيقية أولى"},
        )
        self.assertEqual(uploaded.status_code, 201)
        media = uploaded.json()
        self.assertEqual(media["storageProvider"], "local")
        self.assertTrue(media["isCover"])
        self.assertEqual(media["caption"], "صورة توثيقية أولى")
        media_id = media["id"]

        content = self.client.get(f"/api/events/{event_id}/media/{media_id}/content")
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.content, image_bytes)

        updated_media = self.client.patch(
            f"/api/events/{event_id}/media/{media_id}",
            json={"caption": "الغلاف الرسمي للفعالية", "position": 0, "isCover": True},
        )
        self.assertEqual(updated_media.status_code, 200)
        self.assertEqual(updated_media.json()["media"][0]["caption"], "الغلاف الرسمي للفعالية")
        self.assertEqual(updated_media.json()["coverMediaId"], media_id)

        updated_event = self.client.patch(f"/api/events/{event_id}", json={
            "title": "فعالية توثيق متكاملة", "eventType": "فعالية", "eventDate": "2026-10-20",
            "location": "قاعة المدرسة", "audience": "الصفوف 8-10", "participantCount": 36,
            "goals": "تعزيز التعلم العلمي", "summary": "محطات تعليمية متنوعة",
            "outcomes": "منتجات طلابية موثقة", "recommendations": "توسيع المشاركة", "teacherIds": [2, 3]
        })
        self.assertEqual(updated_event.status_code, 200)
        self.assertEqual({teacher["id"] for teacher in updated_event.json()["teachers"]}, {2, 3})
        self.assertEqual(updated_event.json()["participantCount"], 36)

        pdf = self.client.post(
            f"/api/events/{event_id}/media",
            files={"file": ("event-report.pdf", b"%PDF-1.4\nmock", "application/pdf")},
        )
        self.assertEqual(pdf.status_code, 201)
        pdf_id = pdf.json()["id"]
        bad_cover = self.client.patch(
            f"/api/events/{event_id}/media/{pdf_id}",
            json={"caption": "تقرير", "position": 1, "isCover": True},
        )
        self.assertEqual(bad_cover.status_code, 422)

        reordered = self.client.patch(f"/api/events/{event_id}/media-order", json={"mediaIds": [pdf_id, media_id]})
        self.assertEqual(reordered.status_code, 200)
        self.assertEqual([item["id"] for item in reordered.json()["media"]], [pdf_id, media_id])
        invalid_order = self.client.patch(f"/api/events/{event_id}/media-order", json={"mediaIds": [pdf_id, pdf_id]})
        self.assertEqual(invalid_order.status_code, 422)

        removed = self.client.delete(f"/api/events/{event_id}/media/{media_id}")
        self.assertEqual(removed.status_code, 200)
        final_detail = self.client.get(f"/api/events/{event_id}").json()
        self.assertFalse(any(item["id"] == media_id for item in final_detail["media"]))
        self.assertIsNone(final_detail["coverMediaId"])

    def test_event_documentation_validation(self):
        self.assertEqual(self.client.get("/api/events/999999").status_code, 404)
        invalid_teacher = self.client.post("/api/events", json={
            "title": "فعالية بمعلم غير موجود", "eventType": "فعالية", "eventDate": "2026-10-20",
            "location": "", "audience": "", "participantCount": 0, "goals": "", "summary": "",
            "outcomes": "", "recommendations": "", "teacherIds": [999999]
        })
        self.assertEqual(invalid_teacher.status_code, 422)

    def test_event_image_mime_falls_back_to_extension(self):
        created = self.client.post("/api/events", json={
            "title": "فعالية اختبار نوع الصورة", "eventType": "فعالية", "eventDate": "2026-10-21",
            "location": "المدرسة", "audience": "الصف الثامن", "participantCount": 10,
            "goals": "اختبار التوثيق", "summary": "تنفيذ", "outcomes": "مخرجات", "recommendations": "", "teacherIds": []
        })
        self.assertEqual(created.status_code, 201)
        event_id = created.json()["id"]
        uploaded = self.client.post(
            f"/api/events/{event_id}/media",
            files={"file": ("evidence.jpg", b"mock-jpeg", "application/octet-stream")},
        )
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual(uploaded.json()["mimeType"], "image/jpeg")
        self.assertTrue(uploaded.json()["isCover"])

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
