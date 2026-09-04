-- Marsad Al-Injazat S2-E1 SQLite -> Supabase controlled dry run
-- compiler_version=1.0.0
-- source_sha256=f856c70a821403b2cfdf8cb142825b8a57ca318be5666281a5087634eb77377c
-- dry_run_school_id=897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f
-- current_academic_year=2026/2027
-- IMPORTANT: this script ends with ROLLBACK and must never be edited to COMMIT.
begin;

-- schools: 1 rows
insert into public.schools (id, name, is_active) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'مدرسة مرصد الاختبار التمثيلي', TRUE);

-- academic_years: 2 rows
insert into public.academic_years (id, school_id, label, start_year, end_year, is_current) values (7000000000000100001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', '2025/2026', 2025, 2026, FALSE);
insert into public.academic_years (id, school_id, label, start_year, end_year, is_current) values (7000000000000100002, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', '2026/2027', 2026, 2027, TRUE);

-- school_settings: 1 rows
insert into public.school_settings (school_id, key, value, updated_at, updated_by) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'school_theme', '"indigo"'::jsonb, '2026-09-04T08:00:00+00:00', NULL);

-- teachers: 1 rows
insert into public.teachers (id, school_id, name, specialization, qualification, email, phone, is_active, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'معلم فيزياء', 'فيزياء', 'بكالوريوس', 'teacher@example.com', '90000000', TRUE, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- teacher_profiles: 1 rows
insert into public.teacher_profiles (teacher_id, school_id, employee_number, school_join_year, professional_summary, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'EMP-1', 2020, 'ملف تجريبي', '2026-09-04T08:00:00+00:00');

-- teacher_years: 2 rows
insert into public.teacher_years (school_id, academic_year_id, teacher_id, subject, experience_years, workload, grades, responsibilities, is_active, created_at, updated_at) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100001, 7000000000000000001, NULL, NULL, NULL, NULL, NULL, TRUE, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');
insert into public.teacher_years (school_id, academic_year_id, teacher_id, subject, experience_years, workload, grades, responsibilities, is_active, created_at, updated_at) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 7000000000000000001, 'فيزياء', 12, 20, '10', 'مختبر', TRUE, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- teacher_cv_items: 1 rows
insert into public.teacher_cv_items (id, school_id, teacher_id, item_type, title, organization, start_year, end_year, description, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'course', 'دورة', 'وزارة التربية', 2025, 2025, 'وصف', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- upload_requests: 1 rows
insert into public.upload_requests (id, school_id, academic_year_id, teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, token_hash, status, expires_at, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 7000000000000000001, 'evidence', 'فيزياء', '10', 'طلب شاهد', '2026-09-30', 'ملاحظة', 'PDF', 'fixture-token-hash', 'waiting_upload', '2026-10-01T00:00:00+00:00', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- documents: 1 rows
insert into public.documents (id, school_id, academic_year_id, request_id, teacher_id, title, category, subject, grade, original_name, mime_type, size_bytes, storage_provider, storage_bucket, storage_path, external_url, status, uploaded_at, approved_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 7000000000000000001, 7000000000000000001, 'وثيقة', 'evidence', 'فيزياء', '10', 'doc.pdf', 'application/pdf', 120, 'legacy_local', NULL, 'uploads/doc.pdf', NULL, 'inbox', '2026-09-04T08:00:00+00:00', NULL);

-- events: 1 rows
insert into public.events (id, school_id, academic_year_id, title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 'فعالية', 'activity', '2026-09-02', 'المدرسة', 'الطلبة', 20, 'هدف', 'ملخص', 'نتيجة', 'توصية', 'teal', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- event_media: 1 rows
insert into public.event_media (id, school_id, event_id, original_name, mime_type, size_bytes, storage_provider, storage_bucket, storage_path, external_url, caption, position, is_cover, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'event.jpg', 'image/jpeg', 200, 'google_drive', NULL, 'drive-file-1', 'https://example.invalid/view', 'غلاف', 0, TRUE, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- event_teacher_links: 1 rows
insert into public.event_teacher_links (school_id, event_id, teacher_id, role, created_at) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 7000000000000000001, 'مشارك', '2026-09-04T08:00:00+00:00');

-- activities: 1 rows
insert into public.activities (id, school_id, academic_year_id, actor_user_id, activity_type, title, detail, entity_type, entity_id, created_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, NULL, 'created', 'إنشاء فعالية', 'تفصيل', 'event', 7000000000000000001, '2026-09-04T08:00:00+00:00');

-- meetings: 1 rows
insert into public.meetings (id, school_id, academic_year_id, title, meeting_type, meeting_date, meeting_time, location, agenda, discussion_summary, notes, status, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 'اجتماع', 'اجتماع قسم', '2026-09-03', '10:00', 'قاعة', 'أجندة', 'نقاش', 'ملاحظات', 'held', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- meeting_attendees: 1 rows
insert into public.meeting_attendees (school_id, meeting_id, teacher_id, attendance_status, created_at) values ('897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 7000000000000000001, 'present', '2026-09-04T08:00:00+00:00');

-- meeting_decisions: 1 rows
insert into public.meeting_decisions (id, school_id, meeting_id, title, responsible_teacher_id, responsible_name, due_date, status, notes, completed_at, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'قرار', 7000000000000000001, 'معلم فيزياء', '2026-09-20', 'in_progress', 'متابعة', NULL, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- curriculum_plans: 1 rows
insert into public.curriculum_plans (id, school_id, academic_year_id, title, subject, grade, term, owner_teacher_id, start_date, end_date, notes, status, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 'خطة', 'فيزياء', '10', '1', 7000000000000000001, '2026-09-01', '2027-01-01', 'ملاحظات', 'active', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- curriculum_units: 1 rows
insert into public.curriculum_units (id, school_id, plan_id, title, sequence, planned_start, planned_end, progress_percent, status, delay_reason, notes, responsible_teacher_id, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'وحدة', 1, '2026-09-01', '2026-10-01', 50, 'in_progress', NULL, 'ملاحظة', 7000000000000000001, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- supervision_visits: 1 rows
insert into public.supervision_visits (id, school_id, academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 7000000000000000001, 'زيارة صفية', '2026-09-04', 'ح1', '10', 'درس', 'هدف', 'قوة', 'تطوير', 'توصية', NULL, NULL, 'completed', NULL, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- supervision_actions: 1 rows
insert into public.supervision_actions (id, school_id, visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'إجراء إشرافي', 7000000000000000001, '2026-09-20', 'new', 'ملاحظة', NULL, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- achievement_assessments: 1 rows
insert into public.achievement_assessments (id, school_id, academic_year_id, title, assessment_type, subject, grade, assessment_date, term, teacher_id, max_score, student_count, average_score, highest_score, lowest_score, mastery_threshold_pct, mastered_count, near_mastery_count, intervention_count, notes, status, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000100002, 'اختبار', 'اختبار', 'فيزياء', '10', '2026-09-05', '1', 7000000000000000001, 100.0, 30, 72.0, 98.0, 20.0, 60.0, 18, 7, 5, 'ملاحظات', 'recorded', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- achievement_assessment_standards: 1 rows
insert into public.achievement_assessment_standards (assessment_id, school_id, mastery_reference_source, mastery_reference_year, mastery_reference_note, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'مرجع', '2026', 'ملاحظة', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- achievement_actions: 1 rows
insert into public.achievement_actions (id, school_id, assessment_id, action_type, title, target_group, responsible_teacher_id, start_date, due_date, status, baseline_indicator, target_indicator, outcome_indicator, notes, completed_at, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 7000000000000000001, 'remedial', 'خطة علاج', 'فئة', 7000000000000000001, '2026-09-06', '2026-10-01', 'in_progress', '60', '75', NULL, 'ملاحظة', NULL, '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- achievement_action_metrics: 1 rows
insert into public.achievement_action_metrics (action_id, school_id, metric_name, unit, direction, baseline_value, target_value, outcome_value, measured_at, reference_source, reference_year, reference_note, notes, created_at, updated_at) values (7000000000000000001, '897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f', 'نسبة', '%', 'higher_better', 60.0, 75.0, NULL, NULL, 'مرجع', '2026', 'ملاحظة', 'ملاحظات', '2026-09-04T08:00:00+00:00', '2026-09-04T08:00:00+00:00');

-- Reconciliation: every dry-run target row count must match the compiler manifest.
do $$
declare v_count bigint;
begin
  select count(*) into v_count from public.schools where id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: schools'; end if;
  select count(*) into v_count from public.academic_years where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 2 then raise exception 'S2-E1 reconciliation failed: academic_years expected 2 got %', v_count; end if;
  select count(*) into v_count from public.school_settings where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: school_settings expected 1 got %', v_count; end if;
  select count(*) into v_count from public.teachers where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: teachers expected 1 got %', v_count; end if;
  select count(*) into v_count from public.teacher_profiles where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: teacher_profiles expected 1 got %', v_count; end if;
  select count(*) into v_count from public.teacher_years where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 2 then raise exception 'S2-E1 reconciliation failed: teacher_years expected 2 got %', v_count; end if;
  select count(*) into v_count from public.teacher_cv_items where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: teacher_cv_items expected 1 got %', v_count; end if;
  select count(*) into v_count from public.upload_requests where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: upload_requests expected 1 got %', v_count; end if;
  select count(*) into v_count from public.documents where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: documents expected 1 got %', v_count; end if;
  select count(*) into v_count from public.events where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: events expected 1 got %', v_count; end if;
  select count(*) into v_count from public.event_media where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: event_media expected 1 got %', v_count; end if;
  select count(*) into v_count from public.event_teacher_links where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: event_teacher_links expected 1 got %', v_count; end if;
  select count(*) into v_count from public.activities where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: activities expected 1 got %', v_count; end if;
  select count(*) into v_count from public.meetings where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: meetings expected 1 got %', v_count; end if;
  select count(*) into v_count from public.meeting_attendees where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: meeting_attendees expected 1 got %', v_count; end if;
  select count(*) into v_count from public.meeting_decisions where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: meeting_decisions expected 1 got %', v_count; end if;
  select count(*) into v_count from public.curriculum_plans where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: curriculum_plans expected 1 got %', v_count; end if;
  select count(*) into v_count from public.curriculum_units where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: curriculum_units expected 1 got %', v_count; end if;
  select count(*) into v_count from public.supervision_visits where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: supervision_visits expected 1 got %', v_count; end if;
  select count(*) into v_count from public.supervision_actions where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: supervision_actions expected 1 got %', v_count; end if;
  select count(*) into v_count from public.achievement_assessments where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: achievement_assessments expected 1 got %', v_count; end if;
  select count(*) into v_count from public.achievement_assessment_standards where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: achievement_assessment_standards expected 1 got %', v_count; end if;
  select count(*) into v_count from public.achievement_actions where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: achievement_actions expected 1 got %', v_count; end if;
  select count(*) into v_count from public.achievement_action_metrics where school_id='897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f'::uuid; if v_count <> 1 then raise exception 'S2-E1 reconciliation failed: achievement_action_metrics expected 1 got %', v_count; end if;
end $$;
select 'PASS: S2-E1 SQLite migration dry run' as result;
rollback;
