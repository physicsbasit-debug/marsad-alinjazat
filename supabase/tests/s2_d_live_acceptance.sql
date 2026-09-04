-- Marsad Al-Injazat — Phase S2-D live acceptance
-- Database acceptance and SQLite data-migration readiness gate.
-- Prerequisite: S2-C2 is LIVE GREEN and at least one real Supabase Auth user with public.profiles exists.
-- No auth.users mutation, no storage mutation, and every public fixture is rolled back.

begin;

-- 1) Structural end-state: frozen schema + Auth/RLS + updated_at hardening.
do $$
declare
    v_count integer;
    v_target text[] := array[
        'schools','profiles','school_memberships','academic_years','school_settings','teachers',
        'teacher_profiles','teacher_years','teacher_cv_items','upload_requests','documents','events',
        'event_media','event_teacher_links','activities','meetings','meeting_attendees','meeting_decisions',
        'curriculum_plans','curriculum_units','supervision_visits','supervision_actions',
        'achievement_assessments','achievement_assessment_standards','achievement_actions','achievement_action_metrics'
    ];
begin
    select count(*) into v_count
    from information_schema.tables
    where table_schema='public' and table_type='BASE TABLE' and table_name=any(v_target);
    if v_count <> 26 then
        raise exception 'S2-D acceptance failed: expected 26 target tables, got %', v_count;
    end if;

    select count(*) into v_count
    from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname=any(v_target) and c.relrowsecurity;
    if v_count <> 26 then
        raise exception 'S2-D acceptance failed: expected RLS on all 26 target tables, got %', v_count;
    end if;

    select count(*) into v_count from pg_policies where schemaname='public';
    if v_count <> 69 then
        raise exception 'S2-D acceptance failed: expected 69 public policies, got %', v_count;
    end if;

    if exists (
        select 1 from information_schema.role_table_grants
        where table_schema='public' and grantee='anon'
    ) or exists (
        select 1 from information_schema.role_column_grants
        where table_schema='public' and grantee='anon'
    ) then
        raise exception 'S2-D acceptance failed: anon received public grants';
    end if;

    select count(*) into v_count
    from pg_trigger t
    join pg_class c on c.oid=t.tgrelid
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public'
      and t.tgname ~ '^trg_.*_updated_at$'
      and not t.tgisinternal;
    if v_count <> 22 then
        raise exception 'S2-D acceptance failed: expected 22 updated_at triggers, got %', v_count;
    end if;

    if position('clock_timestamp()' in pg_get_functiondef('public.set_row_updated_at()'::regprocedure)) = 0 then
        raise exception 'S2-D acceptance failed: updated_at helper is not using clock_timestamp()';
    end if;

    select count(*) into v_count
    from pg_trigger t
    join pg_class c on c.oid=t.tgrelid
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='auth' and c.relname='users'
      and t.tgname='on_marsad_auth_user_created' and not t.tgisinternal;
    if v_count <> 1 then
        raise exception 'S2-D acceptance failed: Auth profile trigger missing';
    end if;

    select count(*) into v_count
    from information_schema.columns
    where table_schema='public' and table_name='teacher_years'
      and column_name in ('subject','experience_years','workload','grades','responsibilities')
      and is_nullable='YES';
    if v_count <> 5 then
        raise exception 'S2-D acceptance failed: historical teacher-year optional attributes are no longer nullable';
    end if;
end $$;

-- 2) Reuse one real Auth identity. Never create/mutate auth.users from SQL.
select set_config(
    'marsad.test_user_id',
    coalesce((select id::text from auth.users order by created_at desc limit 1), ''),
    true
);

do $$
begin
    if nullif(current_setting('marsad.test_user_id', true),'') is null then
        raise exception 'S2-D acceptance prerequisite: keep/create one real Auth user';
    end if;
    if not exists (select 1 from public.profiles where id=current_setting('marsad.test_user_id')::uuid) then
        raise exception 'S2-D acceptance prerequisite: newest Auth user has no public profile';
    end if;
end $$;

