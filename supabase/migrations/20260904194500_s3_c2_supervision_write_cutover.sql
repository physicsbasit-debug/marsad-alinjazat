-- Marsad Al-Injazat — Phase S3-C2
-- Supervision vertical slice: atomic visit/action writes + activities timeline.
-- No table/schema shape change. Existing S2-C2 RLS remains authoritative.

begin;

-- Activities were read-only in the browser baseline. S3-C2 permits managers to
-- append supervision timeline rows, still behind RLS and column grants.
grant insert (
    school_id, academic_year_id, actor_user_id, activity_type,
    title, detail, entity_type, entity_id
) on table public.activities to authenticated;
grant usage on sequence public.activities_id_seq to authenticated;

drop policy if exists activities_insert_managers on public.activities;
create policy activities_insert_managers
    on public.activities
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create or replace function public.marsad_create_supervision_visit_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_teacher_id bigint,
    p_visit_type text,
    p_visit_date date,
    p_period_label text,
    p_grade text,
    p_lesson_title text,
    p_objectives text,
    p_strengths text,
    p_development_areas text,
    p_recommendations text,
    p_followup_date date,
    p_followup_notes text,
    p_status text
)
returns bigint
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_visit_id bigint;
    v_teacher_name text;
    v_start_year smallint;
    v_end_year smallint;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C2 manager role required' using errcode = '42501';
    end if;

    if p_visit_date is null then
        raise exception 'visit date is required' using errcode = '22023';
    end if;
    if p_status not in ('planned', 'completed', 'needs_followup', 'closed') then
        raise exception 'invalid supervision visit status' using errcode = '22023';
    end if;
    if char_length(btrim(coalesce(p_visit_type, ''))) < 2 or char_length(p_visit_type) > 100 then
        raise exception 'invalid supervision visit type' using errcode = '22023';
    end if;
    if char_length(coalesce(p_period_label, '')) > 80
       or char_length(coalesce(p_grade, '')) > 80
       or char_length(coalesce(p_lesson_title, '')) > 240
       or char_length(coalesce(p_objectives, '')) > 4000
       or char_length(coalesce(p_strengths, '')) > 5000
       or char_length(coalesce(p_development_areas, '')) > 5000
       or char_length(coalesce(p_recommendations, '')) > 5000
       or char_length(coalesce(p_followup_notes, '')) > 4000 then
        raise exception 'supervision visit text exceeds accepted limits' using errcode = '22023';
    end if;
    if p_followup_date is not null and p_followup_date < p_visit_date then
        raise exception 'followup date cannot precede visit date' using errcode = '22023';
    end if;

    select ay.start_year, ay.end_year
      into v_start_year, v_end_year
      from public.academic_years ay
     where ay.school_id = p_school_id
       and ay.id = p_academic_year_id;
    if not found then
        raise exception 'academic year is outside the current school scope' using errcode = '23503';
    end if;
    if extract(year from p_visit_date)::integer not in (v_start_year, v_end_year)
       or (p_followup_date is not null and extract(year from p_followup_date)::integer not in (v_start_year, v_end_year)) then
        raise exception 'supervision dates do not match the academic year' using errcode = '22023';
    end if;

    select t.name
      into v_teacher_name
      from public.teachers t
      join public.teacher_years ty
        on ty.school_id = t.school_id
       and ty.teacher_id = t.id
       and ty.academic_year_id = p_academic_year_id
       and ty.is_active
     where t.school_id = p_school_id
       and t.id = p_teacher_id
       and t.is_active;
    if not found then
        raise exception 'teacher is not active in the selected academic year' using errcode = '23503';
    end if;

    insert into public.supervision_visits (
        school_id, academic_year_id, teacher_id, visit_type, visit_date,
        period_label, grade, lesson_title, objectives, strengths,
        development_areas, recommendations, followup_date, followup_notes,
        status, closed_at
    ) values (
        p_school_id, p_academic_year_id, p_teacher_id, btrim(p_visit_type), p_visit_date,
        btrim(coalesce(p_period_label, '')), btrim(coalesce(p_grade, '')), btrim(coalesce(p_lesson_title, '')),
        btrim(coalesce(p_objectives, '')), btrim(coalesce(p_strengths, '')),
        btrim(coalesce(p_development_areas, '')), btrim(coalesce(p_recommendations, '')),
        p_followup_date, btrim(coalesce(p_followup_notes, '')), p_status,
        case when p_status = 'closed' then now() else null end
    ) returning id into v_visit_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, p_academic_year_id, (select auth.uid()), 'supervision',
        'إنشاء زيارة: ' || v_teacher_name,
        btrim(p_visit_type) || ' • ' || p_visit_date::text,
        'supervision_visit', v_visit_id
    );

    return v_visit_id;
