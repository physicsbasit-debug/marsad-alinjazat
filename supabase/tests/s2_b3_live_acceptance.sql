-- Marsad Al-Injazat — S2-B3 live acceptance (run AFTER the S2-B3 migration)
-- Safe for Supabase SQL Editor. All test rows are removed by ROLLBACK.

begin;

do $$
declare
    v_count integer;
    v_def text;
begin
    select count(*) into v_count
    from information_schema.tables
    where table_schema = 'public'
      and table_name in (
        'meetings','meeting_attendees','meeting_decisions',
        'curriculum_plans','curriculum_units',
        'supervision_visits','supervision_actions',
        'achievement_assessments','achievement_assessment_standards',
        'achievement_actions','achievement_action_metrics'
      );
    if v_count <> 11 then
        raise exception 'S2-B3 acceptance failed: expected 11 operational tables, found %', v_count;
    end if;

    select count(*) into v_count
    from information_schema.role_table_grants
    where table_schema = 'public'
      and table_name in (
        'meetings','meeting_attendees','meeting_decisions',
        'curriculum_plans','curriculum_units',
        'supervision_visits','supervision_actions',
        'achievement_assessments','achievement_assessment_standards',
        'achievement_actions','achievement_action_metrics'
      )
      and grantee in ('anon','authenticated');
    if v_count <> 0 then
        raise exception 'S2-B3 acceptance failed: browser roles still have % grants', v_count;
    end if;

    select count(*) into v_count
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname in (
        'meetings','meeting_attendees','meeting_decisions',
        'curriculum_plans','curriculum_units',
        'supervision_visits','supervision_actions',
        'achievement_assessments','achievement_assessment_standards',
        'achievement_actions','achievement_action_metrics'
      )
      and c.relrowsecurity;
    if v_count <> 0 then
        raise exception 'S2-B3 acceptance failed: RLS was enabled before S2-C on % tables', v_count;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.meetings'::regclass
      and conname = 'meetings_academic_year_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, academic_year_id)%'
       or v_def not ilike '%REFERENCES academic_years(school_id, id)%' then
        raise exception 'S2-B3 acceptance failed: meeting/year same-school FK missing or wrong: %', v_def;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.meeting_decisions'::regclass
      and conname = 'meeting_decisions_responsible_teacher_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, responsible_teacher_id)%'
       or v_def not ilike '%REFERENCES teachers(school_id, id)%'
       or v_def not ilike '%ON DELETE SET NULL (responsible_teacher_id)%' then
        raise exception 'S2-B3 acceptance failed: optional responsible teacher FK is wrong: %', v_def;
    end if;
end $$;

do $$
declare
    s1 uuid;
    s2 uuid;
    y1 bigint;
    y2 bigint;
    t1 bigint;
    t2 bigint;
    t3 bigint;
    t_delete bigint;
    m1 bigint;
    d_delete bigint;
    p1 bigint;
    v1 bigint;
    a1 bigint;
    action1 bigint;
    action2 bigint;
    v_nullable bigint;
