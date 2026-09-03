-- Marsad Al-Injazat — Phase S2-C2
-- Domain RLS baseline for the remaining 21 frozen PostgreSQL tables.
-- Runtime remains React -> FastAPI -> SQLite. No storage/public-upload cutover happens here.

begin;

-- Private teacher-record visibility: school managers may resolve teacher-linked private rows;
-- a teacher may resolve only rows linked to their own membership teacher_id. Viewer is excluded.
create or replace function private.can_access_teacher_record(p_school_id uuid, p_teacher_id bigint)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.school_memberships sm
        where sm.school_id = p_school_id
          and sm.user_id = (select auth.uid())
          and sm.status = 'active'
          and (
              sm.role in ('owner', 'admin', 'lead_teacher')
              or (sm.role = 'teacher' and sm.teacher_id = p_teacher_id)
          )
    );
$$;

revoke all on function private.can_access_teacher_record(uuid, bigint) from public, anon, authenticated;
grant execute on function private.can_access_teacher_record(uuid, bigint) to authenticated;

-- Deterministic RLS/grant baseline for all 21 domain tables.
alter table public.teachers enable row level security;
alter table public.teacher_profiles enable row level security;
alter table public.teacher_years enable row level security;
alter table public.teacher_cv_items enable row level security;
alter table public.upload_requests enable row level security;
alter table public.documents enable row level security;
alter table public.events enable row level security;
alter table public.event_media enable row level security;
alter table public.event_teacher_links enable row level security;
alter table public.activities enable row level security;
alter table public.meetings enable row level security;
alter table public.meeting_attendees enable row level security;
alter table public.meeting_decisions enable row level security;
alter table public.curriculum_plans enable row level security;
alter table public.curriculum_units enable row level security;
alter table public.supervision_visits enable row level security;
alter table public.supervision_actions enable row level security;
alter table public.achievement_assessments enable row level security;
alter table public.achievement_assessment_standards enable row level security;
alter table public.achievement_actions enable row level security;
alter table public.achievement_action_metrics enable row level security;

revoke all on table public.teachers from public, anon, authenticated;
revoke all on table public.teacher_profiles from public, anon, authenticated;
revoke all on table public.teacher_years from public, anon, authenticated;
revoke all on table public.teacher_cv_items from public, anon, authenticated;
revoke all on table public.upload_requests from public, anon, authenticated;
revoke all on table public.documents from public, anon, authenticated;
revoke all on table public.events from public, anon, authenticated;
revoke all on table public.event_media from public, anon, authenticated;
revoke all on table public.event_teacher_links from public, anon, authenticated;
revoke all on table public.activities from public, anon, authenticated;
revoke all on table public.meetings from public, anon, authenticated;
revoke all on table public.meeting_attendees from public, anon, authenticated;
revoke all on table public.meeting_decisions from public, anon, authenticated;
revoke all on table public.curriculum_plans from public, anon, authenticated;
revoke all on table public.curriculum_units from public, anon, authenticated;
revoke all on table public.supervision_visits from public, anon, authenticated;
revoke all on table public.supervision_actions from public, anon, authenticated;
revoke all on table public.achievement_assessments from public, anon, authenticated;
revoke all on table public.achievement_assessment_standards from public, anon, authenticated;
revoke all on table public.achievement_actions from public, anon, authenticated;
revoke all on table public.achievement_action_metrics from public, anon, authenticated;
revoke all on sequence public.teachers_id_seq from public, anon, authenticated;
revoke all on sequence public.teacher_cv_items_id_seq from public, anon, authenticated;
revoke all on sequence public.upload_requests_id_seq from public, anon, authenticated;
revoke all on sequence public.documents_id_seq from public, anon, authenticated;
revoke all on sequence public.events_id_seq from public, anon, authenticated;
revoke all on sequence public.event_media_id_seq from public, anon, authenticated;
revoke all on sequence public.activities_id_seq from public, anon, authenticated;
revoke all on sequence public.meetings_id_seq from public, anon, authenticated;
revoke all on sequence public.meeting_decisions_id_seq from public, anon, authenticated;
revoke all on sequence public.curriculum_plans_id_seq from public, anon, authenticated;
revoke all on sequence public.curriculum_units_id_seq from public, anon, authenticated;
revoke all on sequence public.supervision_visits_id_seq from public, anon, authenticated;
revoke all on sequence public.supervision_actions_id_seq from public, anon, authenticated;
revoke all on sequence public.achievement_assessments_id_seq from public, anon, authenticated;
revoke all on sequence public.achievement_actions_id_seq from public, anon, authenticated;