end;
$$;

create or replace function public.marsad_update_supervision_visit_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_visit_id bigint,
    p_teacher_id bigint,
    p_visit_type text,
    p_visit_date date,
    p_period_label text,
    p_grade text,
    p_lesson_title text,
    p_objectives text,
    p_strengths text,
    p_development_areas text,
    p_recommendations text,
    p_followup_date date,
    p_followup_notes text,
    p_status text
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_teacher_name text;
    v_closed_at timestamptz;
    v_start_year smallint;
    v_end_year smallint;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C2 manager role required' using errcode = '42501';
    end if;
    if p_visit_date is null or p_status not in ('planned', 'completed', 'needs_followup', 'closed') then
        raise exception 'invalid supervision visit payload' using errcode = '22023';
    end if;
    if char_length(btrim(coalesce(p_visit_type, ''))) < 2 or char_length(p_visit_type) > 100 then
        raise exception 'invalid supervision visit type' using errcode = '22023';
    end if;
    if char_length(coalesce(p_period_label, '')) > 80
       or char_length(coalesce(p_grade, '')) > 80
       or char_length(coalesce(p_lesson_title, '')) > 240
       or char_length(coalesce(p_objectives, '')) > 4000
       or char_length(coalesce(p_strengths, '')) > 5000
       or char_length(coalesce(p_development_areas, '')) > 5000
       or char_length(coalesce(p_recommendations, '')) > 5000
       or char_length(coalesce(p_followup_notes, '')) > 4000 then
        raise exception 'supervision visit text exceeds accepted limits' using errcode = '22023';
    end if;
    if p_followup_date is not null and p_followup_date < p_visit_date then
        raise exception 'followup date cannot precede visit date' using errcode = '22023';
    end if;

    select ay.start_year, ay.end_year
      into v_start_year, v_end_year
      from public.academic_years ay
     where ay.school_id = p_school_id and ay.id = p_academic_year_id;
    if not found then
        raise exception 'academic year is outside the current school scope' using errcode = '23503';
    end if;
    if extract(year from p_visit_date)::integer not in (v_start_year, v_end_year)
       or (p_followup_date is not null and extract(year from p_followup_date)::integer not in (v_start_year, v_end_year)) then
        raise exception 'supervision dates do not match the academic year' using errcode = '22023';
    end if;

    select sv.closed_at
      into v_closed_at
      from public.supervision_visits sv
     where sv.school_id = p_school_id
       and sv.academic_year_id = p_academic_year_id
       and sv.id = p_visit_id
     for update;
    if not found then
        raise exception 'supervision visit not found in tenant/year scope' using errcode = 'P0002';
    end if;

    select t.name
      into v_teacher_name
      from public.teachers t
      join public.teacher_years ty
        on ty.school_id = t.school_id
       and ty.teacher_id = t.id
       and ty.academic_year_id = p_academic_year_id
       and ty.is_active
     where t.school_id = p_school_id
       and t.id = p_teacher_id
       and t.is_active;
    if not found then
        raise exception 'teacher is not active in the selected academic year' using errcode = '23503';
    end if;

    if p_status = 'closed' and v_closed_at is null then
        v_closed_at := now();
    elsif p_status <> 'closed' then
        v_closed_at := null;
    end if;

    update public.supervision_visits
       set teacher_id = p_teacher_id,
           visit_type = btrim(p_visit_type),
           visit_date = p_visit_date,
           period_label = btrim(coalesce(p_period_label, '')),
           grade = btrim(coalesce(p_grade, '')),
           lesson_title = btrim(coalesce(p_lesson_title, '')),
           objectives = btrim(coalesce(p_objectives, '')),
           strengths = btrim(coalesce(p_strengths, '')),
           development_areas = btrim(coalesce(p_development_areas, '')),
           recommendations = btrim(coalesce(p_recommendations, '')),
           followup_date = p_followup_date,
           followup_notes = btrim(coalesce(p_followup_notes, '')),
           status = p_status,
           closed_at = v_closed_at
     where school_id = p_school_id
       and academic_year_id = p_academic_year_id
       and id = p_visit_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, p_academic_year_id, (select auth.uid()), 'supervision',
        'تحديث زيارة: ' || v_teacher_name, p_status,
        'supervision_visit', p_visit_id
    );
