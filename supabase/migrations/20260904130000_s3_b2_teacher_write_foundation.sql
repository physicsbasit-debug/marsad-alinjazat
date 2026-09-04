-- Marsad Al-Injazat — Phase S3-B2
-- Teacher write foundation: unlock owner/admin writes to teacher_years and expose
-- atomic SECURITY INVOKER RPCs for teacher create/update. No Teachers UI cutover.

begin;

-- teacher_years was deliberately locked in S2-C2. S3-B2 opens only the columns
-- needed by the verified teacher create/update workflow. RLS remains authoritative.
grant insert (
    school_id,
    academic_year_id,
    teacher_id,
    subject,
    experience_years,
    workload,
    grades,
    responsibilities
) on table public.teacher_years to authenticated;

grant update (
    subject,
    experience_years,
    workload,
    grades,
    responsibilities
) on table public.teacher_years to authenticated;

drop policy if exists teacher_years_insert_managers on public.teacher_years;
drop policy if exists teacher_years_update_managers on public.teacher_years;

create policy teacher_years_insert_managers
    on public.teacher_years
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy teacher_years_update_managers
    on public.teacher_years
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

-- Atomic create/link operation. SECURITY INVOKER is deliberate: the caller's
-- authenticated grants and RLS policies remain in force throughout the function.
create or replace function public.marsad_create_teacher_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_name text,
    p_subject text,
    p_specialization text default null,
    p_qualification text default null,
    p_experience_years integer default 0,
    p_workload integer default 0,
    p_email text default null,
    p_phone text default null
)
returns table(teacher_id bigint, linked_existing boolean)
language plpgsql
volatile
security invoker
set search_path = ''
as $$
declare
    v_teacher_id bigint;
    v_match_count integer := 0;
    v_linked_existing boolean := false;
    v_name text := btrim(coalesce(p_name, ''));
    v_subject text := btrim(coalesce(p_subject, ''));
    v_specialization text := nullif(btrim(coalesce(p_specialization, '')), '');
    v_qualification text := nullif(btrim(coalesce(p_qualification, '')), '');
    v_email text := nullif(lower(btrim(coalesce(p_email, ''))), '');
    v_phone text := nullif(btrim(coalesce(p_phone, '')), '');
    v_identity_lock text;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception using errcode = '42501', message = 'teacher write denied for this school';
    end if;

    if not exists (
        select 1
        from public.academic_years ay
        where ay.school_id = p_school_id
          and ay.id = p_academic_year_id
    ) then
        raise exception using errcode = '23503', message = 'academic year does not belong to school';
    end if;

    if char_length(v_name) < 3 or char_length(v_name) > 120 then
        raise exception using errcode = '22023', message = 'teacher name length is invalid';
    end if;
    if char_length(v_subject) < 2 or char_length(v_subject) > 80 then
        raise exception using errcode = '22023', message = 'teacher subject length is invalid';
    end if;
    if v_specialization is not null and char_length(v_specialization) > 120 then
        raise exception using errcode = '22023', message = 'teacher specialization is too long';
    end if;
    if v_qualification is not null and char_length(v_qualification) > 160 then
        raise exception using errcode = '22023', message = 'teacher qualification is too long';
    end if;
    if v_email is not null and char_length(v_email) > 160 then
        raise exception using errcode = '22023', message = 'teacher email is too long';
    end if;
    if v_phone is not null and char_length(v_phone) > 40 then
        raise exception using errcode = '22023', message = 'teacher phone is too long';
    end if;
    if p_experience_years < 0 or p_experience_years > 60 then
        raise exception using errcode = '22023', message = 'teacher experience is outside allowed range';
    end if;
    if p_workload < 0 or p_workload > 40 then
        raise exception using errcode = '22023', message = 'teacher workload is outside allowed range';
    end if;

    v_identity_lock := p_school_id::text || '|' || coalesce(v_email, lower(v_name) || '|' || lower(v_subject));
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_identity_lock, 0));

    if v_email is not null then
        select count(*), min(t.id)
          into v_match_count, v_teacher_id
          from public.teachers t
         where t.school_id = p_school_id
           and lower(btrim(coalesce(t.email, ''))) = v_email;
        if v_match_count > 1 then
            raise exception using errcode = '21000', message = 'ambiguous teacher identity by email';
        end if;
    end if;

    if v_teacher_id is null then
        select count(distinct t.id), min(t.id)
          into v_match_count, v_teacher_id
          from public.teachers t
         where t.school_id = p_school_id
           and lower(btrim(t.name)) = lower(v_name)
           and exists (
               select 1
                 from public.teacher_years ty
                where ty.school_id = p_school_id
                  and ty.teacher_id = t.id
                  and lower(btrim(coalesce(ty.subject, ''))) = lower(v_subject)
           );
        if v_match_count > 1 then
            raise exception using errcode = '21000', message = 'ambiguous teacher identity by name and subject';
        end if;
    end if;

    if v_teacher_id is null then
        insert into public.teachers (
            school_id, name, specialization, qualification, email, phone, is_active
        ) values (
            p_school_id, v_name, v_specialization, v_qualification, v_email, v_phone, true
        )
        returning id into v_teacher_id;
        v_linked_existing := false;
    else
        v_linked_existing := true;
    end if;

    insert into public.teacher_years (
        school_id, academic_year_id, teacher_id, subject,
        experience_years, workload
    ) values (
        p_school_id, p_academic_year_id, v_teacher_id, v_subject,
        p_experience_years::smallint, p_workload::smallint
    )
    on conflict (school_id, academic_year_id, teacher_id) do nothing;

    return query select v_teacher_id, v_linked_existing;
