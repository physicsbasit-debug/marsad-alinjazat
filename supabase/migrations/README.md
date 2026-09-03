# Database migrations

بدأت migrations التشغيلية في **Phase S2-B1** بعد تجميد تصميم PostgreSQL في S2-A.

الموجود حاليًا:

```text
20260901120000_s2_b1_core_identity_tenancy.sql
20260901190000_s2_b2_teachers_domain.sql
20260901210000_s2_b3_operational_domains.sql
20260902080000_s2_b4_content_intake_domains.sql
20260902090000_s2_b5_schema_hardening.sql
20260903080000_s2_b5_fix1_updated_at_clock.sql
20260903100000_s2_c1_security_foundation.sql
20260903123000_s2_c2_domain_rls_baseline.sql
```

- S2-B1: `schools`, `profiles`, `school_memberships`, `academic_years`.
- S2-B2: مجال المعلمين وإكمال same-school FK للعضوية.
- S2-B3: الاجتماعات والتخطيط والإشراف والتحصيل، 11 جدولًا.
- S2-B4: الإعدادات غير السرية والطلبات والوثائق والفعاليات والوسائط وروابط المعلمين وسجل النشاط، 7 جداول.
- S2-B5: إغلاق المخطط، 22 trigger لـ`updated_at` وثلاثة فهارس نهائية واختبار قبول شامل. لا ينشئ جدول مجال جديدًا.

سلسلة S2-B تمثل كل **الجداول الـ26** و**299 عمودًا** في عقد S2-A. لا تنقل هذه migrations بيانات SQLite أو bytes التخزين، ولا تنشئ RLS policies؛ سياسات التفويض تبدأ في S2-C. مشروع Supabase قد يفعّل RLS تلقائيًا عبر إعداد خارجي، ولا يُعطّل ذلك هنا ما دامت browser grants والسياسات صفرًا.

### S2-B5 Fix 1 — updated_at clock semantics

- `20260903080000_s2_b5_fix1_updated_at_clock.sql` replaces only `public.set_row_updated_at()` so it uses `clock_timestamp()` rather than `statement_timestamp()`.
- The original S2-B5 migration remains unchanged because it has already been applied to the live Supabase project.
- The 22 existing triggers are reused; no trigger/table/index is recreated.

### S2-C1 — Security foundation

`20260903100000_s2_c1_security_foundation.sql` starts Auth/RLS on the five core identity/tenancy tables only. It creates the non-exposed `private` policy-helper schema, the Auth->profile trigger, targeted authenticated grants, and 11 RLS policies. The remaining 21 domain tables stay closed until S2-C2.

### S2-C2 — Domain RLS baseline

`20260903123000_s2_c2_domain_rls_baseline.sql` enables RLS on the remaining 21 domain tables, adds 58 least-privilege policies and one private teacher-record visibility helper. Five trusted/storage-coupled tables remain browser-write locked. Runtime stays FastAPI/SQLite.
