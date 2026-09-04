from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package.json"
CONTRACT = ROOT / "supabase" / "schema" / "s2_e1_sqlite_migration_contract.json"
COMPILER = ROOT / "scripts" / "marsad_sqlite_migration_compiler.py"
WORKFLOW = ROOT / ".github" / "workflows" / "quality-pages.yml"
VISIBLE_WORKFLOW = ROOT / "GITHUB_WORKFLOW_VISIBLE" / "quality-pages.yml"
MIGRATIONS = ROOT / "supabase" / "migrations"
EXPECTED_MIGRATIONS = [
    "20260901120000_s2_b1_core_identity_tenancy.sql",
    "20260901190000_s2_b2_teachers_domain.sql",
    "20260901210000_s2_b3_operational_domains.sql",
    "20260902080000_s2_b4_content_intake_domains.sql",
    "20260902090000_s2_b5_schema_hardening.sql",
    "20260903080000_s2_b5_fix1_updated_at_clock.sql",
    "20260903100000_s2_c1_security_foundation.sql",
    "20260903123000_s2_c2_domain_rls_baseline.sql",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def create_fixture(root: Path) -> Path:
    data_dir = root / "data"
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(data_dir)
    env["APP_AUTO_BACKUP_ON_STARTUP"] = "false"
    subprocess.run(
        [sys.executable, "-c", "from server.db import init_db; init_db()"],
        cwd=ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    db = data_dir / "marsad_alinjazat.sqlite3"
    now = "2026-09-04T08:00:00+00:00"
    with sqlite3.connect(db) as conn:
        # init_db seeds demonstration rows; S2-E1 uses a deterministic isolated fixture instead.
        conn.execute("PRAGMA foreign_keys=OFF")
        source_tables = [
            "achievement_action_metrics", "achievement_actions", "achievement_assessment_standards",
            "achievement_assessments", "supervision_actions", "supervision_visits", "curriculum_units",
            "curriculum_plans", "meeting_decisions", "meeting_attendees", "meetings", "activities",
            "event_teacher_links", "event_media_meta", "event_media", "event_record_years", "events",
            "documents", "request_record_years", "upload_requests", "teacher_cv_items",
            "teacher_record_years", "teacher_profiles", "teachers", "settings",
        ]
        for table in source_tables:
            conn.execute(f'DELETE FROM "{table}"')
        conn.execute("DELETE FROM sqlite_sequence")
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)", ("school_theme", "indigo", now))
        conn.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)", ("google_refresh_token", "TOPSECRET", now))
        conn.execute(
            "INSERT INTO teachers(id,name,subject,specialization,qualification,experience_years,workload,cv_completion,email,phone,created_at,updated_at) VALUES(1,?,?,?,?,?,?,?,?,?,?,?)",
            ("معلم فيزياء", "فيزياء", "فيزياء", "بكالوريوس", 12, 20, 90, "teacher@example.com", "90000000", now, now),
        )
        conn.execute(
            "INSERT INTO teacher_profiles(teacher_id,employee_number,school_join_year,grades,responsibilities,professional_summary,updated_at) VALUES(1,?,?,?,?,?,?)",
            ("EMP-1", 2020, "10", "مختبر", "ملف تجريبي", now),
        )
        conn.execute(
            "INSERT INTO teacher_cv_items(id,teacher_id,item_type,title,organization,start_year,end_year,description,created_at,updated_at) VALUES(1,1,'course','دورة','وزارة التربية',2025,2025,'وصف',?,?)",
            (now, now),
        )
        conn.execute("INSERT INTO teacher_record_years(teacher_id,academic_year,created_at,updated_at) VALUES(1,'2025/2026',?,?)", (now, now))
        conn.execute(
            "INSERT INTO upload_requests(id,teacher_id,request_type,subject,grade,title,deadline,notes,allowed_files,token_hash,status,expires_at,created_at,updated_at) VALUES(1,1,'evidence','فيزياء','10','طلب شاهد','2026-09-30','ملاحظة','PDF','fixture-token-hash','waiting_upload','2026-10-01T00:00:00+00:00',?,?)",
            (now, now),
        )
        conn.execute("INSERT INTO request_record_years(request_id,academic_year,created_at,updated_at) VALUES(1,'2026/2027',?,?)", (now, now))
        conn.execute(
            "INSERT INTO documents(id,request_id,teacher_id,title,category,subject,grade,academic_year,original_name,mime_type,size_bytes,storage_provider,storage_file_id,storage_path,web_view_link,status,uploaded_at,approved_at) VALUES(1,1,1,'وثيقة','evidence','فيزياء','10',NULL,'doc.pdf','application/pdf',120,'local',NULL,'uploads/doc.pdf',NULL,'inbox',?,NULL)",
            (now,),
        )
        conn.execute(
            "INSERT INTO events(id,title,event_type,event_date,location,audience,participant_count,goals,summary,outcomes,recommendations,cover_tone,created_at,updated_at) VALUES(1,'فعالية','activity','2026-09-02','المدرسة','الطلبة',20,'هدف','ملخص','نتيجة','توصية','teal',?,?)",
            (now, now),
        )
        conn.execute("INSERT INTO event_record_years(event_id,academic_year,created_at,updated_at) VALUES(1,'2026/2027',?,?)", (now, now))
        conn.execute(
            "INSERT INTO event_media(id,event_id,original_name,mime_type,size_bytes,storage_provider,storage_file_id,storage_path,web_view_link,created_at) VALUES(1,1,'event.jpg','image/jpeg',200,'google_drive','drive-file-1',NULL,'https://example.invalid/view',?)",
            (now,),
        )
        conn.execute("INSERT INTO event_media_meta(media_id,caption,position,is_cover,updated_at) VALUES(1,'غلاف',0,1,?)", (now,))
        conn.execute("INSERT INTO event_teacher_links(event_id,teacher_id,role,created_at) VALUES(1,1,'مشارك',?)", (now,))
        conn.execute("INSERT INTO activities(id,activity_type,title,detail,entity_type,entity_id,created_at) VALUES(1,'created','إنشاء فعالية','تفصيل','event',1,?)", (now,))
        conn.execute(
            "INSERT INTO meetings(id,title,meeting_type,meeting_date,meeting_time,location,agenda,discussion_summary,notes,academic_year,status,created_at,updated_at) VALUES(1,'اجتماع','اجتماع قسم','2026-09-03','10:00','قاعة','أجندة','نقاش','ملاحظات','2026/2027','held',?,?)",
            (now, now),
        )
        conn.execute("INSERT INTO meeting_attendees(meeting_id,teacher_id,attendance_status,created_at) VALUES(1,1,'present',?)", (now,))
        conn.execute(
            "INSERT INTO meeting_decisions(id,meeting_id,title,responsible_teacher_id,responsible_name,due_date,status,notes,completed_at,created_at,updated_at) VALUES(1,1,'قرار',1,'معلم فيزياء','2026-09-20','in_progress','متابعة',NULL,?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO curriculum_plans(id,title,subject,grade,term,academic_year,owner_teacher_id,start_date,end_date,notes,status,created_at,updated_at) VALUES(1,'خطة','فيزياء','10','1','2026/2027',1,'2026-09-01','2027-01-01','ملاحظات','active',?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO curriculum_units(id,plan_id,title,sequence,planned_start,planned_end,progress_percent,status,delay_reason,notes,responsible_teacher_id,created_at,updated_at) VALUES(1,1,'وحدة',1,'2026-09-01','2026-10-01',50,'in_progress',NULL,'ملاحظة',1,?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO supervision_visits(id,teacher_id,visit_type,visit_date,period_label,grade,lesson_title,objectives,strengths,development_areas,recommendations,followup_date,followup_notes,academic_year,status,closed_at,created_at,updated_at) VALUES(1,1,'زيارة صفية','2026-09-04','ح1','10','درس','هدف','قوة','تطوير','توصية',NULL,NULL,'2026/2027','completed',NULL,?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO supervision_actions(id,visit_id,title,responsible_teacher_id,due_date,status,notes,completed_at,created_at,updated_at) VALUES(1,1,'إجراء إشرافي',1,'2026-09-20','new','ملاحظة',NULL,?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO achievement_assessments(id,title,assessment_type,subject,grade,assessment_date,term,academic_year,teacher_id,max_score,student_count,average_score,highest_score,lowest_score,mastery_threshold_pct,mastered_count,near_mastery_count,intervention_count,notes,status,created_at,updated_at) VALUES(1,'اختبار','اختبار','فيزياء','10','2026-09-05','1','2026/2027',1,100,30,72,98,20,60,18,7,5,'ملاحظات','recorded',?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO achievement_assessment_standards(assessment_id,mastery_reference_source,mastery_reference_year,mastery_reference_note,created_at,updated_at) VALUES(1,'مرجع','2026','ملاحظة',?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO achievement_actions(id,assessment_id,action_type,title,target_group,responsible_teacher_id,start_date,due_date,status,baseline_indicator,target_indicator,outcome_indicator,notes,completed_at,created_at,updated_at) VALUES(1,1,'remedial','خطة علاج','فئة',1,'2026-09-06','2026-10-01','in_progress','60','75',NULL,'ملاحظة',NULL,?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO achievement_action_metrics(action_id,metric_name,unit,direction,baseline_value,target_value,outcome_value,measured_at,reference_source,reference_year,reference_note,notes,created_at,updated_at) VALUES(1,'نسبة','%','higher_better',60,75,NULL,NULL,'مرجع','2026','ملاحظة','ملاحظات',?,?)",
            (now, now),
        )
        conn.commit()
    return db


