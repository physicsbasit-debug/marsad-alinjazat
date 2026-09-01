# Database migrations

بدأت migrations التشغيلية في **Phase S2-B1** بعد تجميد تصميم PostgreSQL في S2-A.

الموجود حاليًا:

```text
20260901120000_s2_b1_core_identity_tenancy.sql
```

ينشئ فقط `schools`, `profiles`, `school_memberships`, و`academic_years`. لا تنقل هذه migration بيانات SQLite ولا تفعل RLS؛ سياسات RLS مؤجلة إلى S2-C.
