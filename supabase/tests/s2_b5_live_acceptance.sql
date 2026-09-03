-- Marsad Al-Injazat — S2-B5 whole-schema live acceptance
-- Run AFTER the S2-B5 migration in Supabase SQL Editor.
-- Safe: the only test row is removed by the final ROLLBACK.
-- S2-C has not started yet, so browser grants and RLS policies must remain zero.

begin;

do $$
declare
    v_expected_tables text[] := array[
        'schools','profiles','school_memberships','academic_years','school_settings',
        'teachers','teacher_profiles','teacher_years','teacher_cv_items',
        'upload_requests','documents','events','event_media','event_teacher_links','activities',
        'meetings','meeting_attendees','meeting_decisions','curriculum_plans','curriculum_units',
        'supervision_visits','supervision_actions','achievement_assessments',
        'achievement_assessment_standards','achievement_actions','achievement_action_metrics'
    ];
    v_updated_tables text[] := array[
        'schools','profiles','school_memberships','academic_years','school_settings',
        'teachers','teacher_profiles','teacher_years','teacher_cv_items','upload_requests',
        'events','event_media','meetings','meeting_decisions','curriculum_plans','curriculum_units',
        'supervision_visits','supervision_actions','achievement_assessments',
        'achievement_assessment_standards','achievement_actions','achievement_action_metrics'
    ];
    v_table_count integer;
    v_column_count integer;
    v_column_signature text;
    v_legacy_count integer;
    v_grant_count integer;
    v_policy_count integer;
    v_rls_count integer;
    v_sequence_leak_count integer;
    v_unvalidated_count integer;
    v_invalid_index_count integer;
    v_unsafe_fk_count integer;
    v_trigger_count integer;
    v_trigger_table_count integer;
    v_required_index_count integer;
    v_secret_column_count integer;
    v_raw_token_count integer;
    v_function_count integer;
    v_function_grant_count integer;
