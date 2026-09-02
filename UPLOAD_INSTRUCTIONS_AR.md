# تعليمات رفع مرصد الإنجازات v0.20.0 — Phase S2-B4

1. ارفع محتويات `changed_files_only` فوق `main` الحالي بعد S2-B3 LIVE GREEN.
2. تأكد أن الملفات المخفية وصلت، خصوصًا `.github/workflows/quality-pages.yml` و`.gitignore` و`.env.example`. توجد نسخ مرئية احتياطية كما في المراحل السابقة.
3. انتظر GitHub Actions وتحقق من نجاح S0 وS1 وS2-A وS2-B1 وS2-B2 وS2-B3 وS2-B4 وpytest وHTTP E2E.
4. إذا أصبح GitHub أخضر فقط، شغّل `supabase/migrations/20260902080000_s2_b4_content_intake_domains.sql` يدويًا في Supabase SQL Editor.
5. لا تعِد تشغيل migrations القديمة.
6. بعد نجاح migration الرابعة شغّل `supabase/tests/s2_b4_live_acceptance.sql`.
7. النتيجة المطلوبة: `PASS: S2-B4 live acceptance`.

لا تعطل auto-RLS إذا ظهر على الجداول الجديدة. اختبار القبول يتأكد من عدم وجود Policies ومن بقاء browser grants = 0 حتى S2-C.