-- 3) Build a complete miniature dataset in two schools. School A has two academic years;
-- School B is a fully populated outsider tenant. All rows disappear at final ROLLBACK.
do $$
declare
    v_uid uuid := current_setting('marsad.test_user_id')::uuid;
    s_a uuid; s_b uuid;
    y_a_cur bigint; y_a_old bigint; y_b_cur bigint;
    t_a1 bigint; t_a2 bigint; t_b1 bigint;
    r_a_cur bigint; r_a_old bigint; r_b bigint;
    e_a_cur bigint; e_a_old bigint; e_b bigint;
    m_a_cur bigint; m_a_old bigint; m_b bigint;
    p_a_cur bigint; p_a_old bigint; p_b bigint;
    v_a_cur bigint; v_a_old bigint; v_b bigint;
    a_a_cur bigint; a_a_old bigint; a_b bigint;
    act_a bigint; act_b bigint;
begin
    insert into public.schools(name) values('S2-D Acceptance School A') returning id into s_a;
    insert into public.schools(name) values('S2-D Acceptance School B') returning id into s_b;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_a,'2090/2091',2090,2091,true) returning id into y_a_cur;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_a,'2089/2090',2089,2090,false) returning id into y_a_old;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values(s_b,'2090/2091',2090,2091,true) returning id into y_b_cur;

    insert into public.teachers(school_id,name,specialization) values(s_a,'S2-D Teacher A1','Physics') returning id into t_a1;
    insert into public.teachers(school_id,name,specialization) values(s_a,'S2-D Teacher A2','Chemistry') returning id into t_a2;
    insert into public.teachers(school_id,name,specialization) values(s_b,'S2-D Teacher B1','Physics') returning id into t_b1;

    insert into public.school_memberships(school_id,user_id,teacher_id,role,status)
    values(s_a,v_uid,t_a1,'owner','active');

    insert into public.school_settings(school_id,key,value,updated_by)
    values(s_a,'migration_acceptance',jsonb_build_object('school','A'),v_uid);
    insert into public.school_settings(school_id,key,value,updated_by)
    values(s_b,'migration_acceptance',jsonb_build_object('school','B'),null);

    insert into public.teacher_profiles(teacher_id,school_id,employee_number,school_join_year,professional_summary)
    values(t_a1,s_a,'S2D-A1',2020,'Acceptance profile A1');
    insert into public.teacher_profiles(teacher_id,school_id,employee_number,school_join_year,professional_summary)
    values(t_a2,s_a,'S2D-A2',2021,'Acceptance profile A2');
    insert into public.teacher_profiles(teacher_id,school_id,employee_number,school_join_year,professional_summary)
    values(t_b1,s_b,'S2D-B1',2022,'Acceptance profile B1');

    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload,grades,responsibilities)
    values(s_a,y_a_cur,t_a1,'Physics',12,20,'10','Lab');
    -- Historical attributes intentionally unknown and therefore NULL.
    insert into public.teacher_years(school_id,academic_year_id,teacher_id)
    values(s_a,y_a_old,t_a1);
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject)
    values(s_a,y_a_cur,t_a2,'Chemistry');
    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject)
    values(s_b,y_b_cur,t_b1,'Physics');

    insert into public.teacher_cv_items(school_id,teacher_id,item_type,title,start_year,end_year)
    values(s_a,t_a1,'course','S2-D Course A',2088,2088);
    insert into public.teacher_cv_items(school_id,teacher_id,item_type,title,start_year,end_year)
    values(s_b,t_b1,'course','S2-D Course B',2088,2088);

    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,deadline,allowed_files,token_hash,status,expires_at
    ) values(s_a,y_a_cur,t_a1,'evidence','Physics','10','S2-D Request A Current',date '2090-10-01','pdf','s2d-a-current-token','waiting_upload',clock_timestamp()+interval '1 day')
    returning id into r_a_cur;
    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,deadline,allowed_files,token_hash,status,expires_at
    ) values(s_a,y_a_old,t_a1,'evidence','Physics','10','S2-D Request A Old',date '2089-10-01','pdf','s2d-a-old-token','approved',clock_timestamp()+interval '1 day')
    returning id into r_a_old;
    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,deadline,allowed_files,token_hash,status,expires_at
    ) values(s_b,y_b_cur,t_b1,'evidence','Physics','10','S2-D Request B',date '2090-10-01','pdf','s2d-b-token','waiting_upload',clock_timestamp()+interval '1 day')
    returning id into r_b;

    insert into public.documents(school_id,academic_year_id,request_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status)
    values(s_a,y_a_cur,r_a_cur,t_a1,'S2-D Document A Current','evidence','a-current.pdf',100,'legacy_local','inbox');
    insert into public.documents(school_id,academic_year_id,request_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status)
    values(s_a,y_a_old,r_a_old,t_a1,'S2-D Document A Old','evidence','a-old.pdf',101,'legacy_local','approved');
    insert into public.documents(school_id,academic_year_id,request_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status)
    values(s_b,y_b_cur,r_b,t_b1,'S2-D Document B','evidence','b.pdf',102,'legacy_local','inbox');

    insert into public.events(school_id,academic_year_id,title,event_type,event_date,participant_count)
    values(s_a,y_a_cur,'S2-D Event A Current','activity',date '2090-09-01',10) returning id into e_a_cur;
    insert into public.events(school_id,academic_year_id,title,event_type,event_date,participant_count)
    values(s_a,y_a_old,'S2-D Event A Old','activity',date '2089-09-01',9) returning id into e_a_old;
    insert into public.events(school_id,academic_year_id,title,event_type,event_date,participant_count)
    values(s_b,y_b_cur,'S2-D Event B','activity',date '2090-09-01',8) returning id into e_b;

    insert into public.event_media(school_id,event_id,original_name,size_bytes,storage_provider,caption,position,is_cover)
    values(s_a,e_a_cur,'a.jpg',200,'legacy_local','A cover',0,true);
    insert into public.event_media(school_id,event_id,original_name,size_bytes,storage_provider,caption,position,is_cover)
    values(s_b,e_b,'b.jpg',200,'legacy_local','B cover',0,true);
    insert into public.event_teacher_links(school_id,event_id,teacher_id,role) values(s_a,e_a_cur,t_a1,'participant');
    insert into public.event_teacher_links(school_id,event_id,teacher_id,role) values(s_b,e_b,t_b1,'participant');

    insert into public.activities(school_id,academic_year_id,actor_user_id,activity_type,title)
    values(s_a,y_a_cur,v_uid,'acceptance','S2-D Activity A Current');
    insert into public.activities(school_id,academic_year_id,actor_user_id,activity_type,title)
    values(s_a,y_a_old,v_uid,'acceptance','S2-D Activity A Old');
    insert into public.activities(school_id,academic_year_id,activity_type,title)
    values(s_b,y_b_cur,'acceptance','S2-D Activity B');

    insert into public.meetings(school_id,academic_year_id,title,meeting_date,status)
    values(s_a,y_a_cur,'S2-D Meeting A Current',date '2090-09-02','held') returning id into m_a_cur;
    insert into public.meetings(school_id,academic_year_id,title,meeting_date,status)
    values(s_a,y_a_old,'S2-D Meeting A Old',date '2089-09-02','held') returning id into m_a_old;
    insert into public.meetings(school_id,academic_year_id,title,meeting_date,status)
    values(s_b,y_b_cur,'S2-D Meeting B',date '2090-09-02','held') returning id into m_b;
    insert into public.meeting_attendees(school_id,meeting_id,teacher_id,attendance_status) values(s_a,m_a_cur,t_a1,'present');
    insert into public.meeting_attendees(school_id,meeting_id,teacher_id,attendance_status) values(s_b,m_b,t_b1,'present');
    insert into public.meeting_decisions(school_id,meeting_id,title,responsible_teacher_id,status)
    values(s_a,m_a_cur,'S2-D Decision A',t_a1,'in_progress');
    insert into public.meeting_decisions(school_id,meeting_id,title,responsible_teacher_id,status)
    values(s_b,m_b,'S2-D Decision B',t_b1,'in_progress');

    insert into public.curriculum_plans(school_id,academic_year_id,title,subject,grade,term,owner_teacher_id,status)
    values(s_a,y_a_cur,'S2-D Plan A Current','Physics','10','1',t_a1,'active') returning id into p_a_cur;
    insert into public.curriculum_plans(school_id,academic_year_id,title,subject,grade,term,owner_teacher_id,status)
    values(s_a,y_a_old,'S2-D Plan A Old','Physics','10','1',t_a1,'archived') returning id into p_a_old;
    insert into public.curriculum_plans(school_id,academic_year_id,title,subject,grade,term,owner_teacher_id,status)
    values(s_b,y_b_cur,'S2-D Plan B','Physics','10','1',t_b1,'active') returning id into p_b;
    insert into public.curriculum_units(school_id,plan_id,title,sequence,progress_percent,status,responsible_teacher_id)
    values(s_a,p_a_cur,'S2-D Unit A',1,50,'in_progress',t_a1);
    insert into public.curriculum_units(school_id,plan_id,title,sequence,progress_percent,status,responsible_teacher_id)
    values(s_b,p_b,'S2-D Unit B',1,50,'in_progress',t_b1);

    insert into public.supervision_visits(school_id,academic_year_id,teacher_id,visit_date,status)
    values(s_a,y_a_cur,t_a1,date '2090-09-03','completed') returning id into v_a_cur;
    insert into public.supervision_visits(school_id,academic_year_id,teacher_id,visit_date,status)
    values(s_a,y_a_old,t_a1,date '2089-09-03','closed') returning id into v_a_old;
    insert into public.supervision_visits(school_id,academic_year_id,teacher_id,visit_date,status)
    values(s_b,y_b_cur,t_b1,date '2090-09-03','completed') returning id into v_b;
    insert into public.supervision_actions(school_id,visit_id,title,responsible_teacher_id,status)
    values(s_a,v_a_cur,'S2-D Supervision Action A',t_a1,'new');
    insert into public.supervision_actions(school_id,visit_id,title,responsible_teacher_id,status)
    values(s_b,v_b,'S2-D Supervision Action B',t_b1,'new');

    insert into public.achievement_assessments(
        school_id,academic_year_id,title,subject,grade,assessment_date,term,teacher_id,max_score,student_count,
        average_score,highest_score,lowest_score,mastery_threshold_pct,mastered_count,near_mastery_count,intervention_count,status
    ) values(s_a,y_a_cur,'S2-D Assessment A Current','Physics','10',date '2090-09-04','1',t_a1,100,30,72,98,25,60,18,7,5,'recorded')
    returning id into a_a_cur;
    insert into public.achievement_assessments(
        school_id,academic_year_id,title,subject,grade,assessment_date,term,teacher_id,max_score,student_count,
        average_score,highest_score,lowest_score,mastery_threshold_pct,mastered_count,near_mastery_count,intervention_count,status
    ) values(s_a,y_a_old,'S2-D Assessment A Old','Physics','10',date '2089-09-04','1',t_a1,100,28,70,96,20,60,16,7,5,'reviewed')
    returning id into a_a_old;
    insert into public.achievement_assessments(
        school_id,academic_year_id,title,subject,grade,assessment_date,term,teacher_id,max_score,student_count,
        average_score,highest_score,lowest_score,mastery_threshold_pct,mastered_count,near_mastery_count,intervention_count,status
    ) values(s_b,y_b_cur,'S2-D Assessment B','Physics','10',date '2090-09-04','1',t_b1,100,20,65,90,20,60,10,5,5,'recorded')
    returning id into a_b;

    insert into public.achievement_assessment_standards(assessment_id,school_id,mastery_reference_source,mastery_reference_year)
    values(a_a_cur,s_a,'S2-D Reference A','2090');
    insert into public.achievement_assessment_standards(assessment_id,school_id,mastery_reference_source,mastery_reference_year)
    values(a_b,s_b,'S2-D Reference B','2090');

    insert into public.achievement_actions(school_id,assessment_id,action_type,title,responsible_teacher_id,status,baseline_indicator,target_indicator)
    values(s_a,a_a_cur,'remedial','S2-D Action A',t_a1,'in_progress','60','75') returning id into act_a;
    insert into public.achievement_actions(school_id,assessment_id,action_type,title,responsible_teacher_id,status,baseline_indicator,target_indicator)
    values(s_b,a_b,'remedial','S2-D Action B',t_b1,'in_progress','60','75') returning id into act_b;
    insert into public.achievement_action_metrics(action_id,school_id,metric_name,unit,direction,baseline_value,target_value)
    values(act_a,s_a,'mastery','%','higher_better',60,75);
    insert into public.achievement_action_metrics(action_id,school_id,metric_name,unit,direction,baseline_value,target_value)
    values(act_b,s_b,'mastery','%','higher_better',60,75);

    perform set_config('marsad.s_a',s_a::text,true);
    perform set_config('marsad.s_b',s_b::text,true);
    perform set_config('marsad.y_a_cur',y_a_cur::text,true);
    perform set_config('marsad.y_a_old',y_a_old::text,true);
    perform set_config('marsad.y_b_cur',y_b_cur::text,true);
    perform set_config('marsad.t_a1',t_a1::text,true);
    perform set_config('marsad.t_a2',t_a2::text,true);
    perform set_config('marsad.t_b1',t_b1::text,true);
    perform set_config('marsad.r_a_cur',r_a_cur::text,true);
    perform set_config('marsad.e_a_cur',e_a_cur::text,true);