begin
    select count(*) into v_table_count
    from information_schema.tables
    where table_schema = 'public'
      and table_name = any(v_expected_tables);
    if v_table_count <> 26 then
        raise exception 'S2-B5 acceptance failed: expected 26 frozen target tables, found %', v_table_count;
    end if;

    select count(*) into v_legacy_count
    from information_schema.tables
    where table_schema = 'public'
      and table_name in ('request_record_years','event_record_years','teacher_record_years','event_media_meta');
    if v_legacy_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % removed legacy tables were recreated', v_legacy_count;
    end if;

    -- Exact frozen column/type/identity signature for all 299 target columns.
    select
        count(*),
        md5(string_agg(
            table_name || '.' || column_name || ':' || udt_name || ':' ||
            coalesce(numeric_precision::text,'') || ':' ||
            coalesce(numeric_scale::text,'') || ':' || is_identity,
            '|' order by table_name, ordinal_position
        ))
    into v_column_count, v_column_signature
    from information_schema.columns
    where table_schema = 'public'
      and table_name = any(v_expected_tables);

    if v_column_count <> 299 then
        raise exception 'S2-B5 acceptance failed: expected 299 frozen columns, found %', v_column_count;
    end if;
    if v_column_signature <> '186981dda2d7dab6889068fba74dcb3e' then
        raise exception 'S2-B5 acceptance failed: live column/type signature drifted: %', v_column_signature;
    end if;

    select count(*) into v_grant_count
    from information_schema.role_table_grants
    where table_schema = 'public'
      and table_name = any(v_expected_tables)
      and grantee in ('anon','authenticated');
    if v_grant_count <> 0 then
        raise exception 'S2-B5 acceptance failed: browser roles still have % table grants before S2-C', v_grant_count;
    end if;

    select count(*) into v_policy_count
    from pg_policies
    where schemaname = 'public'
      and tablename::text = any(v_expected_tables);
    if v_policy_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % RLS policies appeared before S2-C', v_policy_count;
    end if;

    -- Auto-RLS may have been applied externally by Supabase on some historical phases.
    -- That is acceptable here because browser grants and policies are both zero.
    select count(*) into v_rls_count
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname::text = any(v_expected_tables)
      and c.relrowsecurity;

    -- No public sequence may be usable by browser roles before S2-C.
    select count(*) into v_sequence_leak_count
    from pg_class s
    join pg_namespace n on n.oid = s.relnamespace
    where n.nspname = 'public'
      and s.relkind = 'S'
      and (
          has_sequence_privilege('anon', format('%I.%I', n.nspname, s.relname), 'USAGE')
          or has_sequence_privilege('anon', format('%I.%I', n.nspname, s.relname), 'SELECT')
          or has_sequence_privilege('anon', format('%I.%I', n.nspname, s.relname), 'UPDATE')
          or has_sequence_privilege('authenticated', format('%I.%I', n.nspname, s.relname), 'USAGE')
          or has_sequence_privilege('authenticated', format('%I.%I', n.nspname, s.relname), 'SELECT')
          or has_sequence_privilege('authenticated', format('%I.%I', n.nspname, s.relname), 'UPDATE')
      );
    if v_sequence_leak_count <> 0 then
        raise exception 'S2-B5 acceptance failed: browser roles can use % public sequences', v_sequence_leak_count;
    end if;

    -- Every constraint already installed on the 26 target tables must be validated.
    select count(*) into v_unvalidated_count
    from pg_constraint con
    join pg_class tbl on tbl.oid = con.conrelid
    join pg_namespace ns on ns.oid = tbl.relnamespace
    where ns.nspname = 'public'
      and tbl.relname::text = any(v_expected_tables)
      and not con.convalidated;
    if v_unvalidated_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % constraints are NOT VALID', v_unvalidated_count;
    end if;

    -- Every public-table index must be ready and valid before schema closure.
    select count(*) into v_invalid_index_count
    from pg_index i
    join pg_class tbl on tbl.oid = i.indrelid
    join pg_namespace ns on ns.oid = tbl.relnamespace
    where ns.nspname = 'public'
      and tbl.relname::text = any(v_expected_tables)
      and (not i.indisvalid or not i.indisready);
    if v_invalid_index_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % indexes are invalid/not-ready', v_invalid_index_count;
    end if;

    -- Generic tenant-isolation audit: whenever BOTH sides of a public FK have school_id,
    -- the FK must pair child.school_id with parent.school_id at the same key position.
    select count(*) into v_unsafe_fk_count
    from pg_constraint fk
    join pg_class child on child.oid = fk.conrelid
    join pg_namespace child_ns on child_ns.oid = child.relnamespace
    join pg_class parent on parent.oid = fk.confrelid
    join pg_namespace parent_ns on parent_ns.oid = parent.relnamespace
    where fk.contype = 'f'
      and child_ns.nspname = 'public'
      and parent_ns.nspname = 'public'
      and child.relname::text = any(v_expected_tables)
      and parent.relname::text = any(v_expected_tables)
      and exists (
          select 1 from pg_attribute a
          where a.attrelid = child.oid and a.attname = 'school_id' and not a.attisdropped
      )
      and exists (
          select 1 from pg_attribute a
          where a.attrelid = parent.oid and a.attname = 'school_id' and not a.attisdropped
      )
      and not exists (
          select 1
          from unnest(fk.conkey) with ordinality as ck(attnum, ord)
          join unnest(fk.confkey) with ordinality as pk(attnum, ord) using (ord)
          join pg_attribute ca on ca.attrelid = child.oid and ca.attnum = ck.attnum
          join pg_attribute pa on pa.attrelid = parent.oid and pa.attnum = pk.attnum
          where ca.attname = 'school_id' and pa.attname = 'school_id'
      );
    if v_unsafe_fk_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % tenant FKs can cross school boundaries', v_unsafe_fk_count;
    end if;

    -- No raw upload token or obvious provider-secret column may exist in the public contract.
    select count(*) into v_raw_token_count
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'upload_requests'
      and column_name = 'token';
    if v_raw_token_count <> 0 then
        raise exception 'S2-B5 acceptance failed: raw upload token column exists';
    end if;

    select count(*) into v_secret_column_count
    from information_schema.columns
    where table_schema = 'public'
      and table_name = any(v_expected_tables)
      and column_name ~* '(service_role|client_secret|refresh_token|access_token|oauth_token)';
    if v_secret_column_count <> 0 then
        raise exception 'S2-B5 acceptance failed: % secret-like public columns exist', v_secret_column_count;
    end if;

    select count(*) into v_function_count
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname = 'set_row_updated_at'
      and p.prorettype = 'trigger'::regtype
      and not p.prosecdef;
    if v_function_count <> 1 then
        raise exception 'S2-B5 acceptance failed: updated_at trigger helper is missing or unsafe';
    end if;

    select count(*) into v_function_grant_count
    from information_schema.routine_privileges
    where specific_schema = 'public'
      and routine_name = 'set_row_updated_at'
      and grantee in ('PUBLIC','anon','authenticated')
      and privilege_type = 'EXECUTE';
    if v_function_grant_count <> 0 then
        raise exception 'S2-B5 acceptance failed: trigger helper has % browser/PUBLIC EXECUTE grants', v_function_grant_count;
    end if;

    select count(*), count(distinct tbl.relname)
    into v_trigger_count, v_trigger_table_count
    from pg_trigger trg
    join pg_class tbl on tbl.oid = trg.tgrelid
    join pg_namespace ns on ns.oid = tbl.relnamespace
    join pg_proc fn on fn.oid = trg.tgfoid
    where ns.nspname = 'public'
      and tbl.relname::text = any(v_updated_tables)
      and not trg.tgisinternal
      and trg.tgenabled <> 'D'
      and fn.proname = 'set_row_updated_at';
    if v_trigger_count <> 22 or v_trigger_table_count <> 22 then
        raise exception 'S2-B5 acceptance failed: updated_at triggers count=% tables=% expected=22/22', v_trigger_count, v_trigger_table_count;
    end if;

    select count(*) into v_required_index_count
    from pg_indexes
    where schemaname = 'public'
      and indexname in (
          'idx_school_memberships_school_status_role',
          'idx_academic_years_school_start',
          'idx_teacher_cv_items_teacher_type'
      );
    if v_required_index_count <> 3 then
        raise exception 'S2-B5 acceptance failed: final hardening indexes found % of 3', v_required_index_count;
    end if;
