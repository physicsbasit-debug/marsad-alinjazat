# Database migrations

بدأت migrations التشغيلية في **Phase S2-B1** بعد تجميد تصميم PostgreSQL في S2-A.

الموجود حاليًا:

```text
20260901120000_s2_b1_core_identity_tenancy.sql
20260901190000_s2_b2_teachers_domain.sql
```

- S2-B1 ينشئ `schools`, `profiles`, `school_memberships`, و`academic_years`.
- S2-B2 ينشئ `teachers`, `teacher_profiles`, `teacher_years`, و`teacher_cv_items` ويكمل FK العضوية إلى المعلم داخل المدرسة نفسها.

لا تنقل هذه migrations بيانات SQLite ولا تفعل RLS؛ سياسات RLS مؤجلة إلى S2-C.