end;
$$;

create or replace function public.marsad_create_supervision_action_v1(
    p_school_id uuid,
    p_visit_id bigint,
    p_title text,
    p_responsible_teacher_id bigint,
    p_due_date date,
    p_status text,
    p_notes text
)
returns bigint
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_action_id bigint;
    v_academic_year_id bigint;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C2 manager role required' using errcode = '42501';
    end if;
    if char_length(btrim(coalesce(p_title, ''))) < 3 or char_length(p_title) > 500
       or char_length(coalesce(p_notes, '')) > 2500
       or p_status not in ('new', 'in_progress', 'completed', 'cancelled') then
        raise exception 'invalid supervision action payload' using errcode = '22023';
    end if;

    select sv.academic_year_id
      into v_academic_year_id
      from public.supervision_visits sv
     where sv.school_id = p_school_id and sv.id = p_visit_id;
    if not found then
        raise exception 'supervision visit not found in tenant scope' using errcode = 'P0002';
    end if;

    if p_responsible_teacher_id is not null and not exists (
        select 1
          from public.teachers t
          join public.teacher_years ty
            on ty.school_id=t.school_id and ty.teacher_id=t.id
           and ty.academic_year_id=v_academic_year_id and ty.is_active
         where t.school_id=p_school_id and t.id=p_responsible_teacher_id and t.is_active
    ) then
        raise exception 'responsible teacher is not active in visit academic year' using errcode = '23503';
    end if;

    insert into public.supervision_actions (
        school_id, visit_id, title, responsible_teacher_id,
        due_date, status, notes, completed_at
    ) values (
        p_school_id, p_visit_id, btrim(p_title), p_responsible_teacher_id,
        p_due_date, p_status, btrim(coalesce(p_notes, '')),
        case when p_status='completed' then now() else null end
    ) returning id into v_action_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, v_academic_year_id, (select auth.uid()), 'supervision',
        'إجراء متابعة: ' || btrim(p_title), p_status,
        'supervision_visit', p_visit_id
    );

    return v_action_id;
end;
$$;

