-- S2-C2 live acceptance
-- Prerequisite: S2-C1 is LIVE GREEN and at least one real Supabase Auth user exists.
-- Uses the newest real Auth user, never mutates auth.users, and rolls back all public fixtures.

begin;

-- Structural security checks.
do $$
declare
    v_count integer;
    v_domain text[] := array[
        'teachers','teacher_profiles','teacher_years','teacher_cv_items','upload_requests','documents',
        'events','event_media','event_teacher_links','activities','meetings','meeting_attendees',
        'meeting_decisions','curriculum_plans','curriculum_units','supervision_visits','supervision_actions',
        'achievement_assessments','achievement_assessment_standards','achievement_actions','achievement_action_metrics'
    ];
    v_locked text[] := array['teacher_years','upload_requests','documents','event_media','activities'];
begin
    select count(*) into v_count
    from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname=any(v_domain) and c.relrowsecurity;
    if v_count <> 21 then
        raise exception 'S2-C2 acceptance failed: expected RLS on 21 domain tables, got %', v_count;
    end if;

    select count(*) into v_count from pg_policies
    where schemaname='public' and tablename=any(v_domain);
    if v_count <> 58 then
        raise exception 'S2-C2 acceptance failed: expected 58 S2-C2 domain policies, got %', v_count;
    end if;

    select count(*) into v_count from pg_policies
    where schemaname='public';
    if v_count <> 69 then
        raise exception 'S2-C2 acceptance failed: expected 69 total public policies after C1+C2, got %', v_count;
    end if;

    if exists (
        select 1 from information_schema.role_table_grants
        where table_schema='public' and grantee='anon'
    ) then
        raise exception 'S2-C2 acceptance failed: anon received public table grants';
    end if;

    select count(*) into v_count
    from information_schema.role_table_grants
    where table_schema='public' and grantee='authenticated'
      and privilege_type='SELECT';
    if v_count <> 26 then
        raise exception 'S2-C2 acceptance failed: authenticated SELECT grants expected 26 tables, got %', v_count;
    end if;

    if exists (
        select 1 from information_schema.role_table_grants
        where table_schema='public' and grantee='authenticated'
          and privilege_type in ('INSERT','UPDATE')
    ) then
        raise exception 'S2-C2 acceptance failed: broad authenticated INSERT/UPDATE table grant detected';
    end if;

    if exists (
        select 1 from information_schema.role_column_grants
        where table_schema='public' and grantee='authenticated'
          and table_name=any(v_locked)
          and privilege_type in ('INSERT','UPDATE','DELETE')
    ) or exists (
        select 1 from information_schema.role_table_grants
        where table_schema='public' and grantee='authenticated'
          and table_name=any(v_locked)
          and privilege_type in ('INSERT','UPDATE','DELETE')
    ) then
        raise exception 'S2-C2 acceptance failed: a locked table received browser write grants';
    end if;

    if not has_function_privilege('authenticated','private.can_access_teacher_record(uuid,bigint)','EXECUTE') then
        raise exception 'S2-C2 acceptance failed: private teacher-record helper EXECUTE missing';
    end if;

end $$;

select set_config(
    'marsad.test_user_id',
    coalesce((select id::text from auth.users order by created_at desc limit 1), ''),
    true
);

do $$
begin
    if nullif(current_setting('marsad.test_user_id', true),'') is null then
        raise exception 'S2-C2 acceptance prerequisite: keep one Auth user from S2-C1 or create a temporary Auth user';
    end if;
    if not exists (select 1 from public.profiles where id=current_setting('marsad.test_user_id')::uuid) then
        raise exception 'S2-C2 acceptance prerequisite: newest Auth user has no public profile; S2-C1 must be LIVE GREEN';
    end if;
end $$;

-- Seed five school contexts for one real Auth user: owner, teacher, viewer, lead_teacher, outsider.
do $$
declare
    v_uid uuid := current_setting('marsad.test_user_id')::uuid;
    s_owner uuid; s_teacher uuid; s_viewer uuid; s_lead uuid; s_out uuid;
    y_owner bigint; y_teacher bigint; y_viewer bigint; y_lead bigint; y_out bigint;
    t_owner bigint; t_self bigint; t_other bigint; t_view bigint; t_lead bigint;
    e_teacher bigint; e_viewer bigint; e_out bigint;
    r_teacher bigint;
