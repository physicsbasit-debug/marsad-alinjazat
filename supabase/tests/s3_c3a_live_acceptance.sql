-- Marsad Al-Injazat — S3-C3A live acceptance
-- Prerequisite: S3-C2 is LIVE GREEN and the S3-C3A migration is applied.
-- Uses one existing active owner account, creates transactional fixtures, then ROLLBACKs everything.

begin;

do $$
declare
    v_count integer;
begin
    if not exists (
        select 1 from pg_policies
         where schemaname='public' and tablename='upload_requests'
           and policyname='upload_requests_update_managers' and cmd='UPDATE'
    ) then
        raise exception 'S3-C3A acceptance failed: upload_requests UPDATE policy missing';
    end if;
    if not exists (
        select 1 from pg_policies
         where schemaname='public' and tablename='documents'
           and policyname='documents_update_managers' and cmd='UPDATE'
    ) then
        raise exception 'S3-C3A acceptance failed: documents UPDATE policy missing';
    end if;
    if not has_column_privilege('authenticated','public.upload_requests','status','UPDATE') then
        raise exception 'S3-C3A acceptance failed: upload request status UPDATE grant missing';
    end if;
    if not has_column_privilege('authenticated','public.documents','status','UPDATE')
       or not has_column_privilege('authenticated','public.documents','approved_at','UPDATE') then
        raise exception 'S3-C3A acceptance failed: document review UPDATE grants missing';
    end if;
    if has_table_privilege('authenticated','public.upload_requests','INSERT') then
        raise exception 'S3-C3A acceptance failed: request INSERT must remain unavailable';
    end if;
    if has_table_privilege('authenticated','public.documents','INSERT') then
        raise exception 'S3-C3A acceptance failed: document INSERT must remain unavailable';
    end if;
    if not has_function_privilege(
        'authenticated',
        'public.marsad_update_upload_request_status_v1(uuid,bigint,bigint,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3A acceptance failed: request review RPC grant missing';
    end if;
    if has_function_privilege(
        'anon',
        'public.marsad_update_upload_request_status_v1(uuid,bigint,bigint,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3A acceptance failed: anon received request review RPC access';
    end if;
    select count(*) into v_count
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public' and p.proname='marsad_update_upload_request_status_v1' and p.prosecdef;
    if v_count <> 0 then
        raise exception 'S3-C3A acceptance failed: request review RPC must remain SECURITY INVOKER';
    end if;
end $$;

select set_config(
    'marsad.s3c3a_user_id',
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
    if nullif(current_setting('marsad.s3c3a_user_id', true),'') is null then
        raise exception 'S3-C3A acceptance prerequisite: no active owner membership exists';
    end if;
end $$;

do $$
declare
    v_uid uuid := current_setting('marsad.s3c3a_user_id')::uuid;
    s_owner uuid; s_lead uuid; s_out uuid;
    y_owner bigint; y_lead bigint; y_out bigint;
    t_owner bigint; t_lead bigint; t_out bigint;
    r_owner bigint; r_lead bigint; r_out bigint;
    d_owner bigint;
begin
    insert into public.schools(name) values ('S3-C3A Owner Fixture') returning id into s_owner;
    insert into public.schools(name) values ('S3-C3A Lead Fixture') returning id into s_lead;
    insert into public.schools(name) values ('S3-C3A Outsider Fixture') returning id into s_out;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_owner,'2094/2095',2094,2095,true) returning id into y_owner;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_lead,'2094/2095',2094,2095,true) returning id into y_lead;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_out,'2094/2095',2094,2095,true) returning id into y_out;

    insert into public.school_memberships(school_id,user_id,role,status) values(s_owner,v_uid,'owner','active');
    insert into public.school_memberships(school_id,user_id,role,status) values(s_lead,v_uid,'lead_teacher','active');

    insert into public.teachers(school_id,name,is_active) values(s_owner,'S3-C3A Owner Teacher',true) returning id into t_owner;
    insert into public.teachers(school_id,name,is_active) values(s_lead,'S3-C3A Lead Teacher',true) returning id into t_lead;
    insert into public.teachers(school_id,name,is_active) values(s_out,'S3-C3A Outsider Teacher',true) returning id into t_out;

    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_owner,y_owner,t_owner,'الفيزياء',10,18,true);
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_lead,y_lead,t_lead,'الفيزياء',10,18,true);
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_out,y_out,t_out,'الفيزياء',10,18,true);

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        deadline,notes,allowed_files,token_hash,status,expires_at
    ) values(
        s_owner,y_owner,t_owner,'اختبار','الفيزياء','العاشر','S3-C3A Owner Request',
        date '2094-09-30','قبول حي','PDF فقط','s3c3a-owner-token-hash','review',timestamptz '2095-01-01 00:00:00+00'
    ) returning id into r_owner;

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        allowed_files,token_hash,status,expires_at
    ) values(s_lead,y_lead,t_lead,'اختبار','الفيزياء','العاشر','S3-C3A Lead Request','PDF فقط','s3c3a-lead-token-hash','review',timestamptz '2095-01-01 00:00:00+00') returning id into r_lead;

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        allowed_files,token_hash,status,expires_at
    ) values(s_out,y_out,t_out,'اختبار','الفيزياء','العاشر','S3-C3A Outsider Request','PDF فقط','s3c3a-out-token-hash','review',timestamptz '2095-01-01 00:00:00+00') returning id into r_out;

    insert into public.documents(
        school_id,academic_year_id,request_id,teacher_id,title,category,subject,grade,
        original_name,mime_type,size_bytes,storage_provider,storage_path,status
    ) values(
        s_owner,y_owner,r_owner,t_owner,'S3-C3A Document','اختبار','الفيزياء','العاشر',
        'acceptance.pdf','application/pdf',100,'legacy_local','acceptance/s3c3a.pdf','inbox'
    ) returning id into d_owner;

    perform set_config('marsad.s3c3a_owner_school',s_owner::text,true);
    perform set_config('marsad.s3c3a_lead_school',s_lead::text,true);
    perform set_config('marsad.s3c3a_out_school',s_out::text,true);
    perform set_config('marsad.s3c3a_owner_year',y_owner::text,true);
    perform set_config('marsad.s3c3a_lead_year',y_lead::text,true);
    perform set_config('marsad.s3c3a_out_year',y_out::text,true);
    perform set_config('marsad.s3c3a_owner_request',r_owner::text,true);
    perform set_config('marsad.s3c3a_lead_request',r_lead::text,true);
    perform set_config('marsad.s3c3a_out_request',r_out::text,true);
    perform set_config('marsad.s3c3a_owner_document',d_owner::text,true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.s3c3a_user_id'), true);
select set_config('request.jwt.claims', json_build_object('sub',current_setting('marsad.s3c3a_user_id'),'role','authenticated')::text, true);
set local role authenticated;

do $$
declare
    s_owner uuid := current_setting('marsad.s3c3a_owner_school')::uuid;
    s_lead uuid := current_setting('marsad.s3c3a_lead_school')::uuid;
    s_out uuid := current_setting('marsad.s3c3a_out_school')::uuid;
    y_owner bigint := current_setting('marsad.s3c3a_owner_year')::bigint;
    y_lead bigint := current_setting('marsad.s3c3a_lead_year')::bigint;
    y_out bigint := current_setting('marsad.s3c3a_out_year')::bigint;
    r_owner bigint := current_setting('marsad.s3c3a_owner_request')::bigint;
    r_lead bigint := current_setting('marsad.s3c3a_lead_request')::bigint;
    r_out bigint := current_setting('marsad.s3c3a_out_request')::bigint;
    d_owner bigint := current_setting('marsad.s3c3a_owner_document')::bigint;
    v_count integer;
    v_rows integer;
    v_blocked boolean;
begin
    perform public.marsad_update_upload_request_status_v1(s_owner,y_owner,r_owner,'approved');

    select count(*) into v_count from public.upload_requests
     where school_id=s_owner and academic_year_id=y_owner and id=r_owner and status='approved';
    if v_count <> 1 then
        raise exception 'S3-C3A acceptance failed: owner request approval did not persist';
    end if;

    select count(*) into v_count from public.documents
     where school_id=s_owner and academic_year_id=y_owner and id=d_owner
       and status='approved' and approved_at is not null;
    if v_count <> 1 then
        raise exception 'S3-C3A acceptance failed: approving request did not approve its document metadata';
    end if;

    select count(*) into v_count from public.activities
     where school_id=s_owner and academic_year_id=y_owner
       and entity_type='request' and entity_id=r_owner
       and activity_type='request' and actor_user_id=current_setting('marsad.s3c3a_user_id')::uuid;
    if v_count <> 1 then
        raise exception 'S3-C3A acceptance failed: request review activity missing';
    end if;

    v_blocked := false;
    begin
        perform public.marsad_update_upload_request_status_v1(s_lead,y_lead,r_lead,'approved');
    exception when insufficient_privilege then v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-C3A acceptance failed: lead_teacher review unexpectedly succeeded';
    end if;

    v_blocked := false;
    begin
        perform public.marsad_update_upload_request_status_v1(s_out,y_out,r_out,'approved');
    exception when insufficient_privilege then v_blocked := true;
    end;
    if not v_blocked then
        raise exception 'S3-C3A acceptance failed: cross-tenant review unexpectedly succeeded';
    end if;

    update public.upload_requests set status='approved' where school_id=s_lead and id=r_lead;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then
        raise exception 'S3-C3A acceptance failed: lead_teacher directly updated request rows';
    end if;
end $$;

reset role;
select 'PASS: S3-C3A requests/documents review RLS acceptance' as result;
rollback;