-- All signed-in access still passes RLS. Table SELECT is granted for policy evaluation only.
grant select on table public.teachers to authenticated;
grant select on table public.teacher_profiles to authenticated;
grant select on table public.teacher_years to authenticated;
grant select on table public.teacher_cv_items to authenticated;
grant select on table public.upload_requests to authenticated;
grant select on table public.documents to authenticated;
grant select on table public.events to authenticated;
grant select on table public.event_media to authenticated;
grant select on table public.event_teacher_links to authenticated;
grant select on table public.activities to authenticated;
grant select on table public.meetings to authenticated;
grant select on table public.meeting_attendees to authenticated;
grant select on table public.meeting_decisions to authenticated;
grant select on table public.curriculum_plans to authenticated;
grant select on table public.curriculum_units to authenticated;
grant select on table public.supervision_visits to authenticated;
grant select on table public.supervision_actions to authenticated;
grant select on table public.achievement_assessments to authenticated;
grant select on table public.achievement_assessment_standards to authenticated;
grant select on table public.achievement_actions to authenticated;
grant select on table public.achievement_action_metrics to authenticated;

-- Browser mutation grants mirror the verified legacy mutation surface and remain owner/admin only via RLS.
-- INSERT/UPDATE use column grants so tenant keys, primary keys, and database timestamps cannot be rewritten.
grant insert (school_id, name, specialization, qualification, email, phone, is_active) on table public.teachers to authenticated;
grant update (name, specialization, qualification, email, phone, is_active) on table public.teachers to authenticated;
grant insert (teacher_id, school_id, employee_number, school_join_year, professional_summary) on table public.teacher_profiles to authenticated;
grant update (employee_number, school_join_year, professional_summary) on table public.teacher_profiles to authenticated;
grant insert (school_id, teacher_id, item_type, title, organization, start_year, end_year, description) on table public.teacher_cv_items to authenticated;
grant delete on table public.teacher_cv_items to authenticated;
grant insert (school_id, academic_year_id, title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone) on table public.events to authenticated;
grant update (academic_year_id, title, event_type, event_date, location, audience, participant_count, goals, summary, outcomes, recommendations, cover_tone) on table public.events to authenticated;
grant insert (school_id, event_id, teacher_id, role) on table public.event_teacher_links to authenticated;
grant delete on table public.event_teacher_links to authenticated;
grant insert (school_id, academic_year_id, title, meeting_type, meeting_date, meeting_time, location, agenda, discussion_summary, notes, status) on table public.meetings to authenticated;
grant update (academic_year_id, title, meeting_type, meeting_date, meeting_time, location, agenda, discussion_summary, notes, status) on table public.meetings to authenticated;
grant insert (school_id, meeting_id, teacher_id, attendance_status) on table public.meeting_attendees to authenticated;
grant delete on table public.meeting_attendees to authenticated;
grant insert (school_id, meeting_id, title, responsible_teacher_id, responsible_name, due_date, status, notes, completed_at) on table public.meeting_decisions to authenticated;
grant update (meeting_id, title, responsible_teacher_id, responsible_name, due_date, status, notes, completed_at) on table public.meeting_decisions to authenticated;
grant delete on table public.meeting_decisions to authenticated;
grant insert (school_id, academic_year_id, title, subject, grade, term, owner_teacher_id, start_date, end_date, notes, status) on table public.curriculum_plans to authenticated;
grant update (academic_year_id, title, subject, grade, term, owner_teacher_id, start_date, end_date, notes, status) on table public.curriculum_plans to authenticated;
grant insert (school_id, plan_id, title, sequence, planned_start, planned_end, progress_percent, status, delay_reason, notes, responsible_teacher_id) on table public.curriculum_units to authenticated;
grant update (plan_id, title, sequence, planned_start, planned_end, progress_percent, status, delay_reason, notes, responsible_teacher_id) on table public.curriculum_units to authenticated;
grant delete on table public.curriculum_units to authenticated;
grant insert (school_id, academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at) on table public.supervision_visits to authenticated;
grant update (academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at) on table public.supervision_visits to authenticated;
grant insert (school_id, visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at) on table public.supervision_actions to authenticated;
grant update (visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at) on table public.supervision_actions to authenticated;
grant delete on table public.supervision_actions to authenticated;
grant insert (school_id, academic_year_id, title, assessment_type, subject, grade, assessment_date, term, teacher_id, max_score, student_count, average_score, highest_score, lowest_score, mastery_threshold_pct, mastered_count, near_mastery_count, intervention_count, notes, status) on table public.achievement_assessments to authenticated;
grant update (academic_year_id, title, assessment_type, subject, grade, assessment_date, term, teacher_id, max_score, student_count, average_score, highest_score, lowest_score, mastery_threshold_pct, mastered_count, near_mastery_count, intervention_count, notes, status) on table public.achievement_assessments to authenticated;
grant insert (assessment_id, school_id, mastery_reference_source, mastery_reference_year, mastery_reference_note) on table public.achievement_assessment_standards to authenticated;
grant update (mastery_reference_source, mastery_reference_year, mastery_reference_note) on table public.achievement_assessment_standards to authenticated;
grant insert (school_id, assessment_id, action_type, title, target_group, responsible_teacher_id, start_date, due_date, status, baseline_indicator, target_indicator, outcome_indicator, notes, completed_at) on table public.achievement_actions to authenticated;
grant update (assessment_id, action_type, title, target_group, responsible_teacher_id, start_date, due_date, status, baseline_indicator, target_indicator, outcome_indicator, notes, completed_at) on table public.achievement_actions to authenticated;
grant delete on table public.achievement_actions to authenticated;
grant insert (action_id, school_id, metric_name, unit, direction, baseline_value, target_value, outcome_value, measured_at, reference_source, reference_year, reference_note, notes) on table public.achievement_action_metrics to authenticated;
grant update (metric_name, unit, direction, baseline_value, target_value, outcome_value, measured_at, reference_source, reference_year, reference_note, notes) on table public.achievement_action_metrics to authenticated;
grant delete on table public.achievement_action_metrics to authenticated;