begin
    insert into public.schools(name) values ('S2-B3 قبول مدرسة 1') returning id into s1;
    insert into public.schools(name) values ('S2-B3 قبول مدرسة 2') returning id into s2;

    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values (s1,'2097/2098',2097,2098,false) returning id into y1;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values (s2,'2097/2098',2097,2098,false) returning id into y2;

    insert into public.teachers(school_id,name) values (s1,'معلم S2-B3 أ') returning id into t1;
    insert into public.teachers(school_id,name) values (s1,'معلم S2-B3 ب') returning id into t2;
    insert into public.teachers(school_id,name) values (s2,'معلم S2-B3 مدرسة أخرى') returning id into t3;
    insert into public.teachers(school_id,name) values (s1,'معلم S2-B3 للحذف') returning id into t_delete;

    insert into public.meetings(school_id,academic_year_id,title,meeting_date,status)
    values (s1,y1,'اجتماع قبول S2-B3',date '2097-09-10','held') returning id into m1;

    insert into public.meeting_attendees(school_id,meeting_id,teacher_id,attendance_status)
    values (s1,m1,t1,'present');

    insert into public.meeting_decisions(school_id,meeting_id,title,responsible_teacher_id,status)
    values (s1,m1,'قرار اختبار',t2,'in_progress');

    insert into public.meeting_decisions(school_id,meeting_id,title,responsible_teacher_id,status)
    values (s1,m1,'قرار حذف مسؤول',t_delete,'new') returning id into d_delete;

    delete from public.teachers where id = t_delete;
    select responsible_teacher_id into v_nullable
    from public.meeting_decisions where id = d_delete;
    if v_nullable is not null then
        raise exception 'S2-B3 acceptance failed: optional responsible_teacher_id did not SET NULL';
    end if;

    insert into public.curriculum_plans(
        school_id,academic_year_id,title,subject,grade,term,owner_teacher_id,status
    ) values (s1,y1,'خطة اختبار','العلوم','10','الأول',t1,'active') returning id into p1;

    insert into public.curriculum_units(
        school_id,plan_id,title,sequence,progress_percent,status,responsible_teacher_id
    ) values (s1,p1,'وحدة اختبار',1,50,'in_progress',t2);

    insert into public.supervision_visits(
        school_id,academic_year_id,teacher_id,visit_date,status
    ) values (s1,y1,t1,date '2097-10-01','completed') returning id into v1;

    insert into public.supervision_actions(
        school_id,visit_id,title,responsible_teacher_id,status
    ) values (s1,v1,'إجراء إشرافي',t2,'new');

    insert into public.achievement_assessments(
        school_id,academic_year_id,title,subject,grade,assessment_date,term,teacher_id,
        max_score,student_count,average_score,highest_score,lowest_score,
        mastery_threshold_pct,mastered_count,near_mastery_count,intervention_count,status
    ) values (
        s1,y1,'تقويم قبول','الفيزياء','10',date '2097-11-01','الأول',t1,
        40,10,30,40,10,60,5,2,3,'recorded'
    ) returning id into a1;

    insert into public.achievement_assessment_standards(
        assessment_id,school_id,mastery_reference_source,mastery_reference_year
    ) values (a1,s1,'وثيقة اختبار','2097/2098');

    insert into public.achievement_actions(
        school_id,assessment_id,action_type,title,responsible_teacher_id,status
    ) values (s1,a1,'remedial','تدخل علاجي',t2,'in_progress') returning id into action1;

    insert into public.achievement_action_metrics(
        action_id,school_id,metric_name,unit,direction,baseline_value,target_value
    ) values (action1,s1,'نسبة الإتقان','%','higher_better',50,70);

    insert into public.achievement_actions(
        school_id,assessment_id,action_type,title,status
    ) values (s1,a1,'followup','متابعة قياس','new') returning id into action2;

    begin
        insert into public.meetings(school_id,academic_year_id,title,meeting_date)
        values (s1,y2,'سنة من مدرسة أخرى',date '2097-09-11');
        raise exception 'expected cross-school academic year rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.meeting_attendees(school_id,meeting_id,teacher_id)
        values (s1,m1,t3);
        raise exception 'expected cross-school attendee teacher rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.curriculum_plans(
            school_id,academic_year_id,title,subject,grade,term,owner_teacher_id
        ) values (s1,y1,'خطة خاطئة','العلوم','10','الأول',t3);
        raise exception 'expected cross-school plan owner rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.curriculum_units(
            school_id,plan_id,title,progress_percent
        ) values (s1,p1,'نسبة خاطئة',101);
        raise exception 'expected curriculum progress check rejection';
    exception when check_violation then null;
    end;

    begin
        insert into public.supervision_visits(
            school_id,academic_year_id,teacher_id,visit_date
        ) values (s1,y1,t3,date '2097-10-02');
        raise exception 'expected cross-school supervision teacher rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        delete from public.teachers where id = t1;
        raise exception 'expected supervised teacher delete restriction';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.achievement_assessments(
            school_id,academic_year_id,title,subject,grade,assessment_date,term,
            max_score,student_count,mastered_count,near_mastery_count,intervention_count
        ) values (
            s1,y1,'تجميع خاطئ','الفيزياء','10',date '2097-11-02','الأول',
            40,10,6,3,2
        );
        raise exception 'expected assessment bucket total check rejection';
    exception when check_violation then null;
    end;

    begin
        insert into public.achievement_action_metrics(
            action_id,school_id,metric_name,direction,baseline_value,target_value,outcome_value
        ) values (action2,s1,'قياس خاطئ','higher_better',10,20,18);
        raise exception 'expected metric measured_at/outcome consistency rejection';
    exception when check_violation then null;
    end;
end $$;

select 'PASS: S2-B3 live acceptance' as result;
rollback;
