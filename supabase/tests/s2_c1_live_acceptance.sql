-- S2-C1 live acceptance
-- Prerequisite: after applying the S2-C1 migration, create one temporary Auth user
-- from Supabase Dashboard > Authentication > Users so the auth->profile trigger is exercised.
-- This script never inserts/updates/deletes auth.users and rolls back all public test data.

begin;

-- Structural security checks as postgres/Supabase SQL Editor owner.
do $$
declare
    v_count integer;
    v_tables text[] := array[
        'schools', 'profiles', 'school_memberships', 'academic_years', 'school_settings'
    ];
begin
    select count(*)
      into v_count
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public'
       and c.relname = any(v_tables)
       and c.relrowsecurity;
    if v_count <> 5 then
        raise exception 'S2-C1 acceptance failed: expected RLS on 5 core tables, got %', v_count;
    end if;

    select count(*)
      into v_count
      from pg_policies
     where schemaname = 'public'
       and tablename = any(v_tables);
    if v_count <> 11 then
        raise exception 'S2-C1 acceptance failed: expected 11 core policies, got %', v_count;
    end if;

    if exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename <> all(v_tables)
    ) then
        raise exception 'S2-C1 acceptance failed: policy leaked onto a non-core table before S2-C2';
    end if;

    select count(*)
      into v_count
      from information_schema.role_table_grants
     where table_schema = 'public'
       and grantee = 'anon';
    if v_count <> 0 then
        raise exception 'S2-C1 acceptance failed: anon received public table grants (%)', v_count;
    end if;

    if exists (
        select 1
        from information_schema.role_table_grants
        where table_schema = 'public'
          and grantee = 'authenticated'
          and table_name <> all(v_tables)
    ) then
        raise exception 'S2-C1 acceptance failed: authenticated grant leaked onto a non-core table';
    end if;

    select count(*)
      into v_count
      from information_schema.role_table_grants
     where table_schema = 'public'
       and grantee = 'authenticated'
       and privilege_type = 'SELECT'
       and table_name = any(v_tables);
    if v_count <> 5 then
        raise exception 'S2-C1 acceptance failed: authenticated SELECT table grants expected 5, got %', v_count;
    end if;

    if exists (
        select 1
        from information_schema.role_table_grants
        where table_schema = 'public'
          and grantee = 'authenticated'
          and privilege_type in ('INSERT', 'UPDATE', 'DELETE')
    ) then
        raise exception 'S2-C1 acceptance failed: broad table-level write grant detected';
    end if;

    if exists (
        select 1
        from information_schema.role_column_grants
        where table_schema = 'public'
          and grantee = 'authenticated'
          and privilege_type in ('INSERT', 'UPDATE', 'DELETE')
          and not (
              (table_name = 'schools' and privilege_type = 'UPDATE' and column_name in ('name', 'is_active'))
              or (table_name = 'profiles' and privilege_type = 'UPDATE' and column_name = 'display_name')
              or (table_name = 'academic_years' and privilege_type = 'INSERT' and column_name in ('school_id', 'label', 'start_year', 'end_year', 'is_current'))
              or (table_name = 'academic_years' and privilege_type = 'UPDATE' and column_name in ('label', 'start_year', 'end_year', 'is_current'))
              or (table_name = 'school_settings' and privilege_type = 'INSERT' and column_name in ('school_id', 'key', 'value', 'updated_by'))
              or (table_name = 'school_settings' and privilege_type = 'UPDATE' and column_name in ('value', 'updated_by'))
          )
    ) then
        raise exception 'S2-C1 acceptance failed: unexpected authenticated column write grant detected';
    end if;

    if not has_schema_privilege('authenticated', 'private', 'USAGE') then
        raise exception 'S2-C1 acceptance failed: authenticated cannot resolve private RLS helpers';
    end if;
    if not has_function_privilege('authenticated', 'private.is_active_school_member(uuid)', 'EXECUTE')
       or not has_function_privilege('authenticated', 'private.has_school_role(uuid,text[])', 'EXECUTE')
       or not has_function_privilege('authenticated', 'private.can_view_profile(uuid)', 'EXECUTE') then
        raise exception 'S2-C1 acceptance failed: authenticated helper EXECUTE grant missing';
    end if;
    if has_function_privilege('authenticated', 'private.handle_new_auth_user()', 'EXECUTE') then
        raise exception 'S2-C1 acceptance failed: authenticated can execute Auth trigger function directly';
    end if;

    select count(*)
      into v_count
      from pg_trigger t
      join pg_class c on c.oid = t.tgrelid
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'auth'
       and c.relname = 'users'
       and t.tgname = 'on_marsad_auth_user_created'
       and not t.tgisinternal;
    if v_count <> 1 then
        raise exception 'S2-C1 acceptance failed: Auth profile trigger missing';
    end if;
end $$;

-- Select the newest real Auth user. The migration never creates users automatically.
select set_config(
    'marsad.test_user_id',
    coalesce((select id::text from auth.users order by created_at desc limit 1), ''),
    true
);