end $$;

-- Functional proof that the database, not application code, advances updated_at.
do $$
declare
    v_school uuid;
    v_before timestamptz;
    v_after timestamptz;
begin
    insert into public.schools(name)
    values ('S2-B5 updated_at acceptance')
    returning id, updated_at into v_school, v_before;

    perform pg_sleep(0.02);

    update public.schools
    set name = 'S2-B5 updated_at acceptance updated'
    where id = v_school;

    select updated_at into v_after
    from public.schools
    where id = v_school;

    if v_after <= v_before then
        raise exception 'S2-B5 acceptance failed: updated_at did not advance (% -> %)', v_before, v_after;
    end if;
end $$;

select
    'PASS: S2-B5 final schema acceptance' as result,
    (
        select count(*)
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relname in (
              'schools','profiles','school_memberships','academic_years','school_settings',
              'teachers','teacher_profiles','teacher_years','teacher_cv_items',
              'upload_requests','documents','events','event_media','event_teacher_links','activities',
              'meetings','meeting_attendees','meeting_decisions','curriculum_plans','curriculum_units',
              'supervision_visits','supervision_actions','achievement_assessments',
              'achievement_assessment_standards','achievement_actions','achievement_action_metrics'
          )
          and c.relrowsecurity
    ) as rls_enabled_tables_before_s2_c;

rollback;
