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
        self.assertIn("visits", boot.json())
        self.assertIn("supervisionAttention", boot.json())
        self.assertIn("assessments", boot.json())
        self.assertIn("achievementAttention", boot.json())
        self.assertEqual(health.json()["version"], "0.9.0")

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
            "highestScore": 39, "lowestScore": 8, "masteryThresholdPct": 60,
            "masteredCount": 14, "nearMasteryCount": 8, "interventionCount": 8,
            "notes": "سجل تحصيل اختباري", "status": "recorded",
        })
        self.assertEqual(created.status_code, 201)
        assessment = created.json()
        assessment_id = assessment["id"]
        self.assertEqual(assessment["masteryPercent"], 47)
        self.assertEqual(assessment["averagePercent"], 55)
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
            "highestScore": 40, "lowestScore": 12, "masteryThresholdPct": 60,
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

    def test_achievement_validation_and_overdue_attention(self):
        bad_counts = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة غير صالحة", "assessmentType": "اختبار", "subject": "الكيمياء",
            "grade": "العاشر", "assessmentDate": "2026-09-20", "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 1, "maxScore": 40, "studentCount": 10,
            "averageScore": 25, "highestScore": 41, "lowestScore": 5, "masteryThresholdPct": 60,
            "masteredCount": 6, "nearMasteryCount": 4, "interventionCount": 2, "notes": "", "status": "recorded",
        })
        self.assertEqual(bad_counts.status_code, 422)

        missing_teacher = self.client.post("/api/achievement/assessments", json={
            "title": "نتيجة بمعلم مفقود", "assessmentType": "اختبار", "subject": "الكيمياء",
            "grade": "العاشر", "assessmentDate": "2026-09-20", "term": "الفصل الأول",
            "academicYear": "2026/2027", "teacherId": 999999, "maxScore": 40, "studentCount": 10,
            "averageScore": 20, "highestScore": 35, "lowestScore": 5, "masteryThresholdPct": 60,
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
            "averageScore": 15, "highestScore": 20, "lowestScore": 8, "masteryThresholdPct": 60,
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
