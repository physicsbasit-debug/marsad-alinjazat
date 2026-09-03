-- Marsad Al-Injazat — Phase S2-B5
-- Final schema hardening before Auth/RLS policy work in S2-C.
-- No domain tables are created here. Runtime remains FastAPI/SQLite.

begin;

-- Keep updated_at reliable at the database boundary instead of depending on
-- every future client/server write path to remember it.
create or replace function public.set_row_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
    new.updated_at := statement_timestamp();
    return new;
end;
$$;

-- The helper is trigger-only. Browser roles must not be able to invoke it as RPC.
revoke all on function public.set_row_updated_at() from public, anon, authenticated;

create trigger trg_schools_updated_at
before update on public.schools
for each row execute function public.set_row_updated_at();

create trigger trg_profiles_updated_at
before update on public.profiles
for each row execute function public.set_row_updated_at();

create trigger trg_school_memberships_updated_at
before update on public.school_memberships
for each row execute function public.set_row_updated_at();

create trigger trg_academic_years_updated_at
before update on public.academic_years
for each row execute function public.set_row_updated_at();

create trigger trg_school_settings_updated_at
before update on public.school_settings
for each row execute function public.set_row_updated_at();

create trigger trg_teachers_updated_at
before update on public.teachers
for each row execute function public.set_row_updated_at();

create trigger trg_teacher_profiles_updated_at
before update on public.teacher_profiles
for each row execute function public.set_row_updated_at();

create trigger trg_teacher_years_updated_at
before update on public.teacher_years
for each row execute function public.set_row_updated_at();

create trigger trg_teacher_cv_items_updated_at
before update on public.teacher_cv_items
for each row execute function public.set_row_updated_at();

create trigger trg_upload_requests_updated_at
before update on public.upload_requests
for each row execute function public.set_row_updated_at();

create trigger trg_events_updated_at
before update on public.events
for each row execute function public.set_row_updated_at();

create trigger trg_event_media_updated_at
before update on public.event_media
for each row execute function public.set_row_updated_at();

create trigger trg_meetings_updated_at
before update on public.meetings
for each row execute function public.set_row_updated_at();

create trigger trg_meeting_decisions_updated_at
before update on public.meeting_decisions
for each row execute function public.set_row_updated_at();

create trigger trg_curriculum_plans_updated_at
before update on public.curriculum_plans
for each row execute function public.set_row_updated_at();

create trigger trg_curriculum_units_updated_at
before update on public.curriculum_units
for each row execute function public.set_row_updated_at();

create trigger trg_supervision_visits_updated_at
before update on public.supervision_visits
for each row execute function public.set_row_updated_at();

create trigger trg_supervision_actions_updated_at
before update on public.supervision_actions
for each row execute function public.set_row_updated_at();

create trigger trg_achievement_assessments_updated_at
before update on public.achievement_assessments
for each row execute function public.set_row_updated_at();

create trigger trg_achievement_assessment_standards_updated_at
before update on public.achievement_assessment_standards
for each row execute function public.set_row_updated_at();

create trigger trg_achievement_actions_updated_at
before update on public.achievement_actions
for each row execute function public.set_row_updated_at();

create trigger trg_achievement_action_metrics_updated_at
before update on public.achievement_action_metrics
for each row execute function public.set_row_updated_at();

-- Final index pass for management/year browsing and teacher-CV filtering.
-- These complement, rather than replace, the domain indexes from S2-B1..S2-B4.
create index idx_school_memberships_school_status_role
    on public.school_memberships (school_id, status, role, user_id);

create index idx_academic_years_school_start
    on public.academic_years (school_id, start_year desc, id desc);

create index idx_teacher_cv_items_teacher_type
    on public.teacher_cv_items (school_id, teacher_id, item_type, id);

commit;