end $$;

-- 4) Database constraints and referential behavior as SQL owner.
do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    s_b uuid:=current_setting('marsad.s_b')::uuid;
    y_a_cur bigint:=current_setting('marsad.y_a_cur')::bigint;
    y_b_cur bigint:=current_setting('marsad.y_b_cur')::bigint;
    t_a1 bigint:=current_setting('marsad.t_a1')::bigint;
    t_b1 bigint:=current_setting('marsad.t_b1')::bigint;
    e_a_cur bigint:=current_setting('marsad.e_a_cur')::bigint;
    v_blocked boolean;
    v_event bigint; v_request bigint; v_doc bigint; v_action bigint;
    v_count integer;
begin
    v_blocked:=false;
    begin
        insert into public.academic_years(school_id,label,start_year,end_year,is_current)
        values(s_a,'2091/2092',2091,2092,true);
    exception when unique_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: duplicate current academic year accepted'; end if;

    v_blocked:=false;
    begin
        insert into public.upload_requests(
            school_id,academic_year_id,teacher_id,request_type,subject,grade,title,allowed_files,token_hash,status,expires_at
        ) values(s_a,y_a_cur,t_a1,'evidence','Physics','10','Duplicate token','pdf','s2d-a-current-token','waiting_upload',clock_timestamp()+interval '1 day');
    exception when unique_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: duplicate token_hash accepted'; end if;

    v_blocked:=false;
    begin
        insert into public.event_media(school_id,event_id,original_name,size_bytes,storage_provider,is_cover)
        values(s_a,e_a_cur,'second-cover.jpg',1,'legacy_local',true);
    exception when unique_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: second event cover accepted'; end if;

    v_blocked:=false;
    begin
        insert into public.event_teacher_links(school_id,event_id,teacher_id,role)
        values(s_a,e_a_cur,t_b1,'cross-school');
    exception when foreign_key_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: cross-school teacher/event link accepted'; end if;

    v_blocked:=false;
    begin
        insert into public.achievement_assessments(
            school_id,academic_year_id,title,subject,grade,assessment_date,term,max_score,student_count,
            mastered_count,near_mastery_count,intervention_count,status
        ) values(s_a,y_a_cur,'Bad buckets','Physics','10',date '2090-09-05','1',100,10,8,5,2,'recorded');
    exception when check_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: invalid achievement bucket arithmetic accepted'; end if;

    insert into public.achievement_actions(school_id,assessment_id,action_type,title,status)
    select s_a,id,'followup','S2-D Metric Guard Action','new'
    from public.achievement_assessments where school_id=s_a limit 1
    returning id into v_action;
    v_blocked:=false;
    begin
        insert into public.achievement_action_metrics(action_id,school_id,metric_name,unit,direction,baseline_value,target_value,outcome_value)
        values(v_action,s_a,'bad metric','%','higher_better',60,75,70);
    exception when check_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: metric outcome without measured_at accepted'; end if;

    v_blocked:=false;
    begin
        insert into public.documents(school_id,academic_year_id,title,category,original_name,size_bytes,storage_provider,status)
        values(s_a,y_a_cur,'Bad provider','x','x.bin',1,'local','inbox');
    exception when check_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: invalid storage provider accepted'; end if;

    -- Request delete must keep the document and null the request link.
    insert into public.upload_requests(
        school_id,academic_year_id,teacher_id,request_type,subject,grade,title,allowed_files,token_hash,status,expires_at
    ) values(s_a,y_a_cur,t_a1,'evidence','Physics','10','Delete-set-null request','pdf','s2d-delete-set-null','waiting_upload',clock_timestamp()+interval '1 day')
    returning id into v_request;
    insert into public.documents(school_id,academic_year_id,request_id,teacher_id,title,category,original_name,size_bytes,storage_provider,status)
    values(s_a,y_a_cur,v_request,t_a1,'Delete-set-null doc','x','null.pdf',1,'legacy_local','inbox') returning id into v_doc;
    delete from public.upload_requests where id=v_request;
    select count(*) into v_count from public.documents where id=v_doc and request_id is null;
    if v_count <> 1 then raise exception 'S2-D acceptance failed: document.request_id did not SET NULL'; end if;

    -- Remove the temporary referential-behavior fixture before role visibility counts.
    -- Otherwise teacher/lead_teacher legitimately see a third self-linked document.
    delete from public.documents where id=v_doc;
    select count(*) into v_count from public.documents where id=v_doc;
    if v_count <> 0 then raise exception 'S2-D acceptance failed: temporary SET NULL document cleanup failed'; end if;

    -- Event delete must cascade to media and teacher links.
    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_a,y_a_cur,'Cascade event','x',date '2090-09-06') returning id into v_event;
    insert into public.event_media(school_id,event_id,original_name,size_bytes,storage_provider,is_cover)
    values(s_a,v_event,'cascade.jpg',1,'legacy_local',false);
    insert into public.event_teacher_links(school_id,event_id,teacher_id,role)
    values(s_a,v_event,t_a1,'participant');
    delete from public.events where id=v_event;
    select (select count(*) from public.event_media where event_id=v_event)
         + (select count(*) from public.event_teacher_links where event_id=v_event)
      into v_count;
    if v_count <> 0 then raise exception 'S2-D acceptance failed: event children did not cascade'; end if;

    -- Teacher root remains protected while restrict-linked operational data exists.
    v_blocked:=false;
    begin
        delete from public.teachers where id=t_a1;
    exception when foreign_key_violation then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: referenced teacher deletion was not restricted'; end if;
