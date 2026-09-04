-- Marsad Al-Injazat — Phase S3-B2R1
-- Teacher write RPC ambiguity correction.
-- The original S3-B2 migration is immutable because it has already been applied live.
-- This migration replaces only marsad_create_teacher_v1 with the same signature/semantics
-- and uses an explicit constraint conflict target so the RETURNS TABLE output variable
-- teacher_id cannot collide with the teacher_years.teacher_id column name.

begin;

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
    on conflict on constraint teacher_years_pkey do nothing;

    return query select v_teacher_id, v_linked_existing;
end;
$$;


commit;
