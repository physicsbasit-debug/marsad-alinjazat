# تعليمات رفع مرصد الإنجازات v0.22.0 — Phase S2-C1

نقطة الأساس: **v0.21.1 / S2-B DATABASE SCHEMA COMPLETE + LIVE GREEN**.

1. ارفع محتويات `changed_files_only` فوق `main` الحالي.
2. تأكد من وصول `.github/workflows/quality-pages.yml`. توجد نسخة مرئية مطابقة في `GITHUB_WORKFLOW_VISIBLE/quality-pages.yml` لحماية الرفع من الهاتف.
3. انتظر GitHub Actions. المطلوب نجاح: pytest، S0، S1، S2-A، S2-B1..B5، S2-B5 Fix 1، S2-C1، وHTTP E2E.
4. بعد GitHub GREEN فقط شغّل في Supabase SQL Editor:
   `supabase/migrations/20260903100000_s2_c1_security_foundation.sql`
5. لا تعِد تشغيل أي migration من S2-B.
6. بعد نجاح migration افتح **Authentication > Users** وأنشئ مستخدم اختبار مؤقتًا واحدًا. لا تدخل في `auth.users` يدويًا من SQL.
7. شغّل:
   `supabase/tests/s2_c1_live_acceptance.sql`
8. النتيجة المطلوبة:
   `PASS: S2-C1 security foundation acceptance`
9. بعد PASS يمكن حذف مستخدم الاختبار المؤقت من شاشة Authentication > Users.

## حدود المرحلة

- لا تحويل لمسار React إلى Supabase بعد.
- لا نقل بيانات SQLite.
- لا Storage policies أو bytes ملفات.
- لا browser grants للجداول الـ21 غير الأساسية.
- لا كتابة مباشرة على `school_memberships` حتى للـowner/admin.
- لا دور أمني مأخوذ من `user_metadata`.

التفاصيل الأمنية: `SUPABASE_SECURITY_FOUNDATION_AR.md`.
