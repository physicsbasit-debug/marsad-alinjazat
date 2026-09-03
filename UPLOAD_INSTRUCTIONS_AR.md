# تعليمات رفع مرصد الإنجازات v0.21.0 — Phase S2-B5

1. ارفع محتويات `changed_files_only` فوق `main` الحالي بعد **S2-B4 LIVE GREEN**.
2. تأكد أن `.github/workflows/quality-pages.yml` وصل. توجد نسخة مرئية مطابقة في `GITHUB_WORKFLOW_VISIBLE/quality-pages.yml`.
3. انتظر GitHub Actions وتحقق من نجاح S0 وS1 وS2-A وS2-B1 وS2-B2 وS2-B3 وS2-B4 وS2-B5 وpytest وHTTP E2E.
4. إذا أصبح GitHub أخضر فقط، شغّل يدويًا في Supabase SQL Editor: `supabase/migrations/20260902090000_s2_b5_schema_hardening.sql`.
5. لا تعِد تشغيل migrations القديمة S2-B1..S2-B4.
6. بعد نجاح migration الخامسة شغّل `supabase/tests/s2_b5_live_acceptance.sql`.
7. النتيجة المطلوبة: `PASS: S2-B5 final schema acceptance`.

S2-B5 لا تنقل بيانات ولا تفعل Auth أو Policies. auto-RLS الموجود من Supabase لا يحتاج تعطيلًا؛ الاختبار يطلب فقط أن تبقى browser grants والسياسات صفرًا قبل S2-C.


### S2-B5 Fix 1 — تصحيح updated_at
كشف اختبار Supabase الحي أن `statement_timestamp()` ثابت طوال SQL statement واحد، لذلك قد لا يتقدم `updated_at` عند تنفيذ أكثر من عملية داخل statement واحد. الإصدار 0.21.1 يضيف Migration تصحيحية جديدة تستبدل الدالة فقط لتستخدم `clock_timestamp()`، مع إبقاء Migration S2-B5 الأصلية والـ22 Trigger دون تعديل.