begin
    insert into public.schools(name) values ('S2-C2 Owner School') returning id into s_owner;
    insert into public.schools(name) values ('S2-C2 Teacher School') returning id into s_teacher;
    insert into public.schools(name) values ('S2-C2 Viewer School') returning id into s_viewer;
    insert into public.schools(name) values ('S2-C2 Lead School') returning id into s_lead;
    insert into public.schools(name) values ('S2-C2 Outsider School') returning id into s_out;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current) values(s_owner,'2090/2091',2090,2091,true) returning id into y_owner;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current) values(s_teacher,'2090/2091',2090,2091,true) returning id into y_teacher;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current) values(s_viewer,'2090/2091',2090,2091,true) returning id into y_viewer;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current) values(s_lead,'2090/2091',2090,2091,true) returning id into y_lead;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current) values(s_out,'2090/2091',2090,2091,true) returning id into y_out;

    insert into public.teachers(school_id,name) values(s_owner,'S2-C2 Owner Managed Teacher') returning id into t_owner;
    insert into public.teachers(school_id,name) values(s_teacher,'S2-C2 Self Teacher') returning id into t_self;
    insert into public.teachers(school_id,name) values(s_teacher,'S2-C2 Other Teacher') returning id into t_other;
    insert into public.teachers(school_id,name) values(s_viewer,'S2-C2 Viewer School Teacher') returning id into t_view;
    insert into public.teachers(school_id,name) values(s_lead,'S2-C2 Lead School Teacher') returning id into t_lead;

    insert into public.school_memberships(school_id,user_id,role,status) values(s_owner,v_uid,'owner','active');
    insert into public.school_memberships(school_id,user_id,teacher_id,role,status) values(s_teacher,v_uid,t_self,'teacher','active');
    insert into public.school_memberships(school_id,user_id,role,status) values(s_viewer,v_uid,'viewer','active');
    insert into public.school_memberships(school_id,user_id,role,status) values(s_lead,v_uid,'lead_teacher','active');

    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_teacher,y_teacher,'S2-C2 Teacher Visible Event','اختبار',date '2090-09-01') returning id into e_teacher;
    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_viewer,y_viewer,'S2-C2 Viewer Visible Event','اختبار',date '2090-09-01') returning id into e_viewer;
    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_out,y_out,'S2-C2 Outsider Event','اختبار',date '2090-09-01') returning id into e_out;

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,deadline,allowed_files,token_hash,status,expires_at
    ) values(
        s_teacher,y_teacher,t_self,'evidence','Physics','10','S2-C2 Teacher Request',date '2090-09-10','pdf','s2c2-teacher-token-hash','waiting_upload',clock_timestamp()+interval '1 day'
    ) returning id into r_teacher;

    insert into public.documents(
        school_id,academic_year_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status
    ) values(
        s_teacher,y_teacher,t_self,'S2-C2 Teacher Document','evidence','teacher.pdf',100,'legacy_local','inbox'
    );

    insert into public.documents(
        school_id,academic_year_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status
    ) values(
        s_viewer,y_viewer,t_view,'S2-C2 Viewer Hidden Document','evidence','viewer.pdf',100,'legacy_local','inbox'
    );

    insert into public.activities(school_id,academic_year_id,activity_type,title)
    values(s_owner,y_owner,'acceptance','S2-C2 Owner Activity');
    insert into public.activities(school_id,academic_year_id,activity_type,title)
    values(s_teacher,y_teacher,'acceptance','S2-C2 Teacher Hidden Activity');

    perform set_config('marsad.s_owner',s_owner::text,true);
    perform set_config('marsad.s_teacher',s_teacher::text,true);
    perform set_config('marsad.s_viewer',s_viewer::text,true);
    perform set_config('marsad.s_lead',s_lead::text,true);
    perform set_config('marsad.s_out',s_out::text,true);
    perform set_config('marsad.y_owner',y_owner::text,true);
    perform set_config('marsad.y_out',y_out::text,true);
    perform set_config('marsad.t_self',t_self::text,true);
    perform set_config('marsad.t_other',t_other::text,true);
    perform set_config('marsad.t_lead',t_lead::text,true);
    perform set_config('marsad.e_teacher',e_teacher::text,true);
    perform set_config('marsad.e_viewer',e_viewer::text,true);
    perform set_config('marsad.e_out',e_out::text,true);
end $$;

select set_config('request.jwt.claim.sub', current_setting('marsad.test_user_id'), true);
select set_config('request.jwt.claims', json_build_object('sub',current_setting('marsad.test_user_id'),'role','authenticated')::text, true);
set local role authenticated;

do $$
declare
    s_owner uuid:=current_setting('marsad.s_owner')::uuid;
    s_teacher uuid:=current_setting('marsad.s_teacher')::uuid;
    s_viewer uuid:=current_setting('marsad.s_viewer')::uuid;
    s_lead uuid:=current_setting('marsad.s_lead')::uuid;
    s_out uuid:=current_setting('marsad.s_out')::uuid;
    y_owner bigint:=current_setting('marsad.y_owner')::bigint;
    y_out bigint:=current_setting('marsad.y_out')::bigint;
    t_self bigint:=current_setting('marsad.t_self')::bigint;
    t_other bigint:=current_setting('marsad.t_other')::bigint;
    v_count integer; v_rows integer; v_blocked boolean;
