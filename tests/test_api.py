import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

TEST_DATA_DIR = tempfile.mkdtemp(prefix="marsad-test-db-")
os.environ["APP_DATA_DIR"] = TEST_DATA_DIR
os.environ["APP_UPLOADS_DIR"] = tempfile.mkdtemp(prefix="marsad-test-uploads-")
os.environ["APP_EVENT_UPLOADS_DIR"] = tempfile.mkdtemp(prefix="marsad-test-event-uploads-")
os.environ["STORAGE_MODE"] = "local"
os.environ["APP_PUBLIC_URL"] = "http://testserver"
os.environ["APP_FRONTEND_URL"] = "http://testserver"
os.environ["APP_ENV"] = "testing"
os.environ["APP_BACKUP_DIR"] = tempfile.mkdtemp(prefix="marsad-test-backups-")
os.environ["APP_CORS_ORIGINS"] = "https://frontend.example"

from fastapi.testclient import TestClient
from server.main import app
from server.db import connect
from server.achievement_metrics import evaluate_impact


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
        self.assertGreaterEqual(len(boot.json()["teacherDirectory"]), len(boot.json()["teachers"]))
        self.assertIn("dashboard", boot.json())
        self.assertIn("visits", boot.json())
        self.assertIn("supervisionAttention", boot.json())
        self.assertIn("assessments", boot.json())
        self.assertIn("achievementAttention", boot.json())
        self.assertEqual(health.json()["version"], "0.14.0")

    def test_ready_and_cors_contract(self):
        ready = self.client.get("/api/ready")
        self.assertEqual(ready.status_code, 200)
        payload = ready.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["version"], "0.14.0")
        self.assertTrue(payload["checks"]["database"])
        self.assertTrue(payload["checks"]["dataDirWritable"])
        self.assertTrue(payload["checks"]["backupDirWritable"])
        self.assertTrue(payload["checks"]["uploadsDirWritable"])

        preflight = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://frontend.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers.get("access-control-allow-origin"), "https://frontend.example")

    def test_cors_origin_normalizes_frontend_subpath(self):
        import server.main as main_module
        self.assertEqual(
            main_module._origin_from_url("https://example.edu/marsad/"),
            "https://example.edu",
        )

    def test_production_readiness_requires_explicit_persistent_paths(self):
        from unittest.mock import patch
        import server.main as main_module

        with patch.object(main_module, "APP_ENV", "production"), patch.dict(
            os.environ,
            {"APP_DATA_DIR": "", "APP_BACKUP_DIR": ""},
            clear=False,
        ):
            response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["checks"]["persistentDataConfigured"])
        self.assertFalse(payload["checks"]["backupDirConfigured"])

    def test_production_local_storage_requires_explicit_upload_paths(self):
        from unittest.mock import patch
        import server.main as main_module

        with patch.object(main_module, "APP_ENV", "production"), patch.dict(
            os.environ,
            {
                "APP_DATA_DIR": TEST_DATA_DIR,
                "APP_BACKUP_DIR": os.environ["APP_BACKUP_DIR"],
                "APP_UPLOADS_DIR": "",
                "APP_EVENT_UPLOADS_DIR": "",
                "STORAGE_MODE": "local",
            },
            clear=False,
        ):
            response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["persistentUploadsConfigured"])

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

    def test_meeting_decisions_end_to_end_flow(self):
        before = self.client.get("/api/bootstrap").json()["dashboard"]["openDecisions"]
        yesterday = (datetime.now(timezone(timedelta(hours=4))).date() - timedelta(days=1)).isoformat()

        created = self.client.post("/api/meetings", json={
            "title": "اجتماع متابعة القرارات",
            "meetingType": "اجتماع متابعة",
            "meetingDate": "2026-09-03",
            "meetingTime": "10:30",
            "location": "قاعة العلوم",
            "agenda": "متابعة تنفيذ خطة القسم ومراجعة القرارات المفتوحة.",
            "discussionSummary": "تمت مراجعة الأولويات وتحديد المسؤوليات ومواعيد الإنجاز.",
            "notes": "اختبار تكامل للمحضر.",
            "status": "held",
            "attendeeIds": [1, 2],
        })
        self.assertEqual(created.status_code, 201)
        meeting_id = created.json()["id"]

        detail = self.client.get(f"/api/meetings/{meeting_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual({row["id"] for row in detail.json()["attendees"]}, {1, 2})
        self.assertFalse(detail.json()["minutesReady"])

        decision = self.client.post(f"/api/meetings/{meeting_id}/decisions", json={
            "title": "إغلاق متابعة الخطة العلاجية",
            "responsibleTeacherId": 1,
            "responsibleName": "",
            "dueDate": yesterday,
            "status": "in_progress",
            "notes": "إرفاق دليل التنفيذ قبل الإغلاق.",
        })
        self.assertEqual(decision.status_code, 201)
        decision_body = decision.json()
        decision_id = decision_body["id"]
        self.assertEqual(decision_body["responsibleName"], "أحمد السالمي")
        self.assertEqual(decision_body["status"], "overdue")
        self.assertEqual(decision_body["baseStatus"], "in_progress")

        after_create = self.client.get("/api/bootstrap").json()
        self.assertEqual(after_create["dashboard"]["openDecisions"], before + 1)
        attention = next(item for item in after_create["decisionAttention"] if item["id"] == decision_id)
        self.assertEqual(attention["status"], "overdue")
        self.assertEqual(attention["meetingTitle"], "اجتماع متابعة القرارات")

        detail_after = self.client.get(f"/api/meetings/{meeting_id}").json()
        self.assertTrue(detail_after["minutesReady"])
        self.assertEqual(detail_after["openDecisionCount"], 1)
        self.assertEqual(detail_after["overdueDecisionCount"], 1)
        self.assertTrue(any("قرار جديد" in item["title"] for item in detail_after["timeline"]))

        updated_meeting = self.client.patch(f"/api/meetings/{meeting_id}", json={
            "title": "اجتماع متابعة القرارات",
            "meetingType": "اجتماع متابعة",
            "meetingDate": "2026-09-03",
            "meetingTime": "11:00",
            "location": "قاعة العلوم",
            "agenda": "متابعة تنفيذ خطة القسم ومراجعة القرارات المفتوحة.",
            "discussionSummary": "تمت مراجعة الأولويات وتحديد المسؤوليات ومواعيد الإنجاز.",
            "notes": "تم تحديث وقت الاجتماع.",
            "status": "held",
            "attendeeIds": [2, 3],
        })
        self.assertEqual(updated_meeting.status_code, 200)
        self.assertEqual({row["id"] for row in updated_meeting.json()["attendees"]}, {2, 3})
        self.assertEqual(updated_meeting.json()["meetingTime"], "11:00")

        completed = self.client.patch(f"/api/meetings/{meeting_id}/decisions/{decision_id}", json={
            "title": "إغلاق متابعة الخطة العلاجية",
            "responsibleTeacherId": 1,
            "responsibleName": "أحمد السالمي",
            "dueDate": yesterday,
            "status": "completed",
            "notes": "تم إرفاق دليل التنفيذ.",
        })
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["baseStatus"], "completed")
        self.assertIsNotNone(completed.json()["completedAt"])

        after_complete = self.client.get("/api/bootstrap").json()
        self.assertEqual(after_complete["dashboard"]["openDecisions"], before)
        summary = next(item for item in after_complete["meetings"] if item["id"] == meeting_id)
        self.assertEqual(summary["openDecisionCount"], 0)
        self.assertEqual(summary["completedDecisionCount"], 1)
        self.assertEqual(summary["overdueDecisionCount"], 0)

        removed = self.client.delete(f"/api/meetings/{meeting_id}/decisions/{decision_id}")
        self.assertEqual(removed.status_code, 200)
        final_detail = self.client.get(f"/api/meetings/{meeting_id}").json()
        self.assertEqual(final_detail["decisions"], [])
        self.assertTrue(any("حذف قرار" in item["title"] for item in final_detail["timeline"]))

    def test_meeting_validation_and_not_found_guards(self):
        invalid_date = self.client.post("/api/meetings", json={
            "title": "اجتماع بتاريخ خاطئ", "meetingDate": "2026-99-03", "meetingTime": "10:00",
            "attendeeIds": []
        })
        self.assertEqual(invalid_date.status_code, 422)

        invalid_time = self.client.post("/api/meetings", json={
            "title": "اجتماع بوقت خاطئ", "meetingDate": "2026-09-03", "meetingTime": "25:90",
            "attendeeIds": []
        })
        self.assertEqual(invalid_time.status_code, 422)

        invalid_attendee = self.client.post("/api/meetings", json={
            "title": "اجتماع بحضور غير صالح", "meetingDate": "2026-09-03", "meetingTime": "",
            "attendeeIds": [999999]
        })
        self.assertEqual(invalid_attendee.status_code, 422)
        self.assertEqual(self.client.get("/api/meetings/999999").status_code, 404)

        meeting = self.client.post("/api/meetings", json={
            "title": "اجتماع اختبار الحراس", "meetingDate": "2026-09-04", "meetingTime": "09:00",
            "attendeeIds": [1]
        })
        self.assertEqual(meeting.status_code, 201)
        meeting_id = meeting.json()["id"]
        invalid_responsible = self.client.post(f"/api/meetings/{meeting_id}/decisions", json={
            "title": "قرار بمسؤول غير صالح", "responsibleTeacherId": 999999, "responsibleName": "",
            "dueDate": "2026-09-10", "status": "new", "notes": ""
        })
        self.assertEqual(invalid_responsible.status_code, 422)
        missing_meeting = self.client.post("/api/meetings/999999/decisions", json={
            "title": "قرار لاجتماع مفقود", "responsibleTeacherId": None, "responsibleName": "",
            "dueDate": None, "status": "new", "notes": ""
        })
        self.assertEqual(missing_meeting.status_code, 404)
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting_id}/decisions/999999").status_code, 404)

    def test_curriculum_planning_lifecycle_and_dashboard_progress(self):
        today = datetime.now(timezone.utc).date()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()
        created = self.client.post("/api/plans", json={
            "title": "خطة فيزياء اختبارية", "subject": "الفيزياء", "grade": "العاشر",
            "term": "الفصل الأول", "ownerTeacherId": 1, "startDate": yesterday, "endDate": tomorrow,
            "notes": "خطة لاختبار دورة التخطيط", "status": "active"
        })
        self.assertEqual(created.status_code, 201)
        plan_id = created.json()["id"]
        edited = self.client.patch(f"/api/plans/{plan_id}", json={
            "title": "خطة فيزياء اختبارية محدثة", "subject": "الفيزياء", "grade": "العاشر",
            "term": "الفصل الأول", "ownerTeacherId": 1, "startDate": yesterday, "endDate": tomorrow,
            "notes": "تم تحديث وصف الخطة", "status": "active"
        })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["title"], "خطة فيزياء اختبارية محدثة")

        unit = self.client.post(f"/api/plans/{plan_id}/units", json={
            "title": "الحركة والقوى", "sequence": 1, "plannedStart": yesterday, "plannedEnd": yesterday,
            "progressPercent": 40, "status": "in_progress", "delayReason": "تأخر نشاط عملي",
            "notes": "", "responsibleTeacherId": 1
        })
        self.assertEqual(unit.status_code, 201)
        unit_data = unit.json()
        self.assertEqual(unit_data["effectiveStatus"], "overdue")
        unit_id = unit_data["id"]

        detail = self.client.get(f"/api/plans/{plan_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["unitCount"], 1)
        self.assertEqual(detail.json()["overdueUnitCount"], 1)
        self.assertEqual(detail.json()["progressPercent"], 40)
        self.assertTrue(any("إضافة وحدة" in item["title"] for item in detail.json()["timeline"]))

        boot = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == plan_id for item in boot["plans"]))
        self.assertTrue(any(item["id"] == unit_id for item in boot["planningAttention"]))
        self.assertGreaterEqual(boot["dashboard"]["planProgress"], 0)

        updated = self.client.patch(f"/api/plans/{plan_id}/units/{unit_id}", json={
            "title": "الحركة والقوى", "sequence": 1, "plannedStart": yesterday, "plannedEnd": yesterday,
            "progressPercent": 70, "status": "completed", "delayReason": "تمت المعالجة",
            "notes": "اكتملت الوحدة", "responsibleTeacherId": 1
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "completed")
        self.assertEqual(updated.json()["progressPercent"], 100)
        self.assertEqual(updated.json()["effectiveStatus"], "completed")

        boot2 = self.client.get("/api/bootstrap").json()
        self.assertFalse(any(item["id"] == unit_id for item in boot2["planningAttention"]))
        summary = next(item for item in boot2["plans"] if item["id"] == plan_id)
        self.assertEqual(summary["completedUnitCount"], 1)
        self.assertEqual(summary["overdueUnitCount"], 0)
        self.assertEqual(summary["progressPercent"], 100)

        removed = self.client.delete(f"/api/plans/{plan_id}/units/{unit_id}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.client.get(f"/api/plans/{plan_id}").json()["units"], [])

    def test_curriculum_planning_validation_guards(self):
        invalid_dates = self.client.post("/api/plans", json={
            "title": "خطة بتاريخ خاطئ", "subject": "العلوم", "grade": "الثامن", "term": "الفصل الأول",
            "ownerTeacherId": 1, "startDate": "2026-09-10", "endDate": "2026-09-01", "notes": "", "status": "active"
        })
        self.assertEqual(invalid_dates.status_code, 422)
        invalid_teacher = self.client.post("/api/plans", json={
            "title": "خطة بمسؤول مفقود", "subject": "العلوم", "grade": "الثامن", "term": "الفصل الأول",
            "ownerTeacherId": 999999, "startDate": None, "endDate": None, "notes": "", "status": "active"
        })
        self.assertEqual(invalid_teacher.status_code, 422)
        self.assertEqual(self.client.get("/api/plans/999999").status_code, 404)

        plan = self.client.post("/api/plans", json={
            "title": "خطة حراس الوحدات", "subject": "العلوم", "grade": "الثامن", "term": "الفصل الأول",
            "ownerTeacherId": 1, "startDate": None, "endDate": None, "notes": "", "status": "active"
        })
        self.assertEqual(plan.status_code, 201)
        plan_id = plan.json()["id"]
        invalid_unit_dates = self.client.post(f"/api/plans/{plan_id}/units", json={
            "title": "وحدة غير صالحة", "sequence": 1, "plannedStart": "2026-10-10", "plannedEnd": "2026-10-01",
            "progressPercent": 0, "status": "not_started", "delayReason": "", "notes": "", "responsibleTeacherId": 1
        })
        self.assertEqual(invalid_unit_dates.status_code, 422)
        invalid_unit_teacher = self.client.post(f"/api/plans/{plan_id}/units", json={
            "title": "وحدة بمسؤول مفقود", "sequence": 1, "plannedStart": None, "plannedEnd": None,
            "progressPercent": 0, "status": "not_started", "delayReason": "", "notes": "", "responsibleTeacherId": 999999
        })
        self.assertEqual(invalid_unit_teacher.status_code, 422)
        self.assertEqual(self.client.delete(f"/api/plans/{plan_id}/units/999999").status_code, 404)


    def test_supervision_visit_lifecycle_dashboard_and_teacher_profile(self):
        oman_today = datetime.now(timezone(timedelta(hours=4))).date()
        yesterday = (oman_today - timedelta(days=1)).isoformat()
        tomorrow = (oman_today + timedelta(days=1)).isoformat()
        later = (oman_today + timedelta(days=5)).isoformat()

        profile_before = self.client.get("/api/teachers/1/profile").json()["stats"]
        created = self.client.post("/api/supervision/visits", json={
            "teacherId": 1,
            "visitType": "زيارة تطويرية",
            "visitDate": tomorrow,
            "periodLabel": "الحصة الثالثة",
            "grade": "العاشر",
            "lessonTitle": "القوى والحركة",
            "objectives": "متابعة تفعيل التعلم النشط.",
            "strengths": "",
            "developmentAreas": "",
            "recommendations": "",
            "followupDate": later,
            "followupNotes": "",
            "status": "planned",
        })
        self.assertEqual(created.status_code, 201)
        visit_id = created.json()["id"]

        planned = self.client.get(f"/api/supervision/visits/{visit_id}")
        self.assertEqual(planned.status_code, 200)
        self.assertEqual(planned.json()["effectiveStatus"], "planned")
        self.assertFalse(planned.json()["reportReady"])

        boot_planned = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == visit_id for item in boot_planned["visits"]))
        self.assertGreaterEqual(boot_planned["dashboard"]["upcomingVisits"], 1)

        followup = self.client.patch(f"/api/supervision/visits/{visit_id}", json={
            "teacherId": 1,
            "visitType": "زيارة تطويرية",
            "visitDate": yesterday,
            "periodLabel": "الحصة الثالثة",
            "grade": "العاشر",
            "lessonTitle": "القوى والحركة",
            "objectives": "متابعة تفعيل التعلم النشط.",
            "strengths": "وضوح الهدف وتنوع الأسئلة الصفية.",
            "developmentAreas": "زيادة زمن تعلم الطلبة التعاوني.",
            "recommendations": "تنفيذ مهمة تعلم ثنائية مع تقويم ختامي قصير.",
            "followupDate": yesterday,
            "followupNotes": "تحتاج متابعة أثر التوصية.",
            "status": "needs_followup",
        })
        self.assertEqual(followup.status_code, 200)
        self.assertEqual(followup.json()["effectiveStatus"], "overdue")
        self.assertTrue(followup.json()["reportReady"])

        overdue_action = self.client.post(f"/api/supervision/visits/{visit_id}/actions", json={
            "title": "تنفيذ نشاط تعلم ثنائي",
            "responsibleTeacherId": 1,
            "dueDate": yesterday,
            "status": "in_progress",
            "notes": "يراجع أثره في الزيارة القادمة.",
        })
        self.assertEqual(overdue_action.status_code, 201)
        self.assertEqual(overdue_action.json()["status"], "overdue")
        self.assertEqual(overdue_action.json()["baseStatus"], "in_progress")
        action_id = overdue_action.json()["id"]

        completed_action = self.client.post(f"/api/supervision/visits/{visit_id}/actions", json={
            "title": "إعداد سؤال خروج قصير",
            "responsibleTeacherId": 1,
            "dueDate": yesterday,
            "status": "completed",
            "notes": "تم التنفيذ.",
        })
        self.assertEqual(completed_action.status_code, 201)
        self.assertEqual(completed_action.json()["status"], "completed")
        self.assertIsNotNone(completed_action.json()["completedAt"])

        detail = self.client.get(f"/api/supervision/visits/{visit_id}").json()
        self.assertEqual(detail["openActionCount"], 1)
        self.assertEqual(detail["completedActionCount"], 1)
        self.assertEqual(detail["overdueActionCount"], 1)
        self.assertEqual(len(detail["actions"]), 2)
        self.assertTrue(any("إجراء متابعة" in item["title"] for item in detail["timeline"]))

        boot_followup = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == visit_id for item in boot_followup["supervisionAttention"]))
        self.assertGreaterEqual(boot_followup["dashboard"]["visitProgress"], 0)

        profile_after = self.client.get("/api/teachers/1/profile").json()["stats"]
        self.assertEqual(profile_after["visitCount"], profile_before["visitCount"] + 1)
        self.assertEqual(profile_after["openFollowupCount"], profile_before["openFollowupCount"] + 1)

        action_done = self.client.patch(f"/api/supervision/visits/{visit_id}/actions/{action_id}", json={
            "title": "تنفيذ نشاط تعلم ثنائي",
            "responsibleTeacherId": 1,
            "dueDate": yesterday,
            "status": "completed",
            "notes": "تم التنفيذ والتحقق.",
        })
        self.assertEqual(action_done.status_code, 200)
        self.assertEqual(action_done.json()["status"], "completed")

        closed = self.client.patch(f"/api/supervision/visits/{visit_id}", json={
            "teacherId": 1,
            "visitType": "زيارة متابعة",
            "visitDate": yesterday,
            "periodLabel": "الحصة الثالثة",
            "grade": "العاشر",
            "lessonTitle": "القوى والحركة",
            "objectives": "التحقق من أثر التوصية.",
            "strengths": "تحسن تفاعل الطلبة.",
            "developmentAreas": "استمرار الممارسة.",
            "recommendations": "استمرار الاستراتيجية.",
            "followupDate": tomorrow,
            "followupNotes": "أغلقت المتابعة بعد تحقق الأثر.",
            "status": "closed",
        })
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "closed")
        self.assertIsNotNone(closed.json()["closedAt"])

        profile_closed = self.client.get("/api/teachers/1/profile").json()["stats"]
        self.assertEqual(profile_closed["openFollowupCount"], profile_before["openFollowupCount"])
        boot_closed = self.client.get("/api/bootstrap").json()
        self.assertFalse(any(item["id"] == visit_id for item in boot_closed["supervisionAttention"]))


    def test_supervision_overdue_action_promotes_visit_to_attention(self):
        oman_today = datetime.now(timezone(timedelta(hours=4))).date()
        yesterday = (oman_today - timedelta(days=1)).isoformat()
        today = oman_today.isoformat()
        created = self.client.post("/api/supervision/visits", json={
            "teacherId": 2, "visitType": "زيارة تطويرية", "visitDate": today,
            "periodLabel": "الحصة الثانية", "grade": "العاشر", "lessonTitle": "تفاعل كيميائي",
            "objectives": "متابعة التفاعل الصفي.", "strengths": "تنظيم جيد.",
            "developmentAreas": "زيادة مشاركة الطلبة.", "recommendations": "تنفيذ مهمة متابعة.",
            "followupDate": None, "followupNotes": "", "status": "completed",
        })
        self.assertEqual(created.status_code, 201)
        visit_id = created.json()["id"]

        action = self.client.post(f"/api/supervision/visits/{visit_id}/actions", json={
            "title": "تنفيذ مهمة متابعة قصيرة", "responsibleTeacherId": 2,
            "dueDate": yesterday, "status": "in_progress", "notes": "",
        })
        self.assertEqual(action.status_code, 201)
        self.assertEqual(action.json()["status"], "overdue")

        detail = self.client.get(f"/api/supervision/visits/{visit_id}").json()
        self.assertEqual(detail["status"], "completed")
        self.assertEqual(detail["effectiveStatus"], "overdue")
        self.assertEqual(detail["overdueActionCount"], 1)
        boot = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == visit_id for item in boot["supervisionAttention"]))

    def test_supervision_validation_and_not_found_guards(self):
        oman_today = datetime.now(timezone(timedelta(hours=4))).date()
        today = oman_today.isoformat()
        yesterday = (oman_today - timedelta(days=1)).isoformat()

        missing_teacher = self.client.post("/api/supervision/visits", json={
            "teacherId": 999999, "visitType": "زيارة صفية", "visitDate": today,
            "periodLabel": "", "grade": "العاشر", "lessonTitle": "", "objectives": "",
            "strengths": "", "developmentAreas": "", "recommendations": "",
            "followupDate": None, "followupNotes": "", "status": "planned",
        })
        self.assertEqual(missing_teacher.status_code, 422)

        invalid_followup = self.client.post("/api/supervision/visits", json={
            "teacherId": 1, "visitType": "زيارة صفية", "visitDate": today,
            "periodLabel": "", "grade": "العاشر", "lessonTitle": "", "objectives": "",
            "strengths": "", "developmentAreas": "", "recommendations": "",
            "followupDate": yesterday, "followupNotes": "", "status": "planned",
        })
        self.assertEqual(invalid_followup.status_code, 422)
        self.assertEqual(self.client.get("/api/supervision/visits/999999").status_code, 404)

        visit = self.client.post("/api/supervision/visits", json={
            "teacherId": 1, "visitType": "زيارة صفية", "visitDate": today,
            "periodLabel": "", "grade": "العاشر", "lessonTitle": "", "objectives": "",
            "strengths": "", "developmentAreas": "", "recommendations": "",
            "followupDate": None, "followupNotes": "", "status": "planned",
        })
        self.assertEqual(visit.status_code, 201)
        visit_id = visit.json()["id"]

        bad_responsible = self.client.post(f"/api/supervision/visits/{visit_id}/actions", json={
            "title": "إجراء بمسؤول مفقود", "responsibleTeacherId": 999999,
            "dueDate": today, "status": "new", "notes": "",
        })
        self.assertEqual(bad_responsible.status_code, 422)
        missing_visit_action = self.client.post("/api/supervision/visits/999999/actions", json={
            "title": "إجراء لزيارة مفقودة", "responsibleTeacherId": None,
            "dueDate": today, "status": "new", "notes": "",
        })
        self.assertEqual(missing_visit_action.status_code, 404)
        self.assertEqual(self.client.delete(f"/api/supervision/visits/{visit_id}/actions/999999").status_code, 404)
        self.assertEqual(self.client.patch("/api/supervision/visits/999999", json={
            "teacherId": 1, "visitType": "زيارة صفية", "visitDate": today,
            "periodLabel": "", "grade": "", "lessonTitle": "", "objectives": "",
            "strengths": "", "developmentAreas": "", "recommendations": "",
            "followupDate": None, "followupNotes": "", "status": "planned",
        }).status_code, 404)

    def test_achievement_assessment_and_intervention_lifecycle(self):
        created = self.client.post("/api/achievement/assessments", json={
            "title": "اختبار التحصيل التجريبي", "assessmentType": "اختبار قصير",
            "subject": "الفيزياء", "grade": "العاشر", "assessmentDate": "2026-09-20",
            "term": "الفصل الأول", "academicYear": "2026/2027", "teacherId": 1,
            "maxScore": 40, "studentCount": 30, "averageScore": 22,
            "highestScore": 39, "lowestScore": 8, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 14, "nearMasteryCount": 8, "interventionCount": 8,
            "notes": "سجل تحصيل اختباري", "status": "recorded",
        })
        self.assertEqual(created.status_code, 201)
        assessment = created.json()
        assessment_id = assessment["id"]
        self.assertEqual(assessment["masteryPercent"], 47)
        self.assertEqual(assessment["averagePercent"], 55)
        self.assertEqual(assessment["masteryReferenceSource"], "مرجع اختبار آلي فقط — ليس معيارًا تربويًا")
        self.assertTrue(assessment["analysisReady"])

        boot = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == assessment_id for item in boot["assessments"]))
        self.assertTrue(any(item["id"] == assessment_id for item in boot["achievementAttention"]))
        self.assertIn("achievementMastery", boot["dashboard"])
        self.assertIn("openAchievementActions", boot["dashboard"])

        action = self.client.post(f"/api/achievement/assessments/{assessment_id}/actions", json={
            "actionType": "remedial", "title": "تدخل علاجي موجه",
            "targetGroup": "الطلبة دون حد الإتقان", "responsibleTeacherId": 1,
            "startDate": "2026-09-21", "dueDate": "2026-09-28", "status": "in_progress",
            "baselineIndicator": "إتقان 47%", "targetIndicator": "60% فأعلى",
            "outcomeIndicator": "", "notes": "إعادة قياس بعد التنفيذ",
        })
        self.assertEqual(action.status_code, 201)
        action_id = action.json()["id"]
        self.assertEqual(action.json()["actionType"], "remedial")

        detail = self.client.get(f"/api/achievement/assessments/{assessment_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(any(item["id"] == action_id for item in detail.json()["actions"]))
        self.assertEqual(detail.json()["openActionCount"], 1)

        updated_action = self.client.patch(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}", json={
            "actionType": "remedial", "title": "تدخل علاجي موجه",
            "targetGroup": "الطلبة دون حد الإتقان", "responsibleTeacherId": 1,
            "startDate": "2026-09-21", "dueDate": "2026-09-28", "status": "completed",
            "baselineIndicator": "إتقان 47%", "targetIndicator": "60% فأعلى",
            "outcomeIndicator": "إتقان 63% في إعادة القياس", "notes": "تم القياس اللاحق",
        })
        self.assertEqual(updated_action.status_code, 200)
        self.assertEqual(updated_action.json()["status"], "completed")
        self.assertIsNotNone(updated_action.json()["completedAt"])

        updated = self.client.patch(f"/api/achievement/assessments/{assessment_id}", json={
            "title": "اختبار التحصيل التجريبي", "assessmentType": "اختبار قصير",
            "subject": "الفيزياء", "grade": "العاشر", "assessmentDate": "2026-09-20",
            "term": "الفصل الأول", "academicYear": "2026/2027", "teacherId": 1,
            "maxScore": 40, "studentCount": 30, "averageScore": 27,
            "highestScore": 40, "lowestScore": 12, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 20, "nearMasteryCount": 6, "interventionCount": 4,
            "notes": "تحسن بعد التدخل", "status": "reviewed",
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["masteryPercent"], 67)
        self.assertEqual(updated.json()["status"], "reviewed")

        removed = self.client.delete(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}")
        self.assertEqual(removed.status_code, 200)
        final = self.client.get(f"/api/achievement/assessments/{assessment_id}").json()
        self.assertEqual(final["actionCount"], 0)

    def test_impact_evaluation_is_arithmetic_not_pedagogical(self):
        self.assertEqual(evaluate_impact(direction="higher_better", baseline_value=48, target_value=70, outcome_value=None)["impactStatus"], "pending")
        self.assertEqual(evaluate_impact(direction="higher_better", baseline_value=48, target_value=70, outcome_value=75)["impactStatus"], "target_met")
        self.assertEqual(evaluate_impact(direction="higher_better", baseline_value=48, target_value=70, outcome_value=64)["impactStatus"], "improved_not_met")
        self.assertEqual(evaluate_impact(direction="higher_better", baseline_value=48, target_value=70, outcome_value=48)["impactStatus"], "no_change")
        self.assertEqual(evaluate_impact(direction="higher_better", baseline_value=48, target_value=70, outcome_value=42)["impactStatus"], "regressed")
        self.assertEqual(evaluate_impact(direction="lower_better", baseline_value=12, target_value=5, outcome_value=4)["impactStatus"], "target_met")
        self.assertEqual(evaluate_impact(direction="lower_better", baseline_value=12, target_value=5, outcome_value=8)["impactStatus"], "improved_not_met")
        self.assertEqual(evaluate_impact(direction="lower_better", baseline_value=12, target_value=5, outcome_value=14)["impactStatus"], "regressed")

    def test_achievement_action_impact_metric_lifecycle_and_attention(self):
        created = self.client.post("/api/achievement/assessments", json={
            "title": "تقويم قياس أثر اختباري", "assessmentType": "تقويم آخر",
            "subject": "العلوم", "grade": "العاشر", "assessmentDate": "2026-10-01",
            "term": "الفصل الأول", "academicYear": "2026/2027", "teacherId": 1,
            "maxScore": 20, "studentCount": 20, "averageScore": 16,
            "highestScore": 20, "lowestScore": 10, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 18, "nearMasteryCount": 2, "interventionCount": 0,
            "notes": "سجل اختبار بنيوي فقط", "status": "reviewed",
        })
        self.assertEqual(created.status_code, 201)
        assessment_id = created.json()["id"]
        action = self.client.post(f"/api/achievement/assessments/{assessment_id}/actions", json={
            "actionType": "enrichment", "title": "برنامج إثرائي اختباري",
            "targetGroup": "فئة تجريبية", "responsibleTeacherId": 1,
            "startDate": "2026-10-02", "dueDate": "2026-10-10", "status": "completed",
            "baselineIndicator": "وصف محفوظ", "targetIndicator": "هدف محفوظ",
            "outcomeIndicator": "", "notes": "اختبار دورة الأثر",
        })
        self.assertEqual(action.status_code, 201)
        action_id = action.json()["id"]
        self.assertIsNone(action.json()["metric"])

        boot = self.client.get("/api/bootstrap").json()
        attention = next(item for item in boot["achievementAttention"] if item["id"] == assessment_id)
        self.assertEqual(attention["unmeasuredCompletedActionCount"], 1)

        pending_payload = {
            "metricName": "مؤشر داخلي اختباري", "unit": "نقطة", "direction": "higher_better",
            "baselineValue": 10, "targetValue": 15, "outcomeValue": None, "measuredAt": None,
            "referenceSource": "هدف داخلي للاختبار وليس معيارًا وزاريًا",
            "referenceYear": "2026", "referenceNote": "اختبار تقني", "notes": "",
        }
        pending = self.client.put(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric", json=pending_payload)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()["impactStatus"], "pending")

        invalid = dict(pending_payload, outcomeValue=12, measuredAt=None)
        self.assertEqual(self.client.put(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric", json=invalid).status_code, 422)

        no_change = dict(pending_payload, outcomeValue=10, measuredAt="2026-10-11")
        measured = self.client.put(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric", json=no_change)
        self.assertEqual(measured.status_code, 200)
        self.assertEqual(measured.json()["impactStatus"], "no_change")
        boot = self.client.get("/api/bootstrap").json()
        attention = next(item for item in boot["achievementAttention"] if item["id"] == assessment_id)
        self.assertEqual(attention["impactReviewActionCount"], 1)
        self.assertEqual(attention["measuredActionCount"], 1)

        target_met = dict(pending_payload, outcomeValue=16, measuredAt="2026-10-11")
        measured = self.client.put(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric", json=target_met)
        self.assertEqual(measured.json()["impactStatus"], "target_met")
        self.assertEqual(measured.json()["improvementValue"], 6.0)
        detail = self.client.get(f"/api/achievement/assessments/{assessment_id}").json()
        saved_action = next(item for item in detail["actions"] if item["id"] == action_id)
        self.assertEqual(saved_action["metric"]["referenceSource"], "هدف داخلي للاختبار وليس معيارًا وزاريًا")
        self.assertEqual(detail["targetMetActionCount"], 1)
        boot = self.client.get("/api/bootstrap").json()
        self.assertFalse(any(item["id"] == assessment_id for item in boot["achievementAttention"]))

        search = self.client.get("/api/search", params={"q": "مؤشر داخلي اختباري", "section": "achievement"})
        self.assertEqual(search.status_code, 200)
        self.assertTrue(any(item["targetId"] == assessment_id for item in search.json()["results"]))

        report = self.client.get("/api/reports/official", params={"reportType": "achievement", "academicYear": "2026/2027", "term": "الفصل الأول"})
        self.assertEqual(report.status_code, 200)
        intervention_section = next(section for section in report.json()["sections"] if section["id"] == "interventions")
        self.assertTrue(any(row["title"] == "برنامج إثرائي اختباري" for row in intervention_section["rows"]))
        self.assertTrue(any(metric["label"] == "تدخلات مقاسة" for metric in report.json()["metrics"]))

        deleted_metric = self.client.delete(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric")
        self.assertEqual(deleted_metric.status_code, 200)
        detail = self.client.get(f"/api/achievement/assessments/{assessment_id}").json()
        self.assertIsNone(next(item for item in detail["actions"] if item["id"] == action_id)["metric"])
        boot = self.client.get("/api/bootstrap").json()
        self.assertTrue(any(item["id"] == assessment_id and item["unmeasuredCompletedActionCount"] == 1 for item in boot["achievementAttention"]))

        self.assertEqual(self.client.delete(f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric").status_code, 404)
        self.assertEqual(self.client.put(f"/api/achievement/assessments/{assessment_id}/actions/999999/metric", json=pending_payload).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/achievement/assessments/{assessment_id}/actions/999999/metric").status_code, 404)

    def test_achievement_validation_and_overdue_attention(self):
        missing_reference = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة بلا مرجع", "assessmentType": "اختبار", "subject": "العلوم",
            "grade": "العاشر", "assessmentDate": "2026-09-20", "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 1, "maxScore": 40, "studentCount": 10,
            "averageScore": 20, "highestScore": 35, "lowestScore": 5, "masteryThresholdPct": 60,
            "masteredCount": 4, "nearMasteryCount": 3, "interventionCount": 3, "notes": "", "status": "recorded",
        })
        self.assertEqual(missing_reference.status_code, 422)

        bad_counts = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة غير صالحة", "assessmentType": "اختبار", "subject": "الكيمياء",
            "grade": "العاشر", "assessmentDate": "2026-09-20", "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 1, "maxScore": 40, "studentCount": 10,
            "averageScore": 25, "highestScore": 41, "lowestScore": 5, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 6, "nearMasteryCount": 4, "interventionCount": 2, "notes": "", "status": "recorded",
        })
        self.assertEqual(bad_counts.status_code, 422)

        missing_teacher = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة بمعلم مفقود", "assessmentType": "اختبار", "subject": "الكيمياء",
            "grade": "العاشر", "assessmentDate": "2026-09-20", "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 999999, "maxScore": 40, "studentCount": 10,
            "averageScore": 20, "highestScore": 35, "lowestScore": 5, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 4, "nearMasteryCount": 3, "interventionCount": 3, "notes": "", "status": "recorded",
        })
        self.assertEqual(missing_teacher.status_code, 422)
        self.assertEqual(self.client.get("/api/achievement/assessments/999999").status_code, 404)

        oman_today = datetime.now(timezone(timedelta(hours=4))).date()
        yesterday = (oman_today - timedelta(days=1)).isoformat()
        created = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة متابعة متأخرة", "assessmentType": "اختبار", "subject": "العلوم",
            "grade": "الثامن", "assessmentDate": yesterday, "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 3, "maxScore": 20, "studentCount": 20,
            "averageScore": 15, "highestScore": 20, "lowestScore": 8, "masteryThresholdPct": 60, "masteryReferenceSource": "مرجع اختبار آلي فقط — ليس معيارًا تربويًا",
            "masteredCount": 15, "nearMasteryCount": 3, "interventionCount": 2, "notes": "", "status": "recorded",
        })
        self.assertEqual(created.status_code, 201)
        assessment_id = created.json()["id"]
        action = self.client.post(f"/api/achievement/assessments/{assessment_id}/actions", json={
            "actionType": "followup", "title": "متابعة متأخرة", "targetGroup": "طالبان",
            "responsibleTeacherId": 3, "startDate": yesterday, "dueDate": yesterday,
            "status": "in_progress", "baselineIndicator": "", "targetIndicator": "",
            "outcomeIndicator": "", "notes": "",
        })
        self.assertEqual(action.status_code, 201)
        self.assertEqual(action.json()["status"], "overdue")
        boot = self.client.get("/api/bootstrap").json()
        attention = next(item for item in boot["achievementAttention"] if item["id"] == assessment_id)
        self.assertEqual(attention["overdueActionCount"], 1)

        bad_action = self.client.post(f"/api/achievement/assessments/{assessment_id}/actions", json={
            "actionType": "remedial", "title": "تاريخ غير صالح", "targetGroup": "",
            "responsibleTeacherId": 3, "startDate": "2026-10-10", "dueDate": "2026-10-01",
            "status": "new", "baselineIndicator": "", "targetIndicator": "", "outcomeIndicator": "", "notes": "",
        })
        self.assertEqual(bad_action.status_code, 422)
        self.assertEqual(self.client.delete(f"/api/achievement/assessments/{assessment_id}/actions/999999").status_code, 404)

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


def _marsad_v09_report_contract_test(self):
    report_types = ["department", "planning", "achievement", "supervision", "meetings", "events"]
    for report_type in report_types:
        response = self.client.get("/api/reports/official", params={
            "reportType": report_type,
            "academicYear": "2026/2027",
            "term": "الفصل الأول",
        })
        self.assertEqual(response.status_code, 200, report_type)
        body = response.json()
        self.assertEqual(body["reportType"], report_type)
        self.assertEqual(body["academicYear"], "2026/2027")
        self.assertIn("title", body)
        self.assertIn("summary", body)
        self.assertIsInstance(body["metrics"], list)
        self.assertIsInstance(body["sections"], list)
        self.assertIsInstance(body["sourceCounts"], dict)
        for section in body["sections"]:
            self.assertIn("columns", section)
            self.assertIn("rows", section)

    teacher_report = self.client.get("/api/reports/official", params={
        "reportType": "teacher",
        "academicYear": "2026/2027",
        "term": "الفصل الأول",
        "teacherId": 1,
    })
    self.assertEqual(teacher_report.status_code, 200)
    self.assertEqual(teacher_report.json()["teacher"]["id"], 1)

    missing_teacher = self.client.get("/api/reports/official", params={
        "reportType": "teacher",
        "academicYear": "2026/2027",
        "term": "الفصل الأول",
    })
    self.assertEqual(missing_teacher.status_code, 422)

    unsupported = self.client.get("/api/reports/official", params={
        "reportType": "imaginary",
        "academicYear": "2026/2027",
        "term": "الفصل الأول",
    })
    self.assertEqual(unsupported.status_code, 404)


MarsadAlInjazatApiTests.test_official_report_center_contract_and_filters = _marsad_v09_report_contract_test


def _marsad_v010_archive_contract_test(self):
    historical_event = self.client.post("/api/events", json={
        "title": "فعالية أرشيفية للاختبار",
        "eventType": "مبادرة",
        "eventDate": "2025-09-10",
        "location": "المدرسة",
        "audience": "طلبة المدرسة",
        "participantCount": 12,
        "goals": "اختبار اكتشاف العام الدراسي تاريخيًا",
        "summary": "سجل تاريخي تجريبي",
        "outcomes": "مخرج موثق",
        "recommendations": "لا توجد",
        "teacherIds": [1],
    })
    self.assertEqual(historical_event.status_code, 201)

    index = self.client.get("/api/archive/years")
    self.assertEqual(index.status_code, 200)
    body = index.json()
    self.assertEqual(body["currentAcademicYear"], "2026/2027")
    years = {item["academicYear"]: item for item in body["years"]}
    self.assertIn("2026/2027", years)
    self.assertIn("2025/2026", years)
    self.assertTrue(years["2026/2027"]["isCurrent"])
    self.assertFalse(years["2025/2026"]["isCurrent"])

    detail = self.client.get("/api/archive/year", params={"academicYear": "2025/2026"})
    self.assertEqual(detail.status_code, 200)
    archive = detail.json()
    self.assertEqual(archive["academicYear"], "2025/2026")
    self.assertGreaterEqual(archive["sourceCounts"]["events"], 1)
    self.assertGreaterEqual(archive["teacherCount"], 1)
    self.assertTrue(any(section["id"] == "events" and section["rows"] for section in archive["sections"]))
    self.assertTrue(any(item["id"] == 1 for item in archive["teachers"]))

    invalid = self.client.get("/api/archive/year", params={"academicYear": "2026-2027"})
    self.assertEqual(invalid.status_code, 422)
    missing = self.client.get("/api/archive/year", params={"academicYear": "2034/2035"})
    self.assertEqual(missing.status_code, 404)
    read_only = self.client.post("/api/archive/year", params={"academicYear": "2025/2026"})
    self.assertEqual(read_only.status_code, 405)


MarsadAlInjazatApiTests.test_historical_archive_contract_and_year_discovery = _marsad_v010_archive_contract_test



def _marsad_v011_global_search_contract_test(self):
    short = self.client.get("/api/search", params={"q": "ا"})
    self.assertEqual(short.status_code, 200)
    self.assertEqual(short.json()["total"], 0)
    self.assertEqual(short.json()["results"], [])

    teacher = self.client.get("/api/search", params={"q": "أَحْمَــد", "section": "teachers"})
    self.assertEqual(teacher.status_code, 200)
    teacher_body = teacher.json()
    self.assertGreaterEqual(teacher_body["total"], 1)
    self.assertEqual(teacher_body["normalizedQuery"], "احمد")
    self.assertTrue(any(item["entityType"] == "teacher" and item["title"] == "أحمد السالمي" for item in teacher_body["results"]))
    self.assertTrue(all(item["section"] == "teachers" for item in teacher_body["results"]))

    plan = self.client.post("/api/plans", json={
        "title": "خطة الموجات للبحث الشامل", "subject": "الفيزياء", "grade": "العاشر",
        "term": "الفصل الأول", "ownerTeacherId": 1, "startDate": "2026-09-01", "endDate": "2026-12-20",
        "notes": "خطة خاصة بعقد البحث", "status": "active",
    })
    self.assertEqual(plan.status_code, 201)
    plan_id = plan.json()["id"]
    unit = self.client.post(f"/api/plans/{plan_id}/units", json={
        "title": "الحركة الموجية الخاصة", "sequence": 1, "plannedStart": "2026-09-01", "plannedEnd": "2026-09-30",
        "progressPercent": 10, "status": "in_progress", "delayReason": "", "notes": "اختبار نتيجة فرعية",
        "responsibleTeacherId": 1,
    })
    self.assertEqual(unit.status_code, 201)
    planning = self.client.get("/api/search", params={"q": "الحركة الموجية", "section": "planning", "academicYear": "2026/2027"})
    self.assertEqual(planning.status_code, 200)
    planning_body = planning.json()
    self.assertGreaterEqual(planning_body["total"], 1)
    self.assertTrue(any(item["entityType"] == "curriculum_unit" and item["targetView"] == "planning" and item["targetId"] == plan_id for item in planning_body["results"]))
    self.assertTrue(all(item["section"] == "planning" and item["academicYear"] == "2026/2027" for item in planning_body["results"]))

    meeting = self.client.post("/api/meetings", json={
        "title": "اجتماع بحث شامل", "meetingType": "اجتماع قسم", "meetingDate": "2026-09-05",
        "meetingTime": "10:00", "location": "قاعة العلوم", "agenda": "مراجعة التخطيط",
        "discussionSummary": "مناقشة نموذج التخطيط", "notes": "", "status": "held", "attendeeIds": [1, 2],
    })
    self.assertEqual(meeting.status_code, 201)
    meeting_id = meeting.json()["id"]
    created_decision = self.client.post(f"/api/meetings/{meeting_id}/decisions", json={
        "title": "توحيد نموذج التخطيط الأسبوعي", "responsibleTeacherId": 2, "responsibleName": "",
        "dueDate": "2026-09-12", "status": "in_progress", "notes": "اعتماد النموذج الموحد",
    })
    self.assertEqual(created_decision.status_code, 201)
    decision = self.client.get("/api/search", params={"q": "توحيد نموذج التخطيط", "section": "meetings"})
    self.assertEqual(decision.status_code, 200)
    self.assertTrue(any(item["entityType"] == "decision" and item["targetView"] == "meetings" and item["targetId"] == meeting_id for item in decision.json()["results"]))

    historical = self.client.post("/api/events", json={
        "title": "معرض نيوتن التاريخي",
        "eventType": "معرض",
        "eventDate": "2025-10-12",
        "location": "المدرسة",
        "audience": "طلبة الصف العاشر",
        "participantCount": 8,
        "goals": "توثيق تاريخي للبحث",
        "summary": "فعالية خاصة باختبار البحث الشامل",
        "outcomes": "نتيجة موثقة",
        "recommendations": "لا توجد",
        "teacherIds": [1],
    })
    self.assertEqual(historical.status_code, 201)
    filtered = self.client.get("/api/search", params={"q": "نيوتن", "academicYear": "2025/2026"})
    self.assertEqual(filtered.status_code, 200)
    filtered_body = filtered.json()
    self.assertTrue(any(item["section"] == "events" and item["title"] == "معرض نيوتن التاريخي" for item in filtered_body["results"]))
    self.assertTrue(all(item.get("academicYear") in {"2025/2026", None} for item in filtered_body["results"]))

    wrong_year = self.client.get("/api/search", params={"q": "نيوتن", "academicYear": "2026/2027"})
    self.assertEqual(wrong_year.status_code, 200)
    self.assertFalse(any(item["title"] == "معرض نيوتن التاريخي" for item in wrong_year.json()["results"]))

    limited = self.client.get("/api/search", params={"q": "ال", "limit": 2})
    self.assertEqual(limited.status_code, 200)
    self.assertLessEqual(len(limited.json()["results"]), 2)

    bad_section = self.client.get("/api/search", params={"q": "العلوم", "section": "imaginary"})
    self.assertEqual(bad_section.status_code, 422)
    bad_year = self.client.get("/api/search", params={"q": "العلوم", "academicYear": "2026-2027"})
    self.assertEqual(bad_year.status_code, 422)
    read_only = self.client.post("/api/search", params={"q": "العلوم"})
    self.assertEqual(read_only.status_code, 405)


MarsadAlInjazatApiTests.test_global_search_contract_normalization_filters_and_navigation = _marsad_v011_global_search_contract_test


def _marsad_v013_historical_entry_and_longitudinal_scope_test(self):
    current_before = self.client.get('/api/bootstrap', params={'academicYear': '2026/2027'})
    self.assertEqual(current_before.status_code, 200)
    before = current_before.json()
    historical_year = '2024/2025'

    historical_teacher = self.client.post('/api/teachers', json={
        'academicYear': historical_year, 'name': 'معلم تاريخي فقط v013', 'subject': 'العلوم',
        'specialization': 'علوم عامة', 'qualification': 'بكالوريوس تربية', 'experienceYears': 9,
        'workload': 18, 'email': 'historical-only-v013@example.edu', 'phone': '',
    })
    self.assertEqual(historical_teacher.status_code, 201)
    historical_teacher_id = historical_teacher.json()['id']
    self.assertFalse(historical_teacher.json()['linkedExisting'])

    # Reusing an existing professional identity for a historical year must link it, not duplicate it.
    existing_teacher_link = self.client.post('/api/teachers', json={
        'academicYear': historical_year, 'name': 'أحمد السالمي', 'subject': 'الفيزياء',
        'specialization': 'فيزياء', 'qualification': 'بكالوريوس تربية', 'experienceYears': 12,
        'workload': 18, 'email': 'ahmed@example.edu', 'phone': '',
    })
    self.assertEqual(existing_teacher_link.status_code, 201)
    self.assertTrue(existing_teacher_link.json()['linkedExisting'])
    self.assertEqual(existing_teacher_link.json()['id'], 1)

    event = self.client.post('/api/events', json={
        'title': 'فعالية تاريخية صريحة v013', 'eventType': 'مبادرة', 'eventDate': '2024-10-12',
        'academicYear': historical_year, 'location': 'المدرسة', 'audience': 'طلبة المدرسة',
        'participantCount': 18, 'goals': 'توثيق سجل سابق', 'summary': 'إدخال تاريخي صريح',
        'outcomes': 'سجل تشغيلي محفوظ', 'recommendations': '', 'teacherIds': [1],
    })
    self.assertEqual(event.status_code, 201)
    event_id = event.json()['id']

    meeting = self.client.post('/api/meetings', json={
        'title': 'اجتماع تاريخي صريح v013', 'meetingType': 'اجتماع قسم',
        'meetingDate': '2025-02-10', 'meetingTime': '10:00', 'location': 'قاعة العلوم',
        'agenda': 'توثيق قرار سابق', 'discussionSummary': 'سجل تاريخي', 'notes': '',
        'academicYear': historical_year, 'status': 'held', 'attendeeIds': [1, 2],
    })
    self.assertEqual(meeting.status_code, 201)
    meeting_id = meeting.json()['id']

    plan = self.client.post('/api/plans', json={
        'title': 'خطة تاريخية صريحة v013', 'subject': 'الفيزياء', 'grade': 'العاشر',
        'term': 'الفصل الأول', 'academicYear': historical_year, 'ownerTeacherId': 1,
        'startDate': '2024-09-01', 'endDate': '2025-01-30', 'notes': 'خطة سنة سابقة', 'status': 'completed',
    })
    self.assertEqual(plan.status_code, 201)
    plan_id = plan.json()['id']

    visit = self.client.post('/api/supervision/visits', json={
        'teacherId': 1, 'visitType': 'زيارة صفية', 'visitDate': '2024-11-06',
        'academicYear': historical_year, 'periodLabel': 'الحصة الثالثة', 'grade': 'العاشر',
        'lessonTitle': 'درس تاريخي', 'objectives': 'هدف موثق', 'strengths': 'قوة موثقة',
        'developmentAreas': 'جانب تطوير', 'recommendations': 'توصية محفوظة',
        'followupDate': '2024-11-20', 'followupNotes': 'متابعة تاريخية', 'status': 'closed',
    })
    self.assertEqual(visit.status_code, 201)
    visit_id = visit.json()['id']

    assessment = self.client.post('/api/achievement/assessments', json={
        'title': 'تقويم تاريخي صريح v013', 'assessmentType': 'اختبار قصير',
        'subject': 'الفيزياء', 'grade': 'العاشر', 'assessmentDate': '2024-12-05',
        'term': 'الفصل الأول', 'academicYear': historical_year, 'teacherId': 1,
        'maxScore': 40, 'studentCount': 20, 'averageScore': 26, 'highestScore': 38, 'lowestScore': 12,
        'masteryThresholdPct': 60,
        'masteryReferenceSource': 'مرجع مدخل للاختبار البنيوي فقط — لا يمثل معيارًا وزاريًا',
        'masteredCount': 12, 'nearMasteryCount': 5, 'interventionCount': 3,
        'notes': 'اختبار فصل السنوات فقط', 'status': 'reviewed',
    })
    self.assertEqual(assessment.status_code, 201)
    assessment_id = assessment.json()['id']

    document = self.client.post(
        '/api/documents',
        data={
            'title': 'وثيقة تاريخية صريحة v013', 'category': 'تحليل نتائج',
            'academicYear': historical_year, 'teacherId': '1', 'subject': 'الفيزياء', 'grade': 'العاشر',
        },
        files={'file': ('historical-analysis.pdf', b'%PDF-1.4\nhistorical\n', 'application/pdf')},
    )
    self.assertEqual(document.status_code, 201)
    document_id = document.json()['id']
    self.assertEqual(document.json()['academicYear'], historical_year)
    self.assertEqual(document.json()['status'], 'approved')

    # The current operating year must remain clean after historical backfill.
    current_after = self.client.get('/api/bootstrap', params={'academicYear': '2026/2027'})
    self.assertEqual(current_after.status_code, 200)
    current = current_after.json()
    self.assertEqual(current['currentAcademicYear'], '2026/2027')
    self.assertEqual(current['academicYear'], '2026/2027')
    self.assertFalse(any(item['id'] == event_id for item in current['events']))
    self.assertFalse(any(item['id'] == meeting_id for item in current['meetings']))
    self.assertFalse(any(item['id'] == plan_id for item in current['plans']))
    self.assertFalse(any(item['id'] == visit_id for item in current['visits']))
    self.assertFalse(any(item['id'] == assessment_id for item in current['assessments']))
    self.assertFalse(any(item['id'] == document_id for item in current['documents']))
    self.assertFalse(any(item['id'] == historical_teacher_id for item in current['teachers']))
    self.assertEqual(current['dashboard']['teacherCount'], before['dashboard']['teacherCount'])
    self.assertFalse(any('تاريخي صريح v013' in item.get('title', '') for item in current['activities']))
    # Historical insertion cannot change current-year operational dashboard counts for these scopes.
    for key in ('openDecisions', 'upcomingVisits', 'planProgress', 'visitProgress', 'achievementMastery', 'openAchievementActions'):
        self.assertEqual(current['dashboard'][key], before['dashboard'][key], key)

    historical = self.client.get('/api/bootstrap', params={'academicYear': historical_year})
    self.assertEqual(historical.status_code, 200)
    old = historical.json()
    self.assertEqual(old['academicYear'], historical_year)
    self.assertEqual(old['currentAcademicYear'], '2026/2027')
    self.assertIn(historical_year, old['availableAcademicYears'])
    self.assertTrue(any(item['id'] == event_id for item in old['events']))
    self.assertTrue(any(item['id'] == meeting_id for item in old['meetings']))
    self.assertTrue(any(item['id'] == plan_id for item in old['plans']))
    self.assertTrue(any(item['id'] == visit_id for item in old['visits']))
    self.assertTrue(any(item['id'] == assessment_id for item in old['assessments']))
    self.assertTrue(any(item['id'] == document_id for item in old['documents']))
    self.assertTrue(any(item['id'] == historical_teacher_id for item in old['teachers']))
    self.assertGreaterEqual(old['dashboard']['teacherCount'], 1)
    self.assertTrue(any('تاريخي صريح v013' in item.get('title', '') for item in old['activities']))

    # Search and archive use the same explicit year instead of a parallel archive copy.
    search = self.client.get('/api/search', params={'q': 'صريح v013', 'academicYear': historical_year})
    self.assertEqual(search.status_code, 200)
    self.assertGreaterEqual(search.json()['total'], 4)
    self.assertTrue(all(item.get('academicYear') in {historical_year, None} for item in search.json()['results']))
    archive = self.client.get('/api/archive/year', params={'academicYear': historical_year})
    self.assertEqual(archive.status_code, 200)
    self.assertGreaterEqual(archive.json()['sourceCounts']['events'], 1)
    self.assertGreaterEqual(archive.json()['sourceCounts']['plans'], 1)
    self.assertGreaterEqual(archive.json()['sourceCounts']['assessments'], 1)

    # Explicit record year is editable: moving the event changes its working-year scope.
    moved = self.client.patch(f'/api/events/{event_id}', json={
        'title': 'فعالية تاريخية صريحة v013', 'eventType': 'مبادرة', 'eventDate': '2025-10-12',
        'academicYear': '2025/2026', 'location': 'المدرسة', 'audience': 'طلبة المدرسة',
        'participantCount': 18, 'goals': 'توثيق سجل سابق', 'summary': 'نقل سنة السجل',
        'outcomes': 'سجل تشغيلي محفوظ', 'recommendations': '', 'teacherIds': [1],
    })
    self.assertEqual(moved.status_code, 200)
    self.assertEqual(moved.json()['academicYear'], '2025/2026')
    old_after_move = self.client.get('/api/bootstrap', params={'academicYear': historical_year}).json()
    self.assertFalse(any(item['id'] == event_id for item in old_after_move['events']))
    next_year = self.client.get('/api/bootstrap', params={'academicYear': '2025/2026'}).json()
    self.assertTrue(any(item['id'] == event_id for item in next_year['events']))

    # Validation is structural only: no invented Omani term boundaries, but obvious year/date mismatch is rejected.
    bad_year = self.client.get('/api/bootstrap', params={'academicYear': '2024-2025'})
    self.assertEqual(bad_year.status_code, 422)
    mismatch = self.client.post('/api/events', json={
        'title': 'سجل بسنة غير منسجمة', 'eventType': 'فعالية', 'eventDate': '2026-10-12',
        'academicYear': historical_year, 'location': '', 'audience': '', 'participantCount': 0,
        'goals': '', 'summary': '', 'outcomes': '', 'recommendations': '', 'teacherIds': [],
    })
    self.assertEqual(mismatch.status_code, 422)


MarsadAlInjazatApiTests.test_historical_entry_longitudinal_scope_and_current_year_isolation = _marsad_v013_historical_entry_and_longitudinal_scope_test


def _marsad_v013_mixed_mastery_standards_guard_test(self):
    base = {
        'assessmentType': 'اختبار قصير', 'subject': 'العلوم', 'grade': 'العاشر',
        'assessmentDate': '2026-10-20', 'term': 'الفصل الأول', 'academicYear': '2026/2027',
        'teacherId': 1, 'maxScore': 40, 'studentCount': 10, 'averageScore': 25,
        'highestScore': 38, 'lowestScore': 10, 'masteredCount': 6, 'nearMasteryCount': 2,
        'interventionCount': 2, 'notes': 'اختبار حارس عدم التجميع', 'status': 'recorded',
        'masteryReferenceNote': 'اختبار تقني فقط ولا يمثل معيارًا تربويًا.',
    }
    first = self.client.post('/api/achievement/assessments', json={
        **base, 'title': 'حارس مرجع مختلف أ', 'masteryThresholdPct': 60,
        'masteryReferenceSource': 'مرجع اختباري أ — ليس معيارًا وزاريًا', 'masteryReferenceYear': 'test-a',
    })
    self.assertEqual(first.status_code, 201)
    second = self.client.post('/api/achievement/assessments', json={
        **base, 'title': 'حارس مرجع مختلف ب', 'assessmentDate': '2026-10-21', 'masteryThresholdPct': 70,
        'masteryReferenceSource': 'مرجع اختباري ب — ليس معيارًا وزاريًا', 'masteryReferenceYear': 'test-b',
    })
    self.assertEqual(second.status_code, 201)

    boot = self.client.get('/api/bootstrap', params={'academicYear': '2026/2027'}).json()
    self.assertFalse(boot['dashboard']['achievementMasteryComparable'])
    self.assertEqual(boot['dashboard']['achievementMastery'], 0)

    report = self.client.get('/api/reports/official', params={
        'reportType': 'achievement', 'academicYear': '2026/2027', 'term': 'الفصل الأول',
    })
    self.assertEqual(report.status_code, 200)
    metric = next(item for item in report.json()['metrics'] if item['label'] == 'الفئة المحققة للحد عبر التقويمات')
    self.assertEqual(metric['value'], 'غير مجمعة')
    self.assertIn('تختلف', metric.get('detail', ''))


MarsadAlInjazatApiTests.test_zz_mixed_mastery_standards_are_not_aggregated = _marsad_v013_mixed_mastery_standards_guard_test


def _marsad_v0131_historical_teacher_directory_and_auto_year_link_test(self):
    historical_year = '2022/2023'
    empty_scope = self.client.get('/api/bootstrap', params={'academicYear': historical_year})
    self.assertEqual(empty_scope.status_code, 200)
    scope = empty_scope.json()
    self.assertEqual(scope['academicYear'], historical_year)
    self.assertEqual(scope['teachers'], [])
    self.assertGreaterEqual(len(scope['teacherDirectory']), 6)
    directory_ids = {item['id'] for item in scope['teacherDirectory']}
    self.assertTrue({1, 2, 3, 4, 5, 6}.issubset(directory_ids))

    meeting = self.client.post('/api/meetings', json={
        'title': 'اجتماع دليل المعلمين التاريخي v0131', 'meetingType': 'اجتماع قسم',
        'meetingDate': '2022-10-10', 'meetingTime': '10:00', 'location': 'قاعة العلوم',
        'agenda': 'اختبار اختيار الحضور من الدليل', 'discussionSummary': 'اختبار تقني',
        'notes': '', 'academicYear': historical_year, 'status': 'held', 'attendeeIds': [1, 2],
    })
    self.assertEqual(meeting.status_code, 201)

    plan = self.client.post('/api/plans', json={
        'title': 'خطة دليل تاريخية v0131', 'subject': 'العلوم', 'grade': 'العاشر',
        'term': 'الفصل الأول', 'academicYear': historical_year, 'ownerTeacherId': 3,
        'startDate': '2022-09-01', 'endDate': '2023-01-31', 'notes': '', 'status': 'completed',
    })
    self.assertEqual(plan.status_code, 201)

    visit = self.client.post('/api/supervision/visits', json={
        'teacherId': 4, 'visitType': 'زيارة صفية', 'visitDate': '2022-11-06',
        'academicYear': historical_year, 'periodLabel': 'الحصة الثالثة', 'grade': 'العاشر',
        'lessonTitle': 'درس تاريخي v0131', 'objectives': '', 'strengths': '',
        'developmentAreas': '', 'recommendations': '', 'followupDate': '',
        'followupNotes': '', 'status': 'completed',
    })
    self.assertEqual(visit.status_code, 201)

    assessment = self.client.post('/api/achievement/assessments', json={
        'title': 'تقويم دليل تاريخي v0131', 'assessmentType': 'اختبار قصير',
        'subject': 'العلوم', 'grade': 'العاشر', 'assessmentDate': '2022-12-05',
        'term': 'الفصل الأول', 'academicYear': historical_year, 'teacherId': 5,
        'maxScore': 40, 'studentCount': 10, 'averageScore': 25, 'highestScore': 38, 'lowestScore': 10,
        'masteryThresholdPct': 60,
        'masteryReferenceSource': 'مرجع تقني للاختبار فقط — لا يمثل معيارًا وزاريًا',
        'masteryReferenceYear': '', 'masteryReferenceNote': 'اختبار ربط الدليل التاريخي.',
        'masteredCount': 6, 'nearMasteryCount': 2, 'interventionCount': 2,
        'notes': '', 'status': 'recorded',
    })
    self.assertEqual(assessment.status_code, 201)

    event = self.client.post('/api/events', json={
        'title': 'فعالية دليل تاريخية v0131', 'eventType': 'فعالية', 'eventDate': '2023-02-12',
        'academicYear': historical_year, 'location': 'المدرسة', 'audience': 'طلبة المدرسة',
        'participantCount': 10, 'goals': '', 'summary': '', 'outcomes': '', 'recommendations': '',
        'teacherIds': [6],
    })
    self.assertEqual(event.status_code, 201)

    with connect() as conn:
        linked_ids = {
            row['teacher_id'] for row in conn.execute(
                'SELECT teacher_id FROM teacher_record_years WHERE academic_year = ?',
                (historical_year,),
            ).fetchall()
        }
    self.assertTrue({1, 2, 3, 4, 5, 6}.issubset(linked_ids))

    scoped_after = self.client.get('/api/bootstrap', params={'academicYear': historical_year})
    self.assertEqual(scoped_after.status_code, 200)
    body = scoped_after.json()
    self.assertTrue({1, 2, 3, 4, 5, 6}.issubset({item['id'] for item in body['teachers']}))
    meeting_detail = self.client.get(f"/api/meetings/{meeting.json()['id']}")
    self.assertEqual(meeting_detail.status_code, 200)
    self.assertEqual({item['id'] for item in meeting_detail.json()['attendees']}, {1, 2})


MarsadAlInjazatApiTests.test_historical_teacher_directory_and_auto_year_link = _marsad_v0131_historical_teacher_directory_and_auto_year_link_test
