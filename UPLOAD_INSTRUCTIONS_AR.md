# تعليمات رفع مرصد الإنجازات v0.18.0 — Phase S2-B2

1. ارفع محتويات `changed_files_only` فوق `main` الحالي بعد S2-B1 GREEN.
2. تأكد أن migration الجديدة ظهرت داخل `supabase/migrations/20260901190000_s2_b2_teachers_domain.sql`.
3. انتظر GitHub Actions وتحقق من نجاح S0, S1, S2-A, S2-B1, S2-B2, pytest وHTTP E2E.
4. لا تشغل SQL الجديد على Supabase قبل أخضر GitHub.
5. بعد الأخضر: شغّل migration الثانية فقط على مشروع Supabase التطويري الحالي.
6. بعدها شغّل `supabase/tests/s2_b2_live_acceptance.sql`.

لا تضف RLS ولا مفاتيح Supabase إلى الواجهة ولا تنقل بيانات SQLite في هذه المرحلة.
