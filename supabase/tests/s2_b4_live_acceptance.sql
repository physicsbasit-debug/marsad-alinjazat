-- Marsad Al-Injazat — S2-B4 live acceptance
-- Run AFTER the S2-B4 migration in Supabase SQL Editor.
-- Safe: all test rows are removed by the final ROLLBACK.

begin;

do $$
declare
    v_table_count integer;
    v_grant_count integer;
    v_rls_count integer;
    v_policy_count integer;
    v_def text;
begin
    select count(*) into v_table_count
    from information_schema.tables
    where table_schema = 'public'
      and table_name in (
        'school_settings','upload_requests','documents','events',
        'event_media','event_teacher_links','activities'
      );
    if v_table_count <> 7 then
        raise exception 'S2-B4 acceptance failed: expected 7 tables, found %', v_table_count;
    end if;

    select count(*) into v_grant_count
    from information_schema.role_table_grants
    where table_schema = 'public'
      and table_name in (
        'school_settings','upload_requests','documents','events',
        'event_media','event_teacher_links','activities'
      )
      and grantee in ('anon','authenticated');
    if v_grant_count <> 0 then
        raise exception 'S2-B4 acceptance failed: browser roles still have % grants', v_grant_count;
    end if;

    select count(*) into v_policy_count
    from pg_policies
    where schemaname = 'public'
      and tablename in (
        'school_settings','upload_requests','documents','events',
        'event_media','event_teacher_links','activities'
      );
    if v_policy_count <> 0 then
        raise exception 'S2-B4 acceptance failed: S2-C policies appeared early: %', v_policy_count;
    end if;

    select count(*) into v_rls_count
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname in (
        'school_settings','upload_requests','documents','events',
        'event_media','event_teacher_links','activities'
      )
      and c.relrowsecurity;
    if v_rls_count not in (0, 7) then
        raise exception 'S2-B4 acceptance failed: inconsistent auto-RLS state, enabled on % of 7 tables', v_rls_count;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.upload_requests'::regclass
      and conname = 'upload_requests_teacher_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, teacher_id)%'
       or v_def not ilike '%REFERENCES teachers(school_id, id)%'
       or v_def not ilike '%ON DELETE RESTRICT%' then
        raise exception 'S2-B4 acceptance failed: upload request teacher FK is wrong: %', v_def;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.documents'::regclass
      and conname = 'documents_request_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, request_id)%'
       or v_def not ilike '%REFERENCES upload_requests(school_id, id)%'
       or v_def not ilike '%ON DELETE SET NULL (request_id)%' then
        raise exception 'S2-B4 acceptance failed: document/request FK is wrong: %', v_def;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.school_settings'::regclass
      and conname = 'school_settings_updated_by_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, updated_by)%'
       or v_def not ilike '%REFERENCES school_memberships(school_id, user_id)%'
       or v_def not ilike '%ON DELETE SET NULL (updated_by)%' then
        raise exception 'S2-B4 acceptance failed: school setting updater FK is wrong: %', v_def;
    end if;
end $$;

do $$
declare
    s1 uuid;
    s2 uuid;
    y1 bigint;
    y2 bigint;
    t_request bigint;
    t_document bigint;
    t_other_school bigint;
    request_keep bigint;
    request_delete bigint;
    request_other_school bigint;
    document_from_request bigint;
    document_direct bigint;
    event1 bigint;
    event2 bigint;
    media1 bigint;
    v_nullable bigint;
    v_count integer;