grant usage on sequence public.teachers_id_seq to authenticated;
grant usage on sequence public.teacher_cv_items_id_seq to authenticated;
grant usage on sequence public.events_id_seq to authenticated;
grant usage on sequence public.meetings_id_seq to authenticated;
grant usage on sequence public.meeting_decisions_id_seq to authenticated;
grant usage on sequence public.curriculum_plans_id_seq to authenticated;
grant usage on sequence public.curriculum_units_id_seq to authenticated;
grant usage on sequence public.supervision_visits_id_seq to authenticated;
grant usage on sequence public.supervision_actions_id_seq to authenticated;
grant usage on sequence public.achievement_assessments_id_seq to authenticated;
grant usage on sequence public.achievement_actions_id_seq to authenticated;

-- Remove/recreate only S2-C2-owned policies for repeatable isolated tests.
drop policy if exists teachers_select_scope on public.teachers;
drop policy if exists teachers_insert_managers on public.teachers;
drop policy if exists teachers_update_managers on public.teachers;
drop policy if exists teacher_profiles_select_scope on public.teacher_profiles;
drop policy if exists teacher_profiles_insert_managers on public.teacher_profiles;
drop policy if exists teacher_profiles_update_managers on public.teacher_profiles;
drop policy if exists teacher_years_select_scope on public.teacher_years;
drop policy if exists teacher_cv_items_select_scope on public.teacher_cv_items;
drop policy if exists teacher_cv_items_delete_managers on public.teacher_cv_items;
drop policy if exists teacher_cv_items_insert_managers on public.teacher_cv_items;
drop policy if exists upload_requests_select_scope on public.upload_requests;
drop policy if exists documents_select_scope on public.documents;
drop policy if exists events_select_scope on public.events;
drop policy if exists events_insert_managers on public.events;
drop policy if exists events_update_managers on public.events;
drop policy if exists event_media_select_scope on public.event_media;
drop policy if exists event_teacher_links_select_scope on public.event_teacher_links;
drop policy if exists event_teacher_links_delete_managers on public.event_teacher_links;
drop policy if exists event_teacher_links_insert_managers on public.event_teacher_links;
drop policy if exists activities_select_scope on public.activities;
drop policy if exists meetings_select_scope on public.meetings;
drop policy if exists meetings_insert_managers on public.meetings;
drop policy if exists meetings_update_managers on public.meetings;
drop policy if exists meeting_attendees_select_scope on public.meeting_attendees;
drop policy if exists meeting_attendees_delete_managers on public.meeting_attendees;
drop policy if exists meeting_attendees_insert_managers on public.meeting_attendees;
drop policy if exists meeting_decisions_select_scope on public.meeting_decisions;
drop policy if exists meeting_decisions_delete_managers on public.meeting_decisions;
drop policy if exists meeting_decisions_insert_managers on public.meeting_decisions;
drop policy if exists meeting_decisions_update_managers on public.meeting_decisions;
drop policy if exists curriculum_plans_select_scope on public.curriculum_plans;
drop policy if exists curriculum_plans_insert_managers on public.curriculum_plans;
drop policy if exists curriculum_plans_update_managers on public.curriculum_plans;
drop policy if exists curriculum_units_select_scope on public.curriculum_units;
drop policy if exists curriculum_units_delete_managers on public.curriculum_units;
drop policy if exists curriculum_units_insert_managers on public.curriculum_units;
drop policy if exists curriculum_units_update_managers on public.curriculum_units;
drop policy if exists supervision_visits_select_scope on public.supervision_visits;
drop policy if exists supervision_visits_insert_managers on public.supervision_visits;
drop policy if exists supervision_visits_update_managers on public.supervision_visits;
drop policy if exists supervision_actions_select_scope on public.supervision_actions;
drop policy if exists supervision_actions_delete_managers on public.supervision_actions;
drop policy if exists supervision_actions_insert_managers on public.supervision_actions;
drop policy if exists supervision_actions_update_managers on public.supervision_actions;
drop policy if exists achievement_assessments_select_scope on public.achievement_assessments;
drop policy if exists achievement_assessments_insert_managers on public.achievement_assessments;
drop policy if exists achievement_assessments_update_managers on public.achievement_assessments;
drop policy if exists achievement_assessment_standards_select_scope on public.achievement_assessment_standards;
drop policy if exists achievement_assessment_standards_insert_managers on public.achievement_assessment_standards;
drop policy if exists achievement_assessment_standards_update_managers on public.achievement_assessment_standards;
drop policy if exists achievement_actions_select_scope on public.achievement_actions;
drop policy if exists achievement_actions_delete_managers on public.achievement_actions;
drop policy if exists achievement_actions_insert_managers on public.achievement_actions;
drop policy if exists achievement_actions_update_managers on public.achievement_actions;
drop policy if exists achievement_action_metrics_select_scope on public.achievement_action_metrics;
drop policy if exists achievement_action_metrics_delete_managers on public.achievement_action_metrics;
drop policy if exists achievement_action_metrics_insert_managers on public.achievement_action_metrics;
drop policy if exists achievement_action_metrics_update_managers on public.achievement_action_metrics;