do $$
begin
    if nullif(current_setting('marsad.test_user_id', true), '') is null then
        raise exception 'S2-C1 acceptance prerequisite: create one temporary Auth user in Dashboard Authentication > Users, then rerun this acceptance script';
    end if;
end $$;

-- The newest user must have been created after S2-C1 so the trigger itself is proven.
do $$
declare
    v_uid uuid := current_setting('marsad.test_user_id')::uuid;
begin
    if not exists (select 1 from public.profiles where id = v_uid) then
        raise exception 'S2-C1 acceptance prerequisite: newest Auth user has no public profile; create one temporary Auth user after applying S2-C1, then rerun';
    end if;
end $$;

-- Create tenant fixtures as database owner. Everything below is rolled back.
do $$
declare
    v_uid uuid := current_setting('marsad.test_user_id')::uuid;
    v_school_a uuid;
    v_school_b uuid;
begin
    insert into public.schools (name)
    values ('S2-C1 Acceptance School A')
    returning id into v_school_a;

    insert into public.schools (name)
    values ('S2-C1 Acceptance School B')
    returning id into v_school_b;

    insert into public.school_memberships (school_id, user_id, role, status)
    values (v_school_a, v_uid, 'owner', 'active');

    perform set_config('marsad.school_a', v_school_a::text, true);
    perform set_config('marsad.school_b', v_school_b::text, true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.test_user_id'), true);
select set_config(
    'request.jwt.claims',
    json_build_object(
        'sub', current_setting('marsad.test_user_id'),
        'role', 'authenticated'
    )::text,
    true
);

set local role authenticated;

do $$
declare
    v_uid uuid := current_setting('marsad.test_user_id')::uuid;
    v_school_a uuid := current_setting('marsad.school_a')::uuid;
    v_school_b uuid := current_setting('marsad.school_b')::uuid;
    v_count integer;
    v_rows integer;
    v_blocked boolean;
begin
    select count(*) into v_count
    from public.schools
    where id in (v_school_a, v_school_b);
    if v_count <> 1 then
        raise exception 'S2-C1 acceptance failed: owner should see only its member school, saw %', v_count;
    end if;

    select count(*) into v_count from public.profiles where id = v_uid;
    if v_count <> 1 then
        raise exception 'S2-C1 acceptance failed: user cannot read own profile';
    end if;

    select count(*) into v_count
    from public.school_memberships
    where school_id in (v_school_a, v_school_b);
    if v_count <> 1 then
        raise exception 'S2-C1 acceptance failed: membership visibility count=%', v_count;
    end if;

    update public.profiles
       set display_name = 'S2-C1 Acceptance User'
     where id = v_uid;
    get diagnostics v_rows = row_count;
    if v_rows <> 1 then
        raise exception 'S2-C1 acceptance failed: self profile update did not affect one row';
    end if;

    update public.schools
       set name = 'S2-C1 Acceptance School A Updated'
     where id = v_school_a;
    get diagnostics v_rows = row_count;
    if v_rows <> 1 then
        raise exception 'S2-C1 acceptance failed: owner could not update own school';
    end if;

    update public.schools
       set name = 'SHOULD NOT UPDATE'
     where id = v_school_b;
    get diagnostics v_rows = row_count;
    if v_rows <> 0 then
        raise exception 'S2-C1 acceptance failed: cross-school update unexpectedly affected % rows', v_rows;
    end if;

    insert into public.academic_years (school_id, label, start_year, end_year, is_current)
    values (v_school_a, '2098/2099', 2098, 2099, false);

    v_blocked := false;
    begin
        insert into public.academic_years (school_id, label, start_year, end_year, is_current)
        values (v_school_b, '2098/2099', 2098, 2099, false);
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S2-C1 acceptance failed: cross-school academic year insert unexpectedly succeeded';
    end if;

    insert into public.school_settings (school_id, key, value, updated_by)
    values (v_school_a, 's2_c1_acceptance', '{"ok":true}'::jsonb, v_uid);

    v_blocked := false;
    begin
        insert into public.school_settings (school_id, key, value, updated_by)
        values (v_school_b, 's2_c1_acceptance', '{"ok":false}'::jsonb, v_uid);
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S2-C1 acceptance failed: cross-school settings insert unexpectedly succeeded';
    end if;

    -- Critical privilege-escalation proof: even an owner has no direct browser grant
    -- to mutate membership role/status.
    v_blocked := false;
    begin
        update public.school_memberships
           set role = 'admin'
         where school_id = v_school_a and user_id = v_uid;
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S2-C1 acceptance failed: browser membership write unexpectedly succeeded';
    end if;

    v_blocked := false;
    begin
        insert into public.schools (name) values ('SHOULD NOT CREATE');
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S2-C1 acceptance failed: browser school creation unexpectedly succeeded';
    end if;

    v_blocked := false;
    begin
        delete from public.academic_years
         where school_id = v_school_a and label = '2098/2099';
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S2-C1 acceptance failed: browser academic-year delete unexpectedly succeeded';
    end if;
end $$;

reset role;

select 'PASS: S2-C1 security foundation acceptance' as result;
rollback;
