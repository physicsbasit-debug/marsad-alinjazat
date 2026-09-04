-- Marsad Al-Injazat — S3-B2 live acceptance
-- Prerequisite: S3-A and S3-B1 are LIVE GREEN and S3-B2 migration is applied.
-- Uses one existing active owner account, creates only transactional fixtures, and ROLLBACKs all changes.

begin;

-- Structural verification before role simulation.
do $$
declare
    v_count integer;
begin
    if not exists (
        select 1
          from pg_policies
         where schemaname='public'
           and tablename='teacher_years'
           and policyname='teacher_years_insert_managers'
           and cmd='INSERT'
    ) then
        raise exception 'S3-B2 acceptance failed: teacher_years INSERT policy missing';
    end if;

    if not exists (
        select 1
          from pg_policies
         where schemaname='public'
           and tablename='teacher_years'
           and policyname='teacher_years_update_managers'
           and cmd='UPDATE'
    ) then
        raise exception 'S3-B2 acceptance failed: teacher_years UPDATE policy missing';
    end if;

    if exists (
        select 1
          from information_schema.role_table_grants
         where table_schema='public'
           and grantee='authenticated'
           and table_name in ('teachers','teacher_years')
           and privilege_type='DELETE'
    ) then
        raise exception 'S3-B2 acceptance failed: root teacher delete was granted';
    end if;

    select count(*) into v_count
      from information_schema.column_privileges
     where table_schema='public'
       and table_name='teacher_years'
       and grantee='authenticated'
       and privilege_type='INSERT'
       and column_name in (
           'school_id','academic_year_id','teacher_id','subject','experience_years',
           'workload','grades','responsibilities'
       );
    if v_count <> 8 then
        raise exception 'S3-B2 acceptance failed: expected 8 teacher_years INSERT column grants, got %', v_count;
    end if;

    select count(*) into v_count
      from information_schema.column_privileges
     where table_schema='public'
       and table_name='teacher_years'
       and grantee='authenticated'
       and privilege_type='UPDATE'
       and column_name in ('subject','experience_years','workload','grades','responsibilities');
    if v_count <> 5 then
        raise exception 'S3-B2 acceptance failed: expected 5 teacher_years UPDATE column grants, got %', v_count;
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-B2 acceptance failed: create RPC EXECUTE missing';
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.marsad_update_teacher_v1(uuid,bigint,bigint,text,text,text,text,integer,integer,text,text,text,integer,text,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-B2 acceptance failed: update RPC EXECUTE missing';
    end if;

    if has_function_privilege(
        'anon',
        'public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_update_teacher_v1(uuid,bigint,bigint,text,text,text,text,integer,integer,text,text,text,integer,text,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-B2 acceptance failed: anon received teacher write RPC access';
    end if;

    if exists (
        select 1
          from pg_proc p
          join pg_namespace n on n.oid=p.pronamespace
         where n.nspname='public'
           and p.proname in ('marsad_create_teacher_v1','marsad_update_teacher_v1')
           and p.prosecdef
    ) then
        raise exception 'S3-B2 acceptance failed: teacher write RPC must remain SECURITY INVOKER';
    end if;

    if position(
        'on conflict on constraint teacher_years_pkey do nothing'
        in lower(pg_get_functiondef('public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)'::regprocedure))
    ) = 0 then
        raise exception 'S3-B2R1 acceptance failed: create RPC still uses an ambiguous conflict target';
    end if;

    if position(
        'on conflict (school_id, academic_year_id, teacher_id)'
        in lower(pg_get_functiondef('public.marsad_create_teacher_v1(uuid,bigint,text,text,text,text,integer,integer,text,text)'::regprocedure))
    ) > 0 then
        raise exception 'S3-B2R1 acceptance failed: ambiguous teacher_id conflict target remains';
    end if;
end $$;

-- Resolve one real owner account already provisioned by S2-E2. No auth mutation.
select set_config(
    'marsad.s3b2_user_id',
    coalesce((
        select sm.user_id::text
          from public.school_memberships sm
          join public.schools s on s.id=sm.school_id and s.is_active
         where sm.role='owner' and sm.status='active'
         order by sm.created_at desc
         limit 1
    ), ''),
    true
);

do $$
begin
    if nullif(current_setting('marsad.s3b2_user_id', true),'') is null then
        raise exception 'S3-B2 acceptance prerequisite: no active owner membership exists';
    end if;
    if not exists (
        select 1 from public.profiles where id=current_setting('marsad.s3b2_user_id')::uuid
    ) then
        raise exception 'S3-B2 acceptance prerequisite: owner has no public profile';
    end if;
end $$;

-- Create three isolated tenancy fixtures as database owner. They all roll back.
do $$
declare
    v_uid uuid := current_setting('marsad.s3b2_user_id')::uuid;
    s_owner uuid;
    s_lead uuid;
    s_out uuid;
    y_owner bigint;
    y_lead bigint;
    y_out bigint;
    t_out bigint;
begin
    insert into public.schools(name) values ('S3-B2 Owner Fixture') returning id into s_owner;
    insert into public.schools(name) values ('S3-B2 Lead Fixture') returning id into s_lead;
    insert into public.schools(name) values ('S3-B2 Outsider Fixture') returning id into s_out;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_owner,'2094/2095',2094,2095,true) returning id into y_owner;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_lead,'2094/2095',2094,2095,true) returning id into y_lead;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_out,'2094/2095',2094,2095,true) returning id into y_out;

    insert into public.school_memberships(school_id,user_id,role,status)
    values(s_owner,v_uid,'owner','active');
    insert into public.school_memberships(school_id,user_id,role,status)
    values(s_lead,v_uid,'lead_teacher','active');

    insert into public.teachers(school_id,name,is_active)
    values(s_out,'S3-B2 Outsider Existing Teacher',true)
    returning id into t_out;

    perform set_config('marsad.s3b2_owner_school',s_owner::text,true);
    perform set_config('marsad.s3b2_lead_school',s_lead::text,true);
    perform set_config('marsad.s3b2_out_school',s_out::text,true);
    perform set_config('marsad.s3b2_owner_year',y_owner::text,true);
    perform set_config('marsad.s3b2_lead_year',y_lead::text,true);
    perform set_config('marsad.s3b2_out_year',y_out::text,true);
    perform set_config('marsad.s3b2_out_teacher',t_out::text,true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.s3b2_user_id'), true);
select set_config(
    'request.jwt.claims',
    json_build_object('sub',current_setting('marsad.s3b2_user_id'),'role','authenticated')::text,
    true
);
set local role authenticated;

do $$
declare
    s_owner uuid := current_setting('marsad.s3b2_owner_school')::uuid;
    s_lead uuid := current_setting('marsad.s3b2_lead_school')::uuid;
    s_out uuid := current_setting('marsad.s3b2_out_school')::uuid;
    y_owner bigint := current_setting('marsad.s3b2_owner_year')::bigint;
    y_lead bigint := current_setting('marsad.s3b2_lead_year')::bigint;
    y_out bigint := current_setting('marsad.s3b2_out_year')::bigint;
    t_out bigint := current_setting('marsad.s3b2_out_teacher')::bigint;
    t_owner bigint;
    t_second bigint;
    linked boolean;
    v_count integer;
    v_rows integer;
    v_blocked boolean;
begin
    -- Owner create is atomic: identity + annual row.
    select teacher_id, linked_existing
      into t_owner, linked
      from public.marsad_create_teacher_v1(
          s_owner, y_owner,
          'S3-B2 Acceptance Teacher', 'الفيزياء', 'فيزياء', 'بكالوريوس تربية',
          11, 18, 's3b2.teacher@example.invalid', '90000000'
      );
    if linked then
        raise exception 'S3-B2 acceptance failed: first create unexpectedly linked existing identity';
    end if;

    select count(*) into v_count
      from public.teachers
     where school_id=s_owner and id=t_owner and name='S3-B2 Acceptance Teacher';
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: owner teacher identity was not created';
    end if;

    select count(*) into v_count
      from public.teacher_years
     where school_id=s_owner and academic_year_id=y_owner and teacher_id=t_owner
       and subject='الفيزياء' and experience_years=11 and workload=18 and is_active;
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: owner teacher_year row was not created';
    end if;

    -- Repeating the same email must link the same identity, not duplicate it.
    select teacher_id, linked_existing
      into t_second, linked
      from public.marsad_create_teacher_v1(
          s_owner, y_owner,
          'Different Display Name Should Not Duplicate', 'الفيزياء', null, null,
          1, 1, 'S3B2.TEACHER@example.invalid', null
      );
    if not linked or t_second <> t_owner then
        raise exception 'S3-B2 acceptance failed: create did not link existing identity by email';
    end if;
    select count(*) into v_count
      from public.teachers
     where school_id=s_owner and lower(email)='s3b2.teacher@example.invalid';
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: duplicate teacher identity was created';
    end if;

    -- Owner update atomically covers teachers + teacher_years + teacher_profiles.
    perform public.marsad_update_teacher_v1(
        s_owner, y_owner, t_owner,
        'S3-B2 Acceptance Teacher Updated', 'العلوم', 'علوم عامة', 'ماجستير تربية',
        12, 20, 's3b2.teacher@example.invalid', '91111111',
        'S3B2-EMP-1', 2024, '9، 10', 'منسق مختبر', 'ملف قبول S3-B2'
    );

    select count(*) into v_count
      from public.teachers
     where school_id=s_owner and id=t_owner
       and name='S3-B2 Acceptance Teacher Updated'
       and specialization='علوم عامة'
       and qualification='ماجستير تربية'
       and phone='91111111';
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: teachers UPDATE did not persist';
    end if;

    select count(*) into v_count
      from public.teacher_years
     where school_id=s_owner and academic_year_id=y_owner and teacher_id=t_owner
       and subject='العلوم' and experience_years=12 and workload=20
       and grades='9، 10' and responsibilities='منسق مختبر' and is_active;
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: teacher_years UPDATE did not persist';
    end if;

    select count(*) into v_count
      from public.teacher_profiles
     where school_id=s_owner and teacher_id=t_owner
       and employee_number='S3B2-EMP-1'
       and school_join_year=2024
       and professional_summary='ملف قبول S3-B2';
    if v_count <> 1 then
        raise exception 'S3-B2 acceptance failed: teacher profile UPSERT did not persist';
    end if;

    -- Cross-tenant create must fail through SECURITY INVOKER + RLS/role check.
    v_blocked := false;
    begin
        select teacher_id into t_second
          from public.marsad_create_teacher_v1(
              s_out, y_out, 'SHOULD NOT CREATE', 'الفيزياء', null, null, 1, 1, null, null
          );
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-B2 acceptance failed: cross-tenant teacher create unexpectedly succeeded';
    end if;

    -- lead_teacher remains read-only for school-wide teacher writes.
    v_blocked := false;
    begin
        select teacher_id into t_second
          from public.marsad_create_teacher_v1(
              s_lead, y_lead, 'SHOULD NOT CREATE LEAD', 'الفيزياء', null, null, 1, 1, null, null
          );
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-B2 acceptance failed: lead_teacher create unexpectedly succeeded';
    end if;

    -- Direct cross-tenant annual write must also be rejected by teacher_years RLS.
    v_blocked := false;
    begin
        insert into public.teacher_years(
            school_id,academic_year_id,teacher_id,subject,experience_years,workload
        ) values(s_out,y_out,t_out,'SHOULD NOT INSERT',1,1);
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-B2 acceptance failed: cross-tenant teacher_years INSERT unexpectedly succeeded';
    end if;

    -- Root destructive delete is still outside the staged teacher surface.
    v_blocked := false;
    begin
        delete from public.teachers where school_id=s_owner and id=t_owner;
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-B2 acceptance failed: root teacher DELETE unexpectedly succeeded';
    end if;

    v_blocked := false;
    begin
        delete from public.teacher_years where school_id=s_owner and teacher_id=t_owner;
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-B2 acceptance failed: teacher_years DELETE unexpectedly succeeded';
    end if;

    -- lead_teacher UPDATE must affect zero rows through RLS.
    update public.teachers set name='SHOULD NOT UPDATE'
     where school_id=s_lead;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then
        raise exception 'S3-B2 acceptance failed: lead_teacher updated teacher rows';
    end if;
end $$;

reset role;
select 'PASS: S3-B2R1 teacher write ambiguity correction' as result;
rollback;
