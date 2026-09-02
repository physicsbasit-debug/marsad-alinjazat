# تعليمات رفع مرصد الإنجازات v0.19.0 — Phase S2-B3

1. ارفع محتويات `changed_files_only` فوق `main` الحالي بعد S2-B2 GREEN ونجاح Live Acceptance.
2. تأكد من وجود migration الجديدة: `supabase/migrations/20260901210000_s2_b3_operational_domains.sql`.
3. انتظر GitHub Actions وتحقق من نجاح S0, S1, S2-A, S2-B1, S2-B2, S2-B3, pytest وHTTP E2E.
4. لا تشغل SQL الجديد على Supabase قبل أخضر GitHub.
5. بعد الأخضر شغّل migration الثالثة فقط في Supabase SQL Editor.
6. بعدها شغّل `supabase/tests/s2_b3_live_acceptance.sql` وتأكد من ظهور `PASS: S2-B3 live acceptance`.

لا تضف RLS ولا مفاتيح Supabase إلى الواجهة ولا تنقل بيانات SQLite في هذه المرحلة.