end $$;

-- 5) Impersonate the real Auth user. First as owner: full same-tenant visibility and zero outsider leakage.
select set_config('request.jwt.claim.sub', current_setting('marsad.test_user_id'), true);
select set_config('request.jwt.claims', json_build_object('sub',current_setting('marsad.test_user_id'),'role','authenticated')::text, true);
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    s_b uuid:=current_setting('marsad.s_b')::uuid;
    y_cur bigint:=current_setting('marsad.y_a_cur')::bigint;
    y_old bigint:=current_setting('marsad.y_a_old')::bigint;
    e_cur bigint:=current_setting('marsad.e_a_cur')::bigint;
    v_domain text[]:=array[
        'teachers','teacher_profiles','teacher_years','teacher_cv_items','upload_requests','documents',
        'events','event_media','event_teacher_links','activities','meetings','meeting_attendees','meeting_decisions',
        'curriculum_plans','curriculum_units','supervision_visits','supervision_actions','achievement_assessments',
        'achievement_assessment_standards','achievement_actions','achievement_action_metrics'
    ];
    v_year text[]:=array[
        'teacher_years','upload_requests','documents','events','meetings','curriculum_plans','supervision_visits','achievement_assessments','activities'
    ];
    t text; v_count integer; v_rows integer; v_blocked boolean;
    v_before timestamptz; v_after timestamptz;