create policy teachers_select_scope
    on public.teachers
    for select
    to authenticated
    using (private.can_access_teacher_record(school_id, id));

create policy teacher_profiles_select_scope
    on public.teacher_profiles
    for select
    to authenticated
    using (private.can_access_teacher_record(school_id, teacher_id));

create policy teacher_years_select_scope
    on public.teacher_years
    for select
    to authenticated
    using (private.can_access_teacher_record(school_id, teacher_id));

create policy teacher_cv_items_select_scope
    on public.teacher_cv_items
    for select
    to authenticated
    using (private.can_access_teacher_record(school_id, teacher_id));

create policy upload_requests_select_scope
    on public.upload_requests
    for select
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy documents_select_scope
    on public.documents
    for select
    to authenticated
    using (private.can_access_teacher_record(school_id, teacher_id));

create policy events_select_scope
    on public.events
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy event_media_select_scope
    on public.event_media
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy event_teacher_links_select_scope
    on public.event_teacher_links
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy activities_select_scope
    on public.activities
    for select
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meetings_select_scope
    on public.meetings
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy meeting_attendees_select_scope
    on public.meeting_attendees
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy meeting_decisions_select_scope
    on public.meeting_decisions
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy curriculum_plans_select_scope
    on public.curriculum_plans
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy curriculum_units_select_scope
    on public.curriculum_units
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy supervision_visits_select_scope
    on public.supervision_visits
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy supervision_actions_select_scope
    on public.supervision_actions
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy achievement_assessments_select_scope
    on public.achievement_assessments
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy achievement_assessment_standards_select_scope
    on public.achievement_assessment_standards
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy achievement_actions_select_scope
    on public.achievement_actions
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy achievement_action_metrics_select_scope
    on public.achievement_action_metrics
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy teachers_insert_managers
    on public.teachers
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teachers_update_managers
    on public.teachers
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teacher_profiles_insert_managers
    on public.teacher_profiles
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teacher_profiles_update_managers
    on public.teacher_profiles
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teacher_cv_items_insert_managers
    on public.teacher_cv_items
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teacher_cv_items_delete_managers
    on public.teacher_cv_items
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy events_insert_managers
    on public.events
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy events_update_managers
    on public.events
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy event_teacher_links_insert_managers
    on public.event_teacher_links
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy event_teacher_links_delete_managers
    on public.event_teacher_links
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meetings_insert_managers
    on public.meetings
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meetings_update_managers
    on public.meetings
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meeting_attendees_insert_managers
    on public.meeting_attendees
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meeting_attendees_delete_managers
    on public.meeting_attendees
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meeting_decisions_insert_managers
    on public.meeting_decisions
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meeting_decisions_update_managers
    on public.meeting_decisions
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy meeting_decisions_delete_managers
    on public.meeting_decisions
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy curriculum_plans_insert_managers
    on public.curriculum_plans
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy curriculum_plans_update_managers
    on public.curriculum_plans
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy curriculum_units_insert_managers
    on public.curriculum_units
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy curriculum_units_update_managers
    on public.curriculum_units
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy curriculum_units_delete_managers
    on public.curriculum_units
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy supervision_visits_insert_managers
    on public.supervision_visits
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy supervision_visits_update_managers
    on public.supervision_visits
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy supervision_actions_insert_managers
    on public.supervision_actions
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy supervision_actions_update_managers
    on public.supervision_actions
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy supervision_actions_delete_managers
    on public.supervision_actions
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_assessments_insert_managers
    on public.achievement_assessments
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_assessments_update_managers
    on public.achievement_assessments
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_assessment_standards_insert_managers
    on public.achievement_assessment_standards
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_assessment_standards_update_managers
    on public.achievement_assessment_standards
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_actions_insert_managers
    on public.achievement_actions
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_actions_update_managers
    on public.achievement_actions
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_actions_delete_managers
    on public.achievement_actions
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_action_metrics_insert_managers
    on public.achievement_action_metrics
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_action_metrics_update_managers
    on public.achievement_action_metrics
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy achievement_action_metrics_delete_managers
    on public.achievement_action_metrics
    for delete
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]));

-- Deliberate locks retained in S2-C2:
-- teacher_years is derived/annual state; upload_requests needs trusted token issuance;
-- documents/event_media are storage-coupled; activities is trusted audit data.
-- No anon/public upload policy and no storage.objects policy is created here.
commit;
