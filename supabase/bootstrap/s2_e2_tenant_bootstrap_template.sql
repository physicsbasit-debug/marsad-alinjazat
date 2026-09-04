-- Marsad Al-Injazat — S2-E2 production tenant bootstrap TEMPLATE
-- This file is safe to commit because it contains placeholders, not the real owner email or school name.
-- Generate/use the personalized live copy outside the public repository.

begin;

do $$
declare
    v_owner_email text := '__OWNER_EMAIL__';
    v_school_name text := '__SCHOOL_NAME__';
    v_owner_id uuid;
    v_school_id uuid;
    v_auth_count integer;
    v_school_count integer;
    v_existing_role text;
    v_existing_status text;
    v_year_id bigint;
    v_year_start smallint;
    v_year_end smallint;
    v_year_current boolean;
    v_conflicting_current integer;
begin
    if left(v_owner_email, 2) = '__' or btrim(v_owner_email) = '' then
        raise exception 'S2-E2 bootstrap template must be personalized before live use';
    end if;
    if left(v_school_name, 2) = '__' or btrim(v_school_name) = '' then
        raise exception 'S2-E2 bootstrap template must be personalized before live use';
    end if;

    select count(*)
      into v_auth_count
      from auth.users
     where lower(email) = lower(v_owner_email);

    if v_auth_count <> 1 then
        raise exception 'S2-E2 bootstrap requires exactly one existing Auth user for the configured owner email; found %', v_auth_count;
    end if;

    select id
      into v_owner_id
      from auth.users
     where lower(email) = lower(v_owner_email)
     limit 1;

    -- A pre-trigger Auth account may lack public.profiles; create only that safe projection.
    insert into public.profiles (id, display_name)
    values (v_owner_id, null)
    on conflict (id) do nothing;

    select count(*)
      into v_school_count
      from public.schools
     where name = v_school_name;

    if v_school_count > 1 then
        raise exception 'S2-E2 bootstrap refused: duplicate schools already exist with the configured name';
    elsif v_school_count = 0 then
        insert into public.schools (name, is_active)
        values (v_school_name, true)
        returning id into v_school_id;
    else
        select id
          into v_school_id
          from public.schools
         where name = v_school_name
         limit 1;

        if not (select is_active from public.schools where id = v_school_id) then
            raise exception 'S2-E2 bootstrap refused: existing school is inactive';
        end if;
    end if;

    select role, status
      into v_existing_role, v_existing_status
      from public.school_memberships
     where school_id = v_school_id
       and user_id = v_owner_id;

    if found then
        if v_existing_role <> 'owner' or v_existing_status <> 'active' then
            raise exception 'S2-E2 bootstrap refused: owner membership exists with role/status %/%', v_existing_role, v_existing_status;
        end if;
    else
        insert into public.school_memberships (school_id, user_id, teacher_id, role, status)
        values (v_school_id, v_owner_id, null, 'owner', 'active');
    end if;

    select count(*)
      into v_conflicting_current
      from public.academic_years
     where school_id = v_school_id
       and is_current
       and label <> '2026/2027';

    if v_conflicting_current > 0 then
        raise exception 'S2-E2 bootstrap refused: another academic year is already current for this school';
    end if;

    select id, start_year, end_year, is_current
      into v_year_id, v_year_start, v_year_end, v_year_current
      from public.academic_years
     where school_id = v_school_id
       and label = '2026/2027';

    if found then
        if v_year_start <> 2026 or v_year_end <> 2027 then
            raise exception 'S2-E2 bootstrap refused: 2026/2027 exists with inconsistent year bounds';
        end if;
        if not v_year_current then
            update public.academic_years
               set is_current = true
             where id = v_year_id;
        end if;
    else
        insert into public.academic_years (school_id, label, start_year, end_year, is_current)
        values (v_school_id, '2026/2027', 2026, 2027, true)
        returning id into v_year_id;
    end if;

    if (select count(*) from public.school_memberships where school_id = v_school_id and user_id = v_owner_id and role = 'owner' and status = 'active') <> 1 then
        raise exception 'S2-E2 bootstrap verification failed: owner membership not established';
    end if;

    if (select count(*) from public.academic_years where school_id = v_school_id and label = '2026/2027' and start_year = 2026 and end_year = 2027 and is_current) <> 1 then
        raise exception 'S2-E2 bootstrap verification failed: current academic year not established';
    end if;
end $$;

select
    'PASS: S2-E2 production tenant bootstrap' as result,
    s.id as school_id,
    s.name as school_name,
    ay.id as academic_year_id,
    ay.label as academic_year,
    sm.role as owner_role,
    sm.status as owner_status
from public.schools s
join public.school_memberships sm on sm.school_id = s.id
join auth.users u on u.id = sm.user_id
join public.academic_years ay on ay.school_id = s.id and ay.is_current
where s.name = '__SCHOOL_NAME__'
  and lower(u.email) = lower('__OWNER_EMAIL__')
  and sm.role = 'owner'
  and sm.status = 'active'
  and ay.label = '2026/2027';

commit;