begin
    if (select count(*) from public.schools where id=s_a) <> 1
       or (select count(*) from public.schools where id=s_b) <> 0 then
        raise exception 'S2-D acceptance failed: core school tenant isolation failed';
    end if;
    if (select count(*) from public.academic_years where school_id=s_a) <> 2
       or (select count(*) from public.academic_years where school_id=s_b) <> 0 then
        raise exception 'S2-D acceptance failed: academic-year tenant isolation failed';
    end if;
    if (select count(*) from public.school_settings where school_id=s_a) <> 1
       or (select count(*) from public.school_settings where school_id=s_b) <> 0 then
        raise exception 'S2-D acceptance failed: school settings tenant isolation failed';
    end if;

    foreach t in array v_domain loop
        execute format('select count(*) from public.%I where school_id=$1',t) into v_count using s_a;
        if v_count < 1 then
            raise exception 'S2-D acceptance failed: owner cannot read populated table %', t;
        end if;
        execute format('select count(*) from public.%I where school_id=$1',t) into v_count using s_b;
        if v_count <> 0 then
            raise exception 'S2-D acceptance failed: cross-tenant rows leaked from table %', t;
        end if;
    end loop;

    foreach t in array v_year loop
        execute format('select count(*) from public.%I where school_id=$1 and academic_year_id=$2',t) into v_count using s_a,y_cur;
        if v_count < 1 then raise exception 'S2-D acceptance failed: current-year row missing from %',t; end if;
        execute format('select count(*) from public.%I where school_id=$1 and academic_year_id=$2',t) into v_count using s_a,y_old;
        if v_count < 1 then raise exception 'S2-D acceptance failed: historical-year row missing from %',t; end if;
    end loop;

    select updated_at into v_before from public.events where id=e_cur;
    perform pg_sleep(0.01);
    update public.events set title='S2-D Owner Updated Event' where id=e_cur;
    get diagnostics v_rows = row_count;
    select updated_at into v_after from public.events where id=e_cur;
    if v_rows <> 1 or v_after <= v_before then
        raise exception 'S2-D acceptance failed: owner update/updated_at trigger did not advance';
    end if;

    v_blocked:=false;
    begin
        insert into public.events(school_id,academic_year_id,title,event_type,event_date)
        values(s_b,current_setting('marsad.y_b_cur')::bigint,'SHOULD NOT INSERT','x',date '2090-09-07');
    exception when insufficient_privilege then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: owner crossed tenant boundary on INSERT'; end if;

    v_blocked:=false;
    begin
        insert into public.documents(school_id,academic_year_id,title,category,original_name,size_bytes,storage_provider,status)
        values(s_a,y_cur,'SHOULD NOT INSERT','x','locked.pdf',1,'legacy_local','inbox');
    exception when insufficient_privilege then v_blocked:=true; end;
    if not v_blocked then raise exception 'S2-D acceptance failed: locked document browser write unexpectedly succeeded'; end if;
