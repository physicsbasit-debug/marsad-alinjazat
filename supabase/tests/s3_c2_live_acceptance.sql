-- Marsad Al-Injazat — S3-C2 live acceptance
-- Prerequisite: S3-C1 is LIVE GREEN and the S3-C2 migration is applied.
-- Uses one existing active owner account, creates only transactional fixtures, and ROLLBACKs all changes.

begin;

-- Structural verification before role simulation.
do $$
declare
    v_count integer;
    v_names text[] := array[
        'marsad_create_supervision_visit_v1',
        'marsad_update_supervision_visit_v1',
        'marsad_create_supervision_action_v1',
        'marsad_update_supervision_action_v1',
        'marsad_delete_supervision_action_v1'
    ];
begin
    if not exists (
        select 1 from pg_policies
         where schemaname='public' and tablename='activities'
           and policyname='activities_insert_managers' and cmd='INSERT'
    ) then
        raise exception 'S3-C2 acceptance failed: activities INSERT policy missing';
    end if;

    if not has_sequence_privilege('authenticated','public.activities_id_seq','USAGE') then
        raise exception 'S3-C2 acceptance failed: activities sequence USAGE missing';
    end if;

    select count(*) into v_count
      from information_schema.column_privileges
     where table_schema='public' and table_name='activities'
       and grantee='authenticated' and privilege_type='INSERT'
       and column_name in (
           'school_id','academic_year_id','actor_user_id','activity_type',
           'title','detail','entity_type','entity_id'
       );
    if v_count <> 8 then
        raise exception 'S3-C2 acceptance failed: expected 8 activities INSERT column grants, got %', v_count;
    end if;

    if has_table_privilege('authenticated','public.supervision_visits','DELETE') then
        raise exception 'S3-C2 acceptance failed: supervision visit DELETE must remain unavailable';
    end if;

    if not has_table_privilege('authenticated','public.supervision_actions','DELETE') then
        raise exception 'S3-C2 acceptance failed: supervision action DELETE grant is missing';
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.marsad_create_supervision_visit_v1(uuid,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text)',
        'EXECUTE'
    ) or not has_function_privilege(
        'authenticated',
        'public.marsad_update_supervision_visit_v1(uuid,bigint,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text)',
        'EXECUTE'
    ) or not has_function_privilege(
        'authenticated',
        'public.marsad_create_supervision_action_v1(uuid,bigint,text,bigint,date,text,text)',
        'EXECUTE'
    ) or not has_function_privilege(
        'authenticated',
        'public.marsad_update_supervision_action_v1(uuid,bigint,bigint,text,bigint,date,text,text)',
        'EXECUTE'
    ) or not has_function_privilege(
        'authenticated',
        'public.marsad_delete_supervision_action_v1(uuid,bigint,bigint)',
        'EXECUTE'
    ) then
        raise exception 'S3-C2 acceptance failed: one or more supervision RPC EXECUTE grants are missing';
    end if;

    if has_function_privilege(
        'anon',
        'public.marsad_create_supervision_visit_v1(uuid,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_update_supervision_visit_v1(uuid,bigint,bigint,bigint,text,date,text,text,text,text,text,text,text,date,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_create_supervision_action_v1(uuid,bigint,text,bigint,date,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_update_supervision_action_v1(uuid,bigint,bigint,text,bigint,date,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_delete_supervision_action_v1(uuid,bigint,bigint)',
        'EXECUTE'
    ) then
        raise exception 'S3-C2 acceptance failed: anon received supervision RPC access';
    end if;

    select count(*) into v_count
      from pg_proc p
      join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public'
       and p.proname = any(v_names)
       and p.prosecdef;
    if v_count <> 0 then
        raise exception 'S3-C2 acceptance failed: supervision RPCs must remain SECURITY INVOKER';
    end if;

    select count(*) into v_count
      from pg_proc p
      join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public' and p.proname = any(v_names);
    if v_count <> 5 then
        raise exception 'S3-C2 acceptance failed: expected 5 supervision RPCs, got %', v_count;
    end if;
end $$;

