-- Marsad S3-C3B live acceptance. Safe fixture: every data mutation is rolled back.
begin;

do $$
declare
    v_count integer;
    v_public boolean;
    v_limit bigint;
begin
    select public, file_size_limit into v_public, v_limit
      from storage.buckets where id='marsad-documents';
    if not found or v_public or v_limit <> 26214400 then
        raise exception 'S3-C3B acceptance failed: private 25MB bucket contract missing';
    end if;

    select count(*) into v_count from pg_policies
     where schemaname='storage' and tablename='objects'
       and policyname='marsad_documents_manager_select'
       and cmd='SELECT';
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: manager Storage SELECT policy missing';
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.marsad_create_upload_request_v1(uuid,bigint,bigint,text,text,text,text,date,text,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3B acceptance failed: manager request creation RPC grant missing';
    end if;
    if has_function_privilege(
        'anon',
        'public.marsad_create_upload_request_v1(uuid,bigint,bigint,text,text,text,text,date,text,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3B acceptance failed: anon received request creation RPC';
    end if;
    if has_function_privilege(
        'authenticated',
        'public.marsad_register_public_upload_v1(bigint,text,text,text,bigint,text,text)',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.marsad_register_public_upload_v1(bigint,text,text,text,bigint,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3B acceptance failed: public registration RPC exposed to browser roles';
    end if;
    if not has_function_privilege(
        'service_role',
        'public.marsad_register_public_upload_v1(bigint,text,text,text,bigint,text,text)',
        'EXECUTE'
    ) then
        raise exception 'S3-C3B acceptance failed: server registration RPC grant missing';
    end if;

    select count(*) into v_count
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public' and p.proname='marsad_create_upload_request_v1' and p.prosecdef;
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: request creation RPC must be SECURITY DEFINER';
    end if;
    select count(*) into v_count
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public' and p.proname='marsad_register_public_upload_v1' and not p.prosecdef;
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: registration RPC must be SECURITY INVOKER';
    end if;
end $$;

select set_config(
    'marsad.s3c3b_user_id',
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
    if nullif(current_setting('marsad.s3c3b_user_id', true),'') is null then
        raise exception 'S3-C3B acceptance prerequisite: no active owner membership exists';
    end if;
end $$;

do $$
declare
    v_uid uuid := current_setting('marsad.s3c3b_user_id')::uuid;
    s_owner uuid; y_owner bigint; t_owner bigint;
begin
    insert into public.schools(name) values ('S3-C3B Owner Fixture') returning id into s_owner;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_owner,'2096/2097',2096,2097,true) returning id into y_owner;
    insert into public.school_memberships(school_id,user_id,role,status)
    values(s_owner,v_uid,'owner','active');
    insert into public.teachers(school_id,name,is_active)
    values(s_owner,'S3-C3B Upload Teacher',true) returning id into t_owner;
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,is_active)
    values(s_owner,y_owner,t_owner,'الفيزياء',10,18,true);
    perform set_config('marsad.s3c3b_school',s_owner::text,true);
    perform set_config('marsad.s3c3b_year',y_owner::text,true);
    perform set_config('marsad.s3c3b_teacher',t_owner::text,true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.s3c3b_user_id'), true);
select set_config('request.jwt.claims', json_build_object('sub',current_setting('marsad.s3c3b_user_id'),'role','authenticated')::text, true);
set local role authenticated;

do $$
declare
    v_school uuid := current_setting('marsad.s3c3b_school')::uuid;
    v_year bigint := current_setting('marsad.s3c3b_year')::bigint;
    v_teacher bigint := current_setting('marsad.s3c3b_teacher')::bigint;
    v_request bigint;
    v_expiry timestamptz;
    v_count integer;
begin
    select id, expires_at into v_request, v_expiry
      from public.marsad_create_upload_request_v1(
        v_school,v_year,v_teacher,'اختبار','الفيزياء','العاشر','S3-C3B Live Request',
        date '2096-09-30','قبول حي','PDF / Word / Excel',repeat('a',64)
      );
    if v_request is null or v_expiry <= now() then
        raise exception 'S3-C3B acceptance failed: request creation returned invalid values';
    end if;
    select count(*) into v_count from public.upload_requests
     where id=v_request and school_id=v_school and academic_year_id=v_year
       and token_hash=repeat('a',64) and status='waiting_upload';
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: request/token hash did not persist';
    end if;
    select count(*) into v_count from public.activities
     where school_id=v_school and academic_year_id=v_year
       and entity_type='request' and entity_id=v_request;
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: request creation activity missing';
    end if;
    perform set_config('marsad.s3c3b_request',v_request::text,true);
end $$;

reset role;
set local role service_role;

do $$
declare
    v_school uuid := current_setting('marsad.s3c3b_school')::uuid;
    v_year bigint := current_setting('marsad.s3c3b_year')::bigint;
    v_request bigint := current_setting('marsad.s3c3b_request')::bigint;
    v_path text := v_school::text || '/' || v_year::text || '/' || v_request::text || '/acceptance.pdf';
    v_document bigint;
    v_count integer;
begin
    v_document := public.marsad_register_public_upload_v1(
        v_request,repeat('a',64),'acceptance.pdf','application/pdf',1024,'marsad-documents',v_path
    );
    select count(*) into v_count from public.documents
     where id=v_document and request_id=v_request and storage_provider='supabase'
       and storage_bucket='marsad-documents' and storage_path=v_path and status='inbox';
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: document metadata registration missing';
    end if;
    select count(*) into v_count from public.upload_requests where id=v_request and status='review';
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: request did not transition to review';
    end if;
    select count(*) into v_count from public.activities
     where school_id=v_school and academic_year_id=v_year
       and entity_type='document' and entity_id=v_document;
    if v_count <> 1 then
        raise exception 'S3-C3B acceptance failed: public upload activity missing';
    end if;
end $$;

reset role;
select 'PASS: S3-C3B public intake and private Storage acceptance' as result;
rollback;