end $$;

-- 6) Viewer: school-wide reading only, no private/sensitive reading, no writes.
reset role;
update public.school_memberships
set role='viewer', status='active', teacher_id=current_setting('marsad.t_a1')::bigint
where school_id=current_setting('marsad.s_a')::uuid and user_id=current_setting('marsad.test_user_id')::uuid;
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    v_rows integer;
begin
    if (select count(*) from public.events where school_id=s_a) < 2 then raise exception 'S2-D acceptance failed: viewer lost school-wide event read'; end if;
    if (select count(*) from public.teachers where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: viewer saw private teacher data'; end if;
    if (select count(*) from public.documents where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: viewer saw private documents'; end if;
    if (select count(*) from public.upload_requests where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: viewer saw upload token records'; end if;
    if (select count(*) from public.activities where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: viewer saw audit activities'; end if;
    update public.events set title='SHOULD NOT UPDATE' where school_id=s_a;
    get diagnostics v_rows = row_count;
    if v_rows <> 0 then raise exception 'S2-D acceptance failed: viewer received write access'; end if;
end $$;

-- 7) Teacher: school-wide operational reading + self-only private records; still no sensitive manager rows or writes.
reset role;
update public.school_memberships
set role='teacher', status='active', teacher_id=current_setting('marsad.t_a1')::bigint
where school_id=current_setting('marsad.s_a')::uuid and user_id=current_setting('marsad.test_user_id')::uuid;
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    t_a1 bigint:=current_setting('marsad.t_a1')::bigint;
    v_rows integer;
begin
    if (select count(*) from public.events where school_id=s_a) < 2 then raise exception 'S2-D acceptance failed: teacher lost school-wide operational read'; end if;
    if (select count(*) from public.teachers where school_id=s_a) <> 1
       or (select count(*) from public.teachers where school_id=s_a and id=t_a1) <> 1 then
        raise exception 'S2-D acceptance failed: teacher self-only directory rule failed';
    end if;
    if (select count(*) from public.teacher_years where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: teacher self year history rule failed'; end if;
    if (select count(*) from public.documents where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: teacher own document visibility failed'; end if;
    if (select count(*) from public.upload_requests where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: teacher saw manager-sensitive upload requests'; end if;
    if (select count(*) from public.activities where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: teacher saw manager-only activities'; end if;
    update public.events set title='SHOULD NOT UPDATE' where school_id=s_a;
    get diagnostics v_rows = row_count;
    if v_rows <> 0 then raise exception 'S2-D acceptance failed: teacher received write access'; end if;
end $$;

-- 8) Lead teacher: broad private teacher read is allowed, school-wide write remains deliberately denied.
reset role;
update public.school_memberships
set role='lead_teacher', status='active', teacher_id=current_setting('marsad.t_a1')::bigint
where school_id=current_setting('marsad.s_a')::uuid and user_id=current_setting('marsad.test_user_id')::uuid;
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    v_rows integer;
begin
    if (select count(*) from public.teachers where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: lead_teacher private teacher read failed'; end if;
    if (select count(*) from public.documents where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: lead_teacher private document read failed'; end if;
    if (select count(*) from public.upload_requests where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: lead_teacher saw manager-sensitive upload requests'; end if;
    update public.teachers set name='SHOULD NOT UPDATE' where school_id=s_a;
    get diagnostics v_rows = row_count;
    if v_rows <> 0 then raise exception 'S2-D acceptance failed: lead_teacher received school-wide write power'; end if;
end $$;

-- 9) Admin: same-tenant management writes and sensitive reads are allowed.
reset role;
update public.school_memberships
set role='admin', status='active', teacher_id=null
where school_id=current_setting('marsad.s_a')::uuid and user_id=current_setting('marsad.test_user_id')::uuid;
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    y_cur bigint:=current_setting('marsad.y_a_cur')::bigint;
    t_a2 bigint:=current_setting('marsad.t_a2')::bigint;
    v_rows integer;
begin
    if (select count(*) from public.upload_requests where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: admin sensitive upload-request read failed'; end if;
    if (select count(*) from public.activities where school_id=s_a) <> 2 then raise exception 'S2-D acceptance failed: admin audit read failed'; end if;
    insert into public.events(school_id,academic_year_id,title,event_type,event_date)
    values(s_a,y_cur,'S2-D Admin Insert','x',date '2090-09-08');
    update public.teachers set qualification='S2-D Admin Updated' where id=t_a2;
    get diagnostics v_rows = row_count;
    if v_rows <> 1 then raise exception 'S2-D acceptance failed: admin allowed update did not affect target row'; end if;
end $$;

-- 10) Suspended membership must collapse all tenant access regardless of stored role.
reset role;
update public.school_memberships
set role='owner', status='suspended', teacher_id=current_setting('marsad.t_a1')::bigint
where school_id=current_setting('marsad.s_a')::uuid and user_id=current_setting('marsad.test_user_id')::uuid;
set local role authenticated;

do $$
declare
    s_a uuid:=current_setting('marsad.s_a')::uuid;
    v_uid uuid:=current_setting('marsad.test_user_id')::uuid;
begin
    if (select count(*) from public.schools where id=s_a) <> 0 then raise exception 'S2-D acceptance failed: suspended membership can still read school'; end if;
    if (select count(*) from public.events where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: suspended membership can still read domain rows'; end if;
    if (select count(*) from public.teachers where school_id=s_a) <> 0 then raise exception 'S2-D acceptance failed: suspended membership can still read private rows'; end if;
    if (select count(*) from public.profiles where id=v_uid) <> 1 then raise exception 'S2-D acceptance failed: user lost self profile visibility'; end if;
end $$;

reset role;
select 'PASS: S2-D database acceptance and migration readiness' as result;
rollback;