create or replace function public.marsad_update_supervision_action_v1(
    p_school_id uuid,
    p_visit_id bigint,
    p_action_id bigint,
    p_title text,
    p_responsible_teacher_id bigint,
    p_due_date date,
    p_status text,
    p_notes text
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_academic_year_id bigint;
    v_completed_at timestamptz;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C2 manager role required' using errcode = '42501';
    end if;
    if char_length(btrim(coalesce(p_title, ''))) < 3 or char_length(p_title) > 500
       or char_length(coalesce(p_notes, '')) > 2500
       or p_status not in ('new', 'in_progress', 'completed', 'cancelled') then
        raise exception 'invalid supervision action payload' using errcode = '22023';
    end if;

    select sv.academic_year_id, sa.completed_at
      into v_academic_year_id, v_completed_at
      from public.supervision_actions sa
      join public.supervision_visits sv
        on sv.school_id=sa.school_id and sv.id=sa.visit_id
     where sa.school_id=p_school_id
       and sa.visit_id=p_visit_id
       and sa.id=p_action_id
     for update of sa;
    if not found then
        raise exception 'supervision action not found in visit scope' using errcode = 'P0002';
    end if;

    if p_responsible_teacher_id is not null and not exists (
        select 1
          from public.teachers t
          join public.teacher_years ty
            on ty.school_id=t.school_id and ty.teacher_id=t.id
           and ty.academic_year_id=v_academic_year_id and ty.is_active
         where t.school_id=p_school_id and t.id=p_responsible_teacher_id and t.is_active
    ) then
        raise exception 'responsible teacher is not active in visit academic year' using errcode = '23503';
    end if;

    if p_status='completed' and v_completed_at is null then
        v_completed_at := now();
    elsif p_status<>'completed' then
        v_completed_at := null;
    end if;

    update public.supervision_actions
       set title=btrim(p_title),
           responsible_teacher_id=p_responsible_teacher_id,
           due_date=p_due_date,
           status=p_status,
           notes=btrim(coalesce(p_notes, '')),
           completed_at=v_completed_at
     where school_id=p_school_id and visit_id=p_visit_id and id=p_action_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, v_academic_year_id, (select auth.uid()), 'supervision',
        'تحديث إجراء: ' || btrim(p_title), p_status,
        'supervision_visit', p_visit_id
    );
end;
$$;

create or replace function public.marsad_delete_supervision_action_v1(
    p_school_id uuid,
    p_visit_id bigint,
    p_action_id bigint
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_academic_year_id bigint;
    v_title text;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C2 manager role required' using errcode = '42501';
    end if;

    select sv.academic_year_id, sa.title
      into v_academic_year_id, v_title
      from public.supervision_actions sa
      join public.supervision_visits sv
        on sv.school_id=sa.school_id and sv.id=sa.visit_id
     where sa.school_id=p_school_id and sa.visit_id=p_visit_id and sa.id=p_action_id
     for update of sa;
    if not found then
        raise exception 'supervision action not found in visit scope' using errcode = 'P0002';
    end if;

    delete from public.supervision_actions
     where school_id=p_school_id and visit_id=p_visit_id and id=p_action_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, v_academic_year_id, (select auth.uid()), 'supervision',
        'حذف إجراء: ' || v_title, 'تم الحذف من متابعة الزيارة',
        'supervision_visit', p_visit_id
    );
end;
$$;

revoke all on function public.marsad_create_supervision_visit_v1(uuid,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text) from public, anon, authenticated;
revoke all on function public.marsad_update_supervision_visit_v1(uuid,bigint,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text) from public, anon, authenticated;
revoke all on function public.marsad_create_supervision_action_v1(uuid,bigint,text,bigint,date,text,text) from public, anon, authenticated;
revoke all on function public.marsad_update_supervision_action_v1(uuid,bigint,bigint,text,bigint,date,text,text) from public, anon, authenticated;
revoke all on function public.marsad_delete_supervision_action_v1(uuid,bigint,bigint) from public, anon, authenticated;

grant execute on function public.marsad_create_supervision_visit_v1(uuid,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text) to authenticated;
grant execute on function public.marsad_update_supervision_visit_v1(uuid,bigint,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text) to authenticated;
grant execute on function public.marsad_create_supervision_action_v1(uuid,bigint,text,bigint,date,text,text) to authenticated;
grant execute on function public.marsad_update_supervision_action_v1(uuid,bigint,bigint,text,bigint,date,text,text) to authenticated;
grant execute on function public.marsad_delete_supervision_action_v1(uuid,bigint,bigint) to authenticated;

commit;