-- Resolve one real owner account already provisioned by S2-E2. No auth mutation.
select set_config(
    'marsad.s3c2_user_id',
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
    if nullif(current_setting('marsad.s3c2_user_id', true),'') is null then
        raise exception 'S3-C2 acceptance prerequisite: no active owner membership exists';
    end if;
    if not exists (
        select 1 from public.profiles where id=current_setting('marsad.s3c2_user_id')::uuid
    ) then
        raise exception 'S3-C2 acceptance prerequisite: owner has no public profile';
    end if;
end $$;

-- Isolated owner, lead-teacher, and outsider tenants. Everything rolls back.
do $$
declare
    v_uid uuid := current_setting('marsad.s3c2_user_id')::uuid;
    s_owner uuid;
    s_lead uuid;
    s_out uuid;
    y_owner bigint;
    y_lead bigint;
    y_out bigint;
    t_owner bigint;
    t_lead bigint;
    t_out bigint;
begin
    insert into public.schools(name) values ('S3-C2 Owner Fixture') returning id into s_owner;
    insert into public.schools(name) values ('S3-C2 Lead Fixture') returning id into s_lead;
    insert into public.schools(name) values ('S3-C2 Outsider Fixture') returning id into s_out;

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
    values(s_owner,'S3-C2 Owner Teacher',true) returning id into t_owner;
    insert into public.teachers(school_id,name,is_active)
    values(s_lead,'S3-C2 Lead Teacher',true) returning id into t_lead;
    insert into public.teachers(school_id,name,is_active)
    values(s_out,'S3-C2 Outsider Teacher',true) returning id into t_out;

    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_owner,y_owner,t_owner,'الفيزياء',10,18,true);
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_lead,y_lead,t_lead,'الفيزياء',10,18,true);
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_out,y_out,t_out,'الفيزياء',10,18,true);

    perform set_config('marsad.s3c2_owner_school',s_owner::text,true);
    perform set_config('marsad.s3c2_lead_school',s_lead::text,true);
    perform set_config('marsad.s3c2_out_school',s_out::text,true);
    perform set_config('marsad.s3c2_owner_year',y_owner::text,true);
    perform set_config('marsad.s3c2_lead_year',y_lead::text,true);
    perform set_config('marsad.s3c2_out_year',y_out::text,true);
    perform set_config('marsad.s3c2_owner_teacher',t_owner::text,true);
    perform set_config('marsad.s3c2_lead_teacher',t_lead::text,true);
    perform set_config('marsad.s3c2_out_teacher',t_out::text,true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.s3c2_user_id'), true);
select set_config(
    'request.jwt.claims',
    json_build_object('sub',current_setting('marsad.s3c2_user_id'),'role','authenticated')::text,
    true
);
set local role authenticated;

do $$
declare
    s_owner uuid := current_setting('marsad.s3c2_owner_school')::uuid;
    s_lead uuid := current_setting('marsad.s3c2_lead_school')::uuid;
    s_out uuid := current_setting('marsad.s3c2_out_school')::uuid;
    y_owner bigint := current_setting('marsad.s3c2_owner_year')::bigint;
    y_lead bigint := current_setting('marsad.s3c2_lead_year')::bigint;
    y_out bigint := current_setting('marsad.s3c2_out_year')::bigint;
    t_owner bigint := current_setting('marsad.s3c2_owner_teacher')::bigint;
    t_lead bigint := current_setting('marsad.s3c2_lead_teacher')::bigint;
    t_out bigint := current_setting('marsad.s3c2_out_teacher')::bigint;
    v_visit bigint;
    v_action bigint;
    v_count integer;
    v_rows integer;
    v_blocked boolean;
begin
    -- Owner can create a current-year visit and the activity row is atomic.
    v_visit := public.marsad_create_supervision_visit_v1(
        s_owner, y_owner, t_owner, 'زيارة صفية', date '2094-09-10',
        'الحصة الثالثة', 'العاشر', 'الحركة', 'متابعة بناء المفهوم',
        'تفاعل جيد', 'تفعيل التحقق من الفهم', 'توصية قابلة للمتابعة',
        date '2094-09-20', 'متابعة لاحقة', 'planned'
    );

    select count(*) into v_count
      from public.supervision_visits
     where school_id=s_owner and academic_year_id=y_owner and id=v_visit
       and teacher_id=t_owner and status='planned' and closed_at is null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: owner visit create did not persist';
    end if;

    select count(*) into v_count
      from public.activities
     where school_id=s_owner and academic_year_id=y_owner
       and entity_type='supervision_visit' and entity_id=v_visit
       and activity_type='supervision' and actor_user_id=current_setting('marsad.s3c2_user_id')::uuid;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: create visit activity was not written atomically';
    end if;

    -- Closing stamps closed_at; reopening clears it.
    perform public.marsad_update_supervision_visit_v1(
        s_owner, y_owner, v_visit, t_owner, 'زيارة متابعة', date '2094-09-10',
        'الحصة الرابعة', 'العاشر', 'الحركة بعد التحديث', 'متابعة الإجراء',
        'قوة محدثة', 'تطوير محدث', 'توصية محدثة', date '2094-09-21',
        'أغلقت مؤقتًا', 'closed'
    );
    select count(*) into v_count
      from public.supervision_visits
     where school_id=s_owner and id=v_visit and status='closed' and closed_at is not null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: closed_at was not stamped';
    end if;

    perform public.marsad_update_supervision_visit_v1(
        s_owner, y_owner, v_visit, t_owner, 'زيارة متابعة', date '2094-09-10',
        'الحصة الرابعة', 'العاشر', 'الحركة بعد التحديث', 'متابعة الإجراء',
        'قوة محدثة', 'تطوير محدث', 'توصية محدثة', date '2094-09-21',
        'أعيد فتحها', 'needs_followup'
    );
    select count(*) into v_count
      from public.supervision_visits
     where school_id=s_owner and id=v_visit and status='needs_followup' and closed_at is null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: reopening did not clear closed_at';
    end if;

    -- Action lifecycle preserves completed_at semantics and writes timeline events.
    v_action := public.marsad_create_supervision_action_v1(
        s_owner, v_visit, 'إجراء قبول S3-C2', t_owner, date '2094-09-25', 'new', 'اختبار الإجراء'
    );
    select count(*) into v_count
      from public.supervision_actions
     where school_id=s_owner and visit_id=v_visit and id=v_action
       and status='new' and completed_at is null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: action create did not persist';
    end if;

    perform public.marsad_update_supervision_action_v1(
        s_owner, v_visit, v_action, 'إجراء قبول S3-C2 مكتمل', t_owner,
        date '2094-09-25', 'completed', 'أغلق للاختبار'
    );
    select count(*) into v_count
      from public.supervision_actions
     where school_id=s_owner and id=v_action and status='completed' and completed_at is not null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: completed_at was not stamped';
    end if;

    perform public.marsad_update_supervision_action_v1(
        s_owner, v_visit, v_action, 'إجراء قبول S3-C2 أعيد فتحه', t_owner,
        date '2094-09-26', 'in_progress', 'أعيد فتح الإجراء'
    );
    select count(*) into v_count
      from public.supervision_actions
     where school_id=s_owner and id=v_action and status='in_progress' and completed_at is null;
    if v_count <> 1 then
        raise exception 'S3-C2 acceptance failed: reopening action did not clear completed_at';
    end if;

    perform public.marsad_delete_supervision_action_v1(s_owner, v_visit, v_action);
    select count(*) into v_count from public.supervision_actions where id=v_action;
    if v_count <> 0 then
        raise exception 'S3-C2 acceptance failed: action delete did not remove the row';
    end if;

    select count(*) into v_count
      from public.activities
     where school_id=s_owner and academic_year_id=y_owner
       and entity_type='supervision_visit' and entity_id=v_visit;
    if v_count < 6 then
        raise exception 'S3-C2 acceptance failed: expected visit/action timeline writes, got %', v_count;
    end if;

    -- lead_teacher remains read-only for the supervision write surface.
    v_blocked := false;
    begin
        perform public.marsad_create_supervision_visit_v1(
            s_lead, y_lead, t_lead, 'زيارة صفية', date '2094-09-12',
            null, null, null, null, null, null, null, null, null, 'planned'
        );
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-C2 acceptance failed: lead_teacher create unexpectedly succeeded';
    end if;

    -- Cross-tenant create is rejected even with a valid teacher in that other tenant.
    v_blocked := false;
    begin
        perform public.marsad_create_supervision_visit_v1(
            s_out, y_out, t_out, 'زيارة صفية', date '2094-09-12',
            null, null, null, null, null, null, null, null, null, 'planned'
        );
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-C2 acceptance failed: cross-tenant create unexpectedly succeeded';
    end if;

    -- Root visit deletion stays outside the staged surface.
    v_blocked := false;
    begin
        delete from public.supervision_visits where school_id=s_owner and id=v_visit;
    exception when insufficient_privilege then
        v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-C2 acceptance failed: visit DELETE unexpectedly succeeded';
    end if;

    -- Lead can read its tenant supervision rows but cannot mutate them directly.
    update public.supervision_visits set status='completed' where school_id=s_lead;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then
        raise exception 'S3-C2 acceptance failed: lead_teacher updated supervision rows';
    end if;
end $$;

reset role;
select 'PASS: S3-C2 supervision write RLS acceptance' as result;
rollback;
