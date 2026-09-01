from __future__ import annotations

import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
YEAR = "2026/2027"
HISTORICAL_YEAR = "2025/2026"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def require(response: httpx.Response, expected: int, label: str) -> httpx.Response:
    if response.status_code != expected:
        raise RuntimeError(
            f"{label}: expected HTTP {expected}, got {response.status_code}: {response.text[:800]}"
        )
    return response


def wait_until_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 25
    last_error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"uvicorn exited early with {process.returncode}:\n{output}")
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=1.0)
            if response.status_code == 200 and response.json().get("ok"):
                return
        except Exception as exc:  # startup polling only
            last_error = str(exc)
        time.sleep(0.15)
    raise RuntimeError(f"server did not become ready: {last_error}")


def start_server(env: dict[str, str], port: int) -> tuple[subprocess.Popen[str], str]:
    base_url = f"http://127.0.0.1:{port}"
    run_env = os.environ.copy()
    run_env.update(env)
    run_env["APP_PUBLIC_URL"] = base_url
    run_env["APP_FRONTEND_URL"] = base_url
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    wait_until_ready(base_url, process)
    return process, base_url


def stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="marsad-s0-e2e-") as temp_root:
        root = Path(temp_root)
        data_dir = root / "data"
        uploads_dir = root / "uploads" / "inbox"
        event_uploads_dir = root / "uploads" / "events"
        backups_dir = root / "backups"
        env = {
            "APP_ENV": "testing",
            "ACADEMIC_YEAR": YEAR,
            "APP_DATA_DIR": str(data_dir),
            "APP_UPLOADS_DIR": str(uploads_dir),
            "APP_EVENT_UPLOADS_DIR": str(event_uploads_dir),
            "APP_BACKUP_DIR": str(backups_dir),
            "APP_AUTO_BACKUP_ON_STARTUP": "false",
            "STORAGE_MODE": "local",
        }

        port = free_port()
        process, base_url = start_server(env, port)
        created_ids: dict[str, int] = {}
        event_media_bytes = b"\x89PNG\r\n\x1a\nMARSAD-S0-E2E"

        try:
            with httpx.Client(base_url=base_url, timeout=12.0) as client:
                require(client.get("/api/health"), 200, "health")
                ready = require(client.get("/api/ready"), 200, "ready").json()
                if not ready.get("ok"):
                    raise RuntimeError(f"readiness reported not ok: {ready}")

                teacher = require(
                    client.post(
                        "/api/teachers",
                        json={
                            "academicYear": YEAR,
                            "name": "معلم فحص S0",
                            "subject": "الفيزياء",
                            "specialization": "فيزياء",
                            "qualification": "بكالوريوس تربية",
                            "experienceYears": 9,
                            "workload": 18,
                            "email": "marsad-s0-e2e@example.edu",
                            "phone": "",
                        },
                    ),
                    201,
                    "create teacher",
                ).json()
                teacher_id = int(teacher["id"])
                created_ids["teacher"] = teacher_id

                require(
                    client.patch(
                        f"/api/teachers/{teacher_id}/profile",
                        json={
                            "academicYear": YEAR,
                            "name": "معلم فحص S0",
                            "subject": "الفيزياء",
                            "specialization": "فيزياء",
                            "qualification": "بكالوريوس تربية",
                            "experienceYears": 9,
                            "workload": 18,
                            "email": "marsad-s0-e2e@example.edu",
                            "phone": "",
                            "employeeNumber": "S0-001",
                            "schoolJoinYear": 2020,
                            "grades": "العاشر",
                            "responsibilities": "فحص انحدار النظام",
                            "professionalSummary": "سجل آلي خاص باختبار S0.",
                        },
                    ),
                    200,
                    "update teacher profile",
                )
                require(
                    client.post(
                        f"/api/teachers/{teacher_id}/cv-items",
                        json={
                            "itemType": "course",
                            "title": "دورة فحص S0",
                            "organization": "المدرسة",
                            "startYear": 2026,
                            "endYear": 2026,
                            "description": "عنصر تحقق آلي",
                        },
                    ),
                    201,
                    "create CV item",
                )

                meeting = require(
                    client.post(
                        "/api/meetings",
                        json={
                            "title": "اجتماع فحص S0",
                            "meetingType": "اجتماع قسم",
                            "meetingDate": "2026-09-10",
                            "academicYear": YEAR,
                            "meetingTime": "10:00",
                            "location": "مختبر العلوم",
                            "agenda": "فحص استمرارية دورة العمل",
                            "discussionSummary": "تم تنفيذ اختبار آلي للمسار.",
                            "notes": "",
                            "status": "held",
                            "attendeeIds": [teacher_id],
                        },
                    ),
                    201,
                    "create meeting",
                ).json()
                meeting_id = int(meeting["id"])
                created_ids["meeting"] = meeting_id
                require(
                    client.post(
                        f"/api/meetings/{meeting_id}/decisions",
                        json={
                            "title": "قرار فحص S0",
                            "responsibleTeacherId": teacher_id,
                            "responsibleName": "",
                            "dueDate": "2026-09-20",
                            "status": "in_progress",
                            "notes": "",
                        },
                    ),
                    201,
                    "create meeting decision",
                )

                plan = require(
                    client.post(
                        "/api/plans",
                        json={
                            "title": "خطة فحص S0",
                            "subject": "الفيزياء",
                            "grade": "العاشر",
                            "term": "الفصل الأول",
                            "academicYear": YEAR,
                            "ownerTeacherId": teacher_id,
                            "startDate": "2026-09-01",
                            "endDate": "2026-12-20",
                            "notes": "",
                            "status": "active",
                        },
                    ),
                    201,
                    "create plan",
                ).json()
                plan_id = int(plan["id"])
                created_ids["plan"] = plan_id
                require(
                    client.post(
                        f"/api/plans/{plan_id}/units",
                        json={
                            "title": "وحدة فحص S0",
                            "sequence": 1,
                            "plannedStart": "2026-09-01",
                            "plannedEnd": "2026-09-30",
                            "progressPercent": 35,
                            "status": "in_progress",
                            "delayReason": "",
                            "notes": "",
                            "responsibleTeacherId": teacher_id,
                        },
                    ),
                    201,
                    "create plan unit",
                )

                visit = require(
                    client.post(
                        "/api/supervision/visits",
                        json={
                            "teacherId": teacher_id,
                            "visitType": "زيارة تطويرية",
                            "visitDate": "2026-09-12",
                            "academicYear": YEAR,
                            "periodLabel": "الحصة الثالثة",
                            "grade": "العاشر",
                            "lessonTitle": "فحص S0",
                            "objectives": "فحص دورة الإشراف.",
                            "strengths": "تنظيم جيد.",
                            "developmentAreas": "متابعة أثر الإجراء.",
                            "recommendations": "تنفيذ متابعة قصيرة.",
                            "followupDate": "2026-09-22",
                            "followupNotes": "",
                            "status": "needs_followup",
                        },
                    ),
                    201,
                    "create supervision visit",
                ).json()
                visit_id = int(visit["id"])
                created_ids["visit"] = visit_id
                require(
                    client.post(
                        f"/api/supervision/visits/{visit_id}/actions",
                        json={
                            "title": "إجراء متابعة S0",
                            "responsibleTeacherId": teacher_id,
                            "dueDate": "2026-09-22",
                            "status": "in_progress",
                            "notes": "",
                        },
                    ),
                    201,
                    "create supervision action",
                )

                assessment = require(
                    client.post(
                        "/api/achievement/assessments",
                        json={
                            "title": "تقويم فحص S0",
                            "assessmentType": "اختبار قصير",
                            "subject": "الفيزياء",
                            "grade": "العاشر",
                            "assessmentDate": "2026-09-15",
                            "term": "الفصل الأول",
                            "academicYear": YEAR,
                            "teacherId": teacher_id,
                            "maxScore": 40,
                            "studentCount": 30,
                            "averageScore": 24,
                            "highestScore": 39,
                            "lowestScore": 8,
                            "masteryThresholdPct": 60,
                            "masteryReferenceSource": "مرجع تقني لاختبار S0 فقط",
                            "masteryReferenceYear": "2026",
                            "masteryReferenceNote": "لا يمثل معيارًا تربويًا.",
                            "masteredCount": 18,
                            "nearMasteryCount": 7,
                            "interventionCount": 5,
                            "notes": "",
                            "status": "recorded",
                        },
                    ),
                    201,
                    "create assessment",
                ).json()
                assessment_id = int(assessment["id"])
                created_ids["assessment"] = assessment_id
                action = require(
                    client.post(
                        f"/api/achievement/assessments/{assessment_id}/actions",
                        json={
                            "actionType": "remedial",
                            "title": "تدخل فحص S0",
                            "targetGroup": "خمسة طلاب",
                            "responsibleTeacherId": teacher_id,
                            "startDate": "2026-09-16",
                            "dueDate": "2026-09-25",
                            "status": "completed",
                            "baselineIndicator": "10",
                            "targetIndicator": "15",
                            "outcomeIndicator": "16",
                            "notes": "",
                        },
                    ),
                    201,
                    "create achievement action",
                ).json()
                action_id = int(action["id"])
                require(
                    client.put(
                        f"/api/achievement/assessments/{assessment_id}/actions/{action_id}/metric",
                        json={
                            "metricName": "مؤشر فحص S0",
                            "unit": "نقطة",
                            "direction": "higher_better",
                            "baselineValue": 10,
                            "targetValue": 15,
                            "outcomeValue": 16,
                            "measuredAt": "2026-09-26",
                            "referenceSource": "هدف داخلي لاختبار S0",
                            "referenceYear": "2026",
                            "referenceNote": "",
                            "notes": "",
                        },
                    ),
                    200,
                    "save impact metric",
                )

                event = require(
                    client.post(
                        "/api/events",
                        json={
                            "title": "فعالية فحص S0",
                            "eventType": "مبادرة",
                            "eventDate": "2026-10-12",
                            "academicYear": YEAR,
                            "location": "المدرسة",
                            "audience": "طلبة الصف العاشر",
                            "participantCount": 20,
                            "goals": "فحص مسار الفعاليات.",
                            "summary": "تنفيذ آلي.",
                            "outcomes": "دليل محفوظ.",
                            "recommendations": "",
                            "teacherIds": [teacher_id],
                        },
                    ),
                    201,
                    "create event",
                ).json()
                event_id = int(event["id"])
                created_ids["event"] = event_id
                media = require(
                    client.post(
                        f"/api/events/{event_id}/media",
                        files={"file": ("s0-evidence.png", event_media_bytes, "image/png")},
                        data={"caption": "دليل فحص S0"},
                    ),
                    201,
                    "upload event media",
                ).json()
                media_id = int(media["id"])
                content = require(
                    client.get(f"/api/events/{event_id}/media/{media_id}/content"),
                    200,
                    "read event media",
                )
                if content.content != event_media_bytes:
                    raise RuntimeError("event media bytes changed during round trip")

                document = require(
                    client.post(
                        "/api/documents",
                        data={
                            "title": "وثيقة فحص S0",
                            "category": "وثيقة",
                            "academicYear": YEAR,
                            "teacherId": str(teacher_id),
                            "subject": "الفيزياء",
                            "grade": "العاشر",
                        },
                        files={"file": ("s0-document.pdf", b"%PDF-1.4\nS0\n", "application/pdf")},
                    ),
                    201,
                    "upload direct document",
                ).json()
                created_ids["document"] = int(document["id"])

                upload_request = require(
                    client.post(
                        "/api/requests",
                        json={
                            "teacherId": teacher_id,
                            "requestType": "اختبار",
                            "subject": "الفيزياء",
                            "grade": "العاشر",
                            "title": "طلب رفع فحص S0",
                            "deadline": "2026-09-28",
                            "notes": "",
                            "allowedFiles": "PDF / Word / Excel",
                        },
                    ),
                    201,
                    "create upload request",
                ).json()
                request_id = int(upload_request["id"])
                created_ids["request"] = request_id
                token = upload_request["uploadUrl"].rsplit("/", 1)[-1]
                require(client.get(f"/api/public/upload/{token}"), 200, "open public upload")
                require(
                    client.post(
                        f"/api/public/upload/{token}",
                        files={"file": ("teacher-upload.pdf", b"%PDF-1.4\nTEACHER\n", "application/pdf")},
                    ),
                    201,
                    "public upload",
                )

                historical_event = require(
                    client.post(
                        "/api/events",
                        json={
                            "title": "فعالية تاريخية فحص S0",
                            "eventType": "فعالية",
                            "eventDate": "2025-10-12",
                            "academicYear": HISTORICAL_YEAR,
                            "location": "المدرسة",
                            "audience": "طلبة المدرسة",
                            "participantCount": 12,
                            "goals": "فحص فصل السنوات.",
                            "summary": "سجل تاريخي.",
                            "outcomes": "",
                            "recommendations": "",
                            "teacherIds": [teacher_id],
                        },
                    ),
                    201,
                    "create historical event",
                ).json()
                historical_event_id = int(historical_event["id"])

                search = require(
                    client.get("/api/search", params={"q": "فحص S0", "academicYear": YEAR}),
                    200,
                    "global search",
                ).json()
                if search.get("total", 0) < 5:
                    raise RuntimeError(f"search did not surface enough created records: {search}")

                for report_type in ("department", "planning", "achievement", "supervision", "meetings", "events"):
                    require(
                        client.get(
                            "/api/reports/official",
                            params={"reportType": report_type, "academicYear": YEAR, "term": "الفصل الأول"},
                        ),
                        200,
                        f"report {report_type}",
                    )

                archive_index = require(client.get("/api/archive/years"), 200, "archive years").json()
                years = {item["academicYear"] for item in archive_index["years"]}
                if HISTORICAL_YEAR not in years or YEAR not in years:
                    raise RuntimeError(f"archive year discovery failed: {years}")
                historical = require(
                    client.get("/api/bootstrap", params={"academicYear": HISTORICAL_YEAR}),
                    200,
                    "historical bootstrap",
                ).json()
                if not any(item["id"] == historical_event_id for item in historical["events"]):
                    raise RuntimeError("historical event missing from its work year")
                current = require(
                    client.get("/api/bootstrap", params={"academicYear": YEAR}),
                    200,
                    "current bootstrap",
                ).json()
                if any(item["id"] == historical_event_id for item in current["events"]):
                    raise RuntimeError("historical event leaked into current work year")

        finally:
            stop_server(process)

        db_path = data_dir / "marsad_alinjazat.sqlite3"
        with sqlite3.connect(db_path) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or fk_violations:
            raise RuntimeError(f"SQLite integrity failed: integrity={integrity}, fk={fk_violations}")

        restart_port = free_port()
        restarted, restart_url = start_server(env, restart_port)
        try:
            with httpx.Client(base_url=restart_url, timeout=12.0) as client:
                current = require(
                    client.get("/api/bootstrap", params={"academicYear": YEAR}),
                    200,
                    "bootstrap after restart",
                ).json()
                checks = {
                    "teacher": any(item["id"] == created_ids["teacher"] for item in current["teachers"]),
                    "meeting": any(item["id"] == created_ids["meeting"] for item in current["meetings"]),
                    "plan": any(item["id"] == created_ids["plan"] for item in current["plans"]),
                    "visit": any(item["id"] == created_ids["visit"] for item in current["visits"]),
                    "assessment": any(item["id"] == created_ids["assessment"] for item in current["assessments"]),
                    "event": any(item["id"] == created_ids["event"] for item in current["events"]),
                    "document": any(item["id"] == created_ids["document"] for item in current["documents"]),
                    "request": any(item["id"] == created_ids["request"] for item in current["requests"]),
                }
                failed = [name for name, ok in checks.items() if not ok]
                if failed:
                    raise RuntimeError(f"persistence after restart failed for: {failed}")
        finally:
            stop_server(restarted)

        print("PASS: Marsad S0 real HTTP E2E regression")
        print("INFO: teacher → meeting → plan → supervision → achievement → event → documents → public upload → reports → archive")
        print("INFO: SQLite integrity ok; data persisted after full server restart")


if __name__ == "__main__":
    main()