def main() -> None:
    for path in (PACKAGE, CONTRACT, COMPILER, WORKFLOW, VISIBLE_WORKFLOW):
        if not path.exists():
            fail(f"missing S2-E1 file: {path.relative_to(ROOT)}")

    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if package.get("version") != "0.25.0":
        fail("S2-E1 requires package version 0.25.0")

    migrations = sorted(p.name for p in MIGRATIONS.glob("*.sql") if p.is_file())
    if migrations != EXPECTED_MIGRATIONS:
        fail("S2-E1 is compiler/dry-run tooling only and must not add a schema migration")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("phase") != "S2-E1" or contract.get("project_version") != "0.25.0":
        fail("invalid S2-E1 contract identity")
    for key in ("schema_changes_allowed", "rls_changes_allowed", "runtime_switch_allowed", "live_data_commit_allowed", "storage_bytes_migration_allowed", "auth_user_mutation_allowed"):
        if contract.get(key) is not False:
            fail(f"{key} must remain false")
    if contract.get("source_table_count") != 25 or contract.get("target_table_count") != 26:
        fail("source/target table counts drifted")
    if contract.get("dry_run_sql_must_rollback") is not True or contract.get("current_academic_year_must_be_explicit") is not True:
        fail("dry-run safety gates are not mandatory")

    if WORKFLOW.read_bytes() != VISIBLE_WORKFLOW.read_bytes():
        fail("visible workflow copy is not byte-identical")
    wf = WORKFLOW.read_text(encoding="utf-8")
    if "python scripts/check_supabase_s2_e1.py" not in wf:
        fail("CI does not execute S2-E1 guard")

    sys.path.insert(0, str(ROOT / "scripts"))
    from marsad_sqlite_migration_compiler import CompileError, compile_database  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="marsad-s2e1-") as temp:
        temp_root = Path(temp)
        db = create_fixture(temp_root)
        out = temp_root / "out"
        report = compile_database(db, out, "مدرسة مرصد الاختبار", "2026/2027")
        sql_path = out / "marsad_s2_e1_dry_run.sql"
        rec_path = out / "marsad_s2_e1_reconciliation.json"
        md_path = out / "marsad_s2_e1_report.md"
        for path in (sql_path, rec_path, md_path):
            if not path.exists() or path.stat().st_size == 0:
                fail(f"compiler did not generate {path.name}")
        if report.get("status") != "READY_FOR_SUPABASE_DRY_RUN":
            fail("fixture compilation did not reach READY status")
        if report["source"]["source_table_count"] != 25 or report["source"]["foreign_key_violations"] != 0:
            fail("fixture source validation drifted")
        if report["source_audit"]["settings"]["excluded_rows"] != 1:
            fail("secret-setting exclusion audit was not preserved")
        if report["folded_relations"]["event_media_meta"]["unmatched_links"] != 0:
            fail("event_media_meta fold is unmatched")
        if report["transform_metrics"]["storage_file_id_folded_to_storage_path"] < 1:
            fail("storage_file_id normalization was not exercised")
        if report["target_expected_counts"]["schools"] != 1 or report["target_expected_counts"]["profiles"] != 0 or report["target_expected_counts"]["school_memberships"] != 0:
            fail("bootstrap target boundary changed")
        if report["target_expected_counts"]["teacher_years"] < 2:
            fail("teacher-year current/history union was not exercised")

        sql = sql_path.read_text(encoding="utf-8")
        lower = sql.lower().rstrip()
        if not lower.endswith("rollback;") or "commit;" in lower:
            fail("generated dry-run SQL must end with ROLLBACK and contain no COMMIT")
        for fragment in (
            "PASS: S2-E1 SQLite migration dry run",
            "legacy_local",
            "google_drive",
            "S2-E1 reconciliation failed",
            "insert into public.teacher_years",
            "insert into public.event_media",
        ):
            if fragment.lower() not in lower:
                fail(f"generated dry-run SQL missing {fragment}")
        if "TOPSECRET" in sql:
            fail("secret setting value leaked into generated SQL")

        # Negative guard: an unsupported legacy storage provider must fail compilation, never be silently dropped.
        bad_db = temp_root / "bad.sqlite3"
        with sqlite3.connect(db) as source_conn, sqlite3.connect(bad_db) as dest_conn:
            source_conn.backup(dest_conn)
        with sqlite3.connect(bad_db) as conn:
            changed = conn.execute("UPDATE documents SET storage_provider='mystery-provider' WHERE id=1").rowcount
            conn.commit()
            if changed != 1:
                fail("negative fixture did not mutate the document provider")
        try:
            compile_database(bad_db, temp_root / "bad-out", "مدرسة مرصد الاختبار", "2026/2027")
        except CompileError:
            pass
        else:
            fail("compiler accepted unsupported storage provider")

    print("PASS: Marsad S2-E1 SQLite migration compiler and rollback-only dry-run tooling")
    print("INFO: source_tables=25 target_tables=26 schema_changes=0 rls_changes=0 live_commit=0")
    print("INFO: fixture_compilation=PASS negative_storage_guard=PASS rollback_guard=PASS")


if __name__ == "__main__":
    main()
