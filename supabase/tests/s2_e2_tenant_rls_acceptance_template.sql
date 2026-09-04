-- Marsad Al-Injazat — S2-E2 tenant RLS acceptance TEMPLATE
-- Read/rollback acceptance. Personalize outside the public repository.

begin;

do $$
declare
    v_owner_email text := '__OWNER_EMAIL__';
    v_school_name text := '__SCHOOL_NAME__';
    v_owner_id uuid;
    v_school_id uuid;
    v_count integer;
begin
    if left(v_owner_email, 2) = '__' or left(v_school_name, 2) = '__' then
        raise exception 'S2-E2 acceptance template must be personalized before live use';
    end if;

    select count(*) into v_count from auth.users where lower(email) = lower(v_owner_email);
    if v_count <> 1 then
        raise exception 'S2-E2 acceptance prerequisite failed: configured owner Auth user count=%', v_count;
    end if;
    select id into v_owner_id from auth.users where lower(email) = lower(v_owner_email) limit 1;

    select count(*) into v_count from public.schools where name = v_school_name;
    if v_count <> 1 then
        raise exception 'S2-E2 acceptance prerequisite failed: configured school count=%', v_count;
    end if;
    select id into v_school_id from public.schools where name = v_school_name limit 1;

    if (select count(*) from public.school_memberships where school_id=v_school_id and user_id=v_owner_id and role='owner' and status='active') <> 1 then
        raise exception 'S2-E2 acceptance prerequisite failed: active owner membership missing';
    end if;
    if (select count(*) from public.academic_years where school_id=v_school_id and label='2026/2027' and start_year=2026 and end_year=2027 and is_current) <> 1 then
        raise exception 'S2-E2 acceptance prerequisite failed: current academic year missing';
    end if;

    perform set_config('marsad.s2e2_owner_id', v_owner_id::text, true);
    perform set_config('marsad.s2e2_school_id', v_school_id::text, true);
end $$;

-- Create an unrelated tenant only inside this rollback transaction to prove isolation.
do $$
declare
    v_other_school_id uuid;
begin
    insert into public.schools (name, is_active)
    values ('S2-E2 isolated acceptance tenant ' || gen_random_uuid()::text, true)
    returning id into v_other_school_id;
    perform set_config('marsad.s2e2_other_school_id', v_other_school_id::text, true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.s2e2_owner_id'), true);
select set_config('request.jwt.claims', json_build_object('sub', current_setting('marsad.s2e2_owner_id'), 'role', 'authenticated')::text, true);
set local role authenticated;

do $$
declare
    v_school_id uuid := current_setting('marsad.s2e2_school_id')::uuid;
    v_count integer;
    v_other_visible integer;
begin
    select count(*) into v_count from public.schools where id = v_school_id;
    if v_count <> 1 then raise exception 'S2-E2 RLS failed: owner cannot read own school'; end if;

    select count(*) into v_count from public.school_memberships where school_id = v_school_id and user_id = auth.uid() and role='owner' and status='active';
    if v_count <> 1 then raise exception 'S2-E2 RLS failed: owner cannot read own membership'; end if;

    select count(*) into v_count from public.academic_years where school_id = v_school_id and label='2026/2027' and is_current;
    if v_count <> 1 then raise exception 'S2-E2 RLS failed: owner cannot read current academic year'; end if;

    select count(*) into v_other_visible
      from public.schools
     where id = current_setting('marsad.s2e2_other_school_id')::uuid;
    if v_other_visible <> 0 then raise exception 'S2-E2 RLS failed: owner can see the unrelated acceptance tenant'; end if;

    if not private.has_school_role(v_school_id, array['owner']::text[]) then
        raise exception 'S2-E2 RLS failed: owner role helper rejected the real owner';
    end if;

    update public.schools set name = name where id = v_school_id;
    get diagnostics v_count = row_count;
    if v_count <> 1 then raise exception 'S2-E2 RLS failed: owner cannot perform allowed school update'; end if;
end $$;

reset role;

-- A random authenticated identity with no membership must see none of the real tenant.
select set_config('request.jwt.claim.sub', gen_random_uuid()::text, true);
select set_config('request.jwt.claims', json_build_object('sub', current_setting('request.jwt.claim.sub'), 'role', 'authenticated')::text, true);
set local role authenticated;

do $$
declare
    v_school_id uuid := current_setting('marsad.s2e2_school_id')::uuid;
    v_count integer;
begin
    select count(*) into v_count from public.schools where id = v_school_id;
    if v_count <> 0 then raise exception 'S2-E2 RLS failed: non-member can read the real school'; end if;

    select count(*) into v_count from public.school_memberships where school_id = v_school_id;
    if v_count <> 0 then raise exception 'S2-E2 RLS failed: non-member can read school memberships'; end if;

    select count(*) into v_count from public.academic_years where school_id = v_school_id;
    if v_count <> 0 then raise exception 'S2-E2 RLS failed: non-member can read academic years'; end if;
end $$;

reset role;

select 'PASS: S2-E2 tenant RLS acceptance' as result;

rollback;