begin
    -- School-wide operational reading: teacher/viewer can read their school, not outsider.
    select count(*) into v_count from public.events where school_id=s_teacher;
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: teacher cannot read school-wide operational event'; end if;
    select count(*) into v_count from public.events where school_id=s_viewer;
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: viewer cannot read school-wide operational event'; end if;
    select count(*) into v_count from public.events where school_id=s_out;
    if v_count <> 0 then raise exception 'S2-C2 acceptance failed: outsider school event leaked'; end if;

    -- Teacher-private reading: teacher sees self only; viewer sees none; lead sees private rows in lead school.
    select count(*) into v_count from public.teachers where school_id=s_teacher and id in (t_self,t_other);
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: teacher private visibility expected 1, got %',v_count; end if;
    select count(*) into v_count from public.teachers where school_id=s_viewer;
    if v_count <> 0 then raise exception 'S2-C2 acceptance failed: viewer saw private teacher directory'; end if;
    select count(*) into v_count from public.teachers where school_id=s_lead;
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: lead_teacher cannot read private teacher directory'; end if;

    select count(*) into v_count from public.documents where school_id=s_teacher;
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: teacher cannot read own document'; end if;
    select count(*) into v_count from public.documents where school_id=s_viewer;
    if v_count <> 0 then raise exception 'S2-C2 acceptance failed: viewer saw private document'; end if;

    -- Token-bearing upload_requests are manager-sensitive, not teacher-self readable in C2.
    select count(*) into v_count from public.upload_requests where school_id=s_teacher;
    if v_count <> 0 then raise exception 'S2-C2 acceptance failed: teacher saw manager-sensitive upload request'; end if;

    -- Audit activity is manager-only.
    select count(*) into v_count from public.activities where school_id=s_owner;
    if v_count <> 1 then raise exception 'S2-C2 acceptance failed: owner cannot read audit activity'; end if;
    select count(*) into v_count from public.activities where school_id=s_teacher;
    if v_count <> 0 then raise exception 'S2-C2 acceptance failed: teacher saw manager-only audit activity'; end if;

    -- Owner can create approved browser-managed domain rows inside own tenant.
    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_owner,y_owner,'S2-C2 Owner Created Event','اختبار',date '2090-09-02');
    insert into public.teachers(school_id,name) values(s_owner,'S2-C2 Owner Created Teacher');

    -- Cross-tenant insert must be rejected even though INSERT privilege exists.
    v_blocked:=false;
    begin
        insert into public.events(school_id,academic_year_id,title,event_type,event_date)
        values(s_out,y_out,'SHOULD NOT INSERT','اختبار',date '2090-09-02');
    exception when insufficient_privilege then v_blocked:=true;
    end;
    if not v_blocked then raise exception 'S2-C2 acceptance failed: cross-school event insert unexpectedly succeeded'; end if;

    -- Teacher and viewer roles are read-only in C2. UPDATE should affect zero rows through RLS.
    update public.events set title='SHOULD NOT UPDATE' where school_id=s_teacher;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then raise exception 'S2-C2 acceptance failed: teacher updated operational row'; end if;
    update public.events set title='SHOULD NOT UPDATE' where school_id=s_viewer;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then raise exception 'S2-C2 acceptance failed: viewer updated operational row'; end if;

    -- lead_teacher is deliberately read-only until department-scoped authorization exists.
    update public.teachers set name='SHOULD NOT UPDATE' where school_id=s_lead;
    get diagnostics v_rows=row_count;
    if v_rows <> 0 then raise exception 'S2-C2 acceptance failed: lead_teacher received school-wide write power'; end if;

    -- Locked trusted/storage/audit tables have no direct browser write grant, even for owner.
    v_blocked:=false;
    begin
        insert into public.activities(school_id,academic_year_id,activity_type,title)
        values(s_owner,y_owner,'forged','SHOULD NOT INSERT');
    exception when insufficient_privilege then v_blocked:=true;
    end;
    if not v_blocked then raise exception 'S2-C2 acceptance failed: browser forged audit activity'; end if;

    v_blocked:=false;
    begin
        insert into public.upload_requests(
            school_id,academic_year_id,teacher_id,request_type,subject,grade,title,deadline,allowed_files,token_hash,status,expires_at
        ) values(s_owner,y_owner,t_self,'x','x','x','SHOULD NOT INSERT',date '2090-09-03','pdf','forbidden-token-hash','waiting_upload',clock_timestamp()+interval '1 day');
    exception when insufficient_privilege then v_blocked:=true;
         when foreign_key_violation then
             raise exception 'S2-C2 acceptance failed: upload request reached FK evaluation before privilege lock';
    end;
    if not v_blocked then raise exception 'S2-C2 acceptance failed: direct upload-request creation unexpectedly succeeded'; end if;

    v_blocked:=false;
    begin
        insert into public.documents(school_id,academic_year_id,title,category,original_name,size_bytes,storage_provider,status)
        values(s_owner,y_owner,'SHOULD NOT INSERT','x','x.pdf',1,'legacy_local','inbox');
    exception when insufficient_privilege then v_blocked:=true;
    end;
    if not v_blocked then raise exception 'S2-C2 acceptance failed: direct document metadata insert unexpectedly succeeded'; end if;

    -- Root destructive delete is not part of the verified legacy route surface.
    v_blocked:=false;
    begin
        delete from public.events where school_id=s_owner;
    exception when insufficient_privilege then v_blocked:=true;
    end;
    if not v_blocked then raise exception 'S2-C2 acceptance failed: root event delete unexpectedly granted'; end if;
end $$;

reset role;
select 'PASS: S2-C2 domain RLS baseline acceptance' as result;
rollback;