begin
    insert into public.schools(name) values ('S2-B4 قبول مدرسة 1') returning id into s1;
    insert into public.schools(name) values ('S2-B4 قبول مدرسة 2') returning id into s2;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values (s1,'2096/2097',2096,2097,false) returning id into y1;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values (s2,'2096/2097',2096,2097,false) returning id into y2;

    insert into public.teachers(school_id,name) values (s1,'معلم طلب S2-B4') returning id into t_request;
    insert into public.teachers(school_id,name) values (s1,'معلم وثيقة S2-B4') returning id into t_document;
    insert into public.teachers(school_id,name) values (s2,'معلم مدرسة أخرى S2-B4') returning id into t_other_school;

    insert into public.school_settings(school_id,key,value)
    values (s1,'school.branding',jsonb_build_object('tone','teal'));

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        token_hash,status,expires_at
    ) values (
        s1,y1,t_request,'تحليل نتائج','العلوم','10','طلب قبول S2-B4',
        's2b4-token-keep','waiting_upload',timestamptz '2097-12-31 20:00:00+00'
    ) returning id into request_keep;

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        token_hash,status,expires_at
    ) values (
        s1,y1,t_request,'خطة','العلوم','10','طلب سيحذف',
        's2b4-token-delete','review',timestamptz '2097-12-31 20:00:00+00'
    ) returning id into request_delete;

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
        token_hash,status,expires_at
    ) values (
        s2,y2,t_other_school,'وثيقة','العلوم','10','طلب مدرسة أخرى',
        's2b4-token-other','waiting_upload',timestamptz '2097-12-31 20:00:00+00'
    ) returning id into request_other_school;

    insert into public.documents(
        school_id,academic_year_id,request_id,teacher_id,title,category,original_name,
        size_bytes,storage_provider,storage_bucket,storage_path,status
    ) values (
        s1,y1,request_delete,t_request,'وثيقة من طلب','تحليل نتائج','analysis.xlsx',
        1200,'legacy_local',null,'legacy/analysis.xlsx','inbox'
    ) returning id into document_from_request;

    delete from public.upload_requests where id = request_delete;
    select request_id into v_nullable from public.documents where id = document_from_request;
    if v_nullable is not null then
        raise exception 'S2-B4 acceptance failed: deleting request did not SET NULL on document.request_id';
    end if;

    insert into public.documents(
        school_id,academic_year_id,teacher_id,title,category,original_name,
        size_bytes,storage_provider,storage_bucket,storage_path,status
    ) values (
        s1,y1,t_document,'وثيقة مباشرة','وثيقة','direct.pdf',
        2048,'supabase','marsad-documents','s2b4/direct.pdf','inbox'
    ) returning id into document_direct;

    delete from public.teachers where id = t_document;
    select teacher_id into v_nullable from public.documents where id = document_direct;
    if v_nullable is not null then
        raise exception 'S2-B4 acceptance failed: deleting optional document teacher did not SET NULL';
    end if;

    begin
        delete from public.teachers where id = t_request;
        raise exception 'expected upload request teacher delete restriction';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.upload_requests(
            school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
            token_hash,status,expires_at
        ) values (
            s1,y2,t_request,'اختبار','العلوم','10','سنة من مدرسة أخرى',
            's2b4-token-cross-year','waiting_upload',timestamptz '2097-12-31 20:00:00+00'
        );
        raise exception 'expected cross-school academic year rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.upload_requests(
            school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
            token_hash,status,expires_at
        ) values (
            s1,y1,t_other_school,'اختبار','العلوم','10','معلم من مدرسة أخرى',
            's2b4-token-cross-teacher','waiting_upload',timestamptz '2097-12-31 20:00:00+00'
        );
        raise exception 'expected cross-school request teacher rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.upload_requests(
            school_id,academic_year_id,teacher_id,request_type,subject,grade,title,
            token_hash,status,expires_at
        ) values (
            s1,y1,t_request,'اختبار','العلوم','10','حالة خاطئة',
            's2b4-token-bad-status','not_a_status',timestamptz '2097-12-31 20:00:00+00'
        );
        raise exception 'expected request status check rejection';
    exception when check_violation then null;
    end;

    begin
        insert into public.documents(
            school_id,academic_year_id,request_id,title,category,original_name,
            size_bytes,storage_provider,status
        ) values (
            s1,y1,request_other_school,'وثيقة عابرة للمدارس','وثيقة','wrong.pdf',
            10,'legacy_local','inbox'
        );
        raise exception 'expected cross-school document/request rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.documents(
            school_id,academic_year_id,title,category,original_name,size_bytes,storage_provider,status
        ) values (
            s1,y1,'مزود خاطئ','وثيقة','bad.bin',10,'local','inbox'
        );
        raise exception 'expected document storage provider rejection';
    exception when check_violation then null;
    end;

    insert into public.events(
        school_id,academic_year_id,title,event_type,event_date,participant_count
    ) values (
        s1,y1,'فعالية قبول S2-B4','تربوية',date '2097-02-10',30
    ) returning id into event1;

    insert into public.events(
        school_id,academic_year_id,title,event_type,event_date,participant_count
    ) values (
        s2,y2,'فعالية مدرسة أخرى','تربوية',date '2097-02-10',20
    ) returning id into event2;

    insert into public.event_media(
        school_id,event_id,original_name,mime_type,size_bytes,storage_provider,
        storage_bucket,storage_path,caption,position,is_cover
    ) values (
        s1,event1,'cover.jpg','image/jpeg',5000,'supabase',
        'marsad-events','s2b4/events/cover.jpg','غلاف',0,true
    ) returning id into media1;

    insert into public.event_media(
        school_id,event_id,original_name,mime_type,size_bytes,storage_provider,
        storage_bucket,storage_path,caption,position,is_cover
    ) values (
        s1,event1,'second.jpg','image/jpeg',4000,'supabase',
        'marsad-events','s2b4/events/second.jpg','صورة ثانية',1,false
    );

    begin
        insert into public.event_media(
            school_id,event_id,original_name,size_bytes,storage_provider,position,is_cover
        ) values (
            s1,event1,'cover-2.jpg',100,'supabase',2,true
        );
        raise exception 'expected one-cover-per-event uniqueness rejection';
    exception when unique_violation then null;
    end;

    begin
        insert into public.event_media(
            school_id,event_id,original_name,size_bytes,storage_provider
        ) values (
            s1,event2,'cross-school.jpg',100,'supabase'
        );
        raise exception 'expected cross-school event media rejection';
    exception when foreign_key_violation then null;
    end;

    insert into public.event_teacher_links(school_id,event_id,teacher_id,role)
    values (s1,event1,t_request,'منظم');

    begin
        insert into public.event_teacher_links(school_id,event_id,teacher_id,role)
        values (s1,event1,t_other_school,'مشارك');
        raise exception 'expected cross-school event teacher rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.events(
            school_id,academic_year_id,title,event_type,event_date,participant_count
        ) values (
            s1,y1,'عدد خاطئ','تربوية',date '2097-02-11',-1
        );
        raise exception 'expected event participant_count check rejection';
    exception when check_violation then null;
    end;

    insert into public.activities(
        school_id,academic_year_id,activity_type,title,entity_type,entity_id
    ) values (
        s1,y1,'event','إنشاء فعالية','event',event1
    );

    begin
        insert into public.activities(
            school_id,academic_year_id,activity_type,title
        ) values (
            s1,y2,'audit','سنة نشاط من مدرسة أخرى'
        );
        raise exception 'expected cross-school activity year rejection';
    exception when foreign_key_violation then null;
    end;

    select count(*) into v_count
    from public.event_media
    where school_id = s1 and event_id = event1 and is_cover;
    if v_count <> 1 then
        raise exception 'S2-B4 acceptance failed: event cover invariant count=%', v_count;
    end if;
end $$;

select 'PASS: S2-B4 live acceptance' as result;
rollback;