end;
$$;

-- Atomic profile update for the current staged academic-year context.
create or replace function public.marsad_update_teacher_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_teacher_id bigint,
    p_name text,
    p_subject text,
    p_specialization text default null,
    p_qualification text default null,
    p_experience_years integer default 0,
    p_workload integer default 0,
    p_email text default null,
    p_phone text default null,
    p_employee_number text default null,
    p_school_join_year integer default null,
    p_grades text default null,
    p_responsibilities text default null,
    p_professional_summary text default null
)
returns bigint
language plpgsql
volatile
security invoker
set search_path = ''
as $$
declare
    v_name text := btrim(coalesce(p_name, ''));
    v_subject text := btrim(coalesce(p_subject, ''));
    v_specialization text := nullif(btrim(coalesce(p_specialization, '')), '');
    v_qualification text := nullif(btrim(coalesce(p_qualification, '')), '');
    v_email text := nullif(lower(btrim(coalesce(p_email, ''))), '');
    v_phone text := nullif(btrim(coalesce(p_phone, '')), '');
    v_employee_number text := nullif(btrim(coalesce(p_employee_number, '')), '');
    v_grades text := nullif(btrim(coalesce(p_grades, '')), '');
    v_responsibilities text := nullif(btrim(coalesce(p_responsibilities, '')), '');
    v_professional_summary text := nullif(btrim(coalesce(p_professional_summary, '')), '');
    v_count integer;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception using errcode = '42501', message = 'teacher write denied for this school';
    end if;

    if not exists (
        select 1 from public.academic_years ay
        where ay.school_id = p_school_id and ay.id = p_academic_year_id
    ) then
        raise exception using errcode = '23503', message = 'academic year does not belong to school';
    end if;

    select count(*) into v_count
      from public.teachers t
     where t.school_id = p_school_id
       and t.id = p_teacher_id;
    if v_count <> 1 then
        raise exception using errcode = 'P0002', message = 'teacher does not exist in school';
    end if;

    if char_length(v_name) < 3 or char_length(v_name) > 120 then
        raise exception using errcode = '22023', message = 'teacher name length is invalid';
    end if;
    if char_length(v_subject) < 2 or char_length(v_subject) > 80 then
        raise exception using errcode = '22023', message = 'teacher subject length is invalid';
    end if;
    if v_specialization is not null and char_length(v_specialization) > 120 then
        raise exception using errcode = '22023', message = 'teacher specialization is too long';
    end if;
    if v_qualification is not null and char_length(v_qualification) > 160 then
        raise exception using errcode = '22023', message = 'teacher qualification is too long';
    end if;
    if v_email is not null and char_length(v_email) > 160 then
        raise exception using errcode = '22023', message = 'teacher email is too long';
    end if;
    if v_phone is not null and char_length(v_phone) > 40 then
        raise exception using errcode = '22023', message = 'teacher phone is too long';
    end if;
    if v_employee_number is not null and char_length(v_employee_number) > 80 then
        raise exception using errcode = '22023', message = 'employee number is too long';
    end if;
    if p_school_join_year is not null and (p_school_join_year < 1950 or p_school_join_year > 2100) then
        raise exception using errcode = '22023', message = 'school join year is outside allowed range';
    end if;
    if char_length(coalesce(v_grades, '')) > 220 then
        raise exception using errcode = '22023', message = 'grades field is too long';
    end if;
    if char_length(coalesce(v_responsibilities, '')) > 2000 then
        raise exception using errcode = '22023', message = 'responsibilities field is too long';
    end if;
    if char_length(coalesce(v_professional_summary, '')) > 2500 then
        raise exception using errcode = '22023', message = 'professional summary is too long';
    end if;
    if p_experience_years < 0 or p_experience_years > 60 then
        raise exception using errcode = '22023', message = 'teacher experience is outside allowed range';
    end if;
    if p_workload < 0 or p_workload > 40 then
        raise exception using errcode = '22023', message = 'teacher workload is outside allowed range';
    end if;

    if v_email is not null and exists (
        select 1
          from public.teachers t
         where t.school_id = p_school_id
           and t.id <> p_teacher_id
           and lower(btrim(coalesce(t.email, ''))) = v_email
    ) then
        raise exception using errcode = '23505', message = 'teacher email already belongs to another teacher';
    end if;

    update public.teachers
       set name = v_name,
           specialization = v_specialization,
           qualification = v_qualification,
           email = v_email,
           phone = v_phone
     where school_id = p_school_id
       and id = p_teacher_id;

    insert into public.teacher_years (
        school_id, academic_year_id, teacher_id, subject,
        experience_years, workload, grades, responsibilities
    ) values (
        p_school_id, p_academic_year_id, p_teacher_id, v_subject,
        p_experience_years::smallint, p_workload::smallint,
        v_grades, v_responsibilities
    )
    on conflict (school_id, academic_year_id, teacher_id) do update
       set subject = excluded.subject,
           experience_years = excluded.experience_years,
           workload = excluded.workload,
           grades = excluded.grades,
           responsibilities = excluded.responsibilities;

    insert into public.teacher_profiles (
        teacher_id, school_id, employee_number, school_join_year, professional_summary
    ) values (
        p_teacher_id, p_school_id, v_employee_number,
        p_school_join_year::smallint, v_professional_summary
    )
    on conflict (teacher_id) do update
       set employee_number = excluded.employee_number,
           school_join_year = excluded.school_join_year,
           professional_summary = excluded.professional_summary;

    return p_teacher_id;
end;
$$;

revoke all on function public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)
    from public, anon, authenticated;
revoke all on function public.marsad_update_teacher_v1(uuid,bigint,bigint,text,text,text,text,integer,integer,text,text,text,integer,text,text,text)
    from public, anon, authenticated;

grant execute on function public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)
    to authenticated;
grant execute on function public.marsad_update_teacher_v1(uuid,bigint,bigint,text,text,text,text,integer,integer,text,text,text,integer,text,text,text)
    to authenticated;

commit;
