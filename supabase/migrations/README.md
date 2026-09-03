# Database migrations

بدأت migrations التشغيلية في **Phase S2-B1** بعد تجميد تصميم PostgreSQL في S2-A.

الموجود حاليًا:

```text
20260901120000_s2_b1_core_identity_tenancy.sql
20260901190000_s2_b2_teachers_domain.sql
20260901210000_s2_b3_operational_domains.sql
20260902080000_s2_b4_content_intake_domains.sql
20260902090000_s2_b5_schema_hardening.sql
```

- S2-B1: `schools`, `profiles`, `school_memberships`, `academic_years`.
- S2-B2: مجال المعلمين وإكمال same-school FK للعضوية.
- S2-B3: الاجتماعات والتخطيط والإشراف والتحصيل، 11 جدولًا.
- S2-B4: الإعدادات غير السرية والطلبات والوثائق والفعاليات والوسائط وروابط المعلمين وسجل النشاط، 7 جداول.
- S2-B5: إغلاق المخطط، 22 trigger لـ`updated_at` وثلاثة فهارس نهائية واختبار قبول شامل. لا ينشئ جدول مجال جديدًا.

سلسلة S2-B تمثل كل **الجداول الـ26** و**299 عمودًا** في عقد S2-A. لا تنقل هذه migrations بيانات SQLite أو bytes التخزين، ولا تنشئ RLS policies؛ سياسات التفويض تبدأ في S2-C. مشروع Supabase قد يفعّل RLS تلقائيًا عبر إعداد خارجي، ولا يُعطّل ذلك هنا ما دامت browser grants والسياسات صفرًا.
