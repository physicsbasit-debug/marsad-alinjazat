-- Marsad Al-Injazat — S2-B2 live acceptance (run AFTER the S2-B2 migration)
-- Safe for the Supabase SQL Editor. Test records are removed by ROLLBACK.

begin;

do $$
declare
    v_count integer;
    v_def text;
begin
    select count(*) into v_count
    from information_schema.tables
    where table_schema = 'public'
      and table_name in ('teachers','teacher_profiles','teacher_years','teacher_cv_items');
    if v_count <> 4 then
        raise exception 'S2-B2 acceptance failed: expected 4 teacher tables, found %', v_count;
    end if;

    select count(*) into v_count
    from information_schema.role_table_grants
    where table_schema = 'public'
      and table_name in ('teachers','teacher_profiles','teacher_years','teacher_cv_items')
      and grantee in ('anon','authenticated');
    if v_count <> 0 then
        raise exception 'S2-B2 acceptance failed: browser roles still have % grants', v_count;
    end if;

    select pg_get_constraintdef(oid) into v_def
    from pg_constraint
    where conrelid = 'public.school_memberships'::regclass
      and conname = 'school_memberships_teacher_fk';
    if v_def is null
       or v_def not ilike '%FOREIGN KEY (school_id, teacher_id)%'
       or v_def not ilike '%REFERENCES teachers(school_id, id)%' then
        raise exception 'S2-B2 acceptance failed: membership same-school teacher FK is missing or wrong: %', v_def;
    end if;
end $$;

do $$
declare
    s1 uuid;
    s2 uuid;
    y1 bigint;
    t1 bigint;
    t2 bigint;
begin
    insert into public.schools(name) values ('S2-B2 قبول مدرسة 1') returning id into s1;
    insert into public.schools(name) values ('S2-B2 قبول مدرسة 2') returning id into s2;
    insert into public.academic_years(school_id,label,start_year,end_year,is_current)
    values (s1,'2098/2099',2098,2099,false) returning id into y1;
    insert into public.teachers(school_id,name) values (s1,'معلم اختبار S2-B2 أ') returning id into t1;
    insert into public.teachers(school_id,name) values (s1,'معلم اختبار S2-B2 ب') returning id into t2;

    insert into public.teacher_profiles(teacher_id,school_id,employee_number,school_join_year)
    values (t1,s1,'S2B2-TEST-1',2020);

    insert into public.teacher_years(school_id,academic_year_id,teacher_id,subject,experience_years,workload)
    values (s1,y1,t1,'العلوم',10,20);

    insert into public.teacher_cv_items(school_id,teacher_id,item_type,title,start_year,end_year)
    values (s1,t1,'course','دورة اختبار',2020,2021);

    begin
        insert into public.teacher_years(school_id,academic_year_id,teacher_id,experience_years)
        values (s1,y1,t2,61);
        raise exception 'expected experience_years constraint rejection';
    exception when check_violation then null;
    end;

    begin
        insert into public.teacher_profiles(teacher_id,school_id,employee_number)
        values (t2,s2,'S2B2-WRONG-SCHOOL');
        raise exception 'expected cross-school teacher profile FK rejection';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.teacher_profiles(teacher_id,school_id,employee_number)
        values (t2,s1,'S2B2-TEST-1');
        raise exception 'expected employee number uniqueness rejection';
    exception when unique_violation then null;
    end;

    begin
        insert into public.teacher_cv_items(school_id,teacher_id,item_type,title,start_year,end_year)
        values (s1,t2,'course','ترتيب سنوات خاطئ',2025,2024);
        raise exception 'expected CV year-order constraint rejection';
    exception when check_violation then null;
    end;
end $$;

select 'PASS: S2-B2 live acceptance' as result;
rollback;
