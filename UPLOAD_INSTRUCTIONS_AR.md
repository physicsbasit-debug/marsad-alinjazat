# تعليمات رفع مرصد الإنجازات v0.23.0 — Phase S2-C2

نقطة الأساس: **v0.22.0 / S2-C1 LIVE GREEN**.

1. ارفع محتويات `changed_files_only` فوق `main`.
2. تأكد من وصول `.github/workflows/quality-pages.yml` والنسخة المرئية المطابقة.
3. انتظر GitHub Actions GREEN. المطلوب نجاح جميع الحراس حتى S2-C2 وHTTP E2E.
4. بعد الأخضر فقط شغّل `supabase/migrations/20260903123000_s2_c2_domain_rls_baseline.sql`.
5. لا تعِد تشغيل S2-C1 أو أي migration سابقة.
6. أبقِ مستخدم Auth الذي استُخدم في S2-C1 حتى يكتمل اختبار C2.
7. شغّل `supabase/tests/s2_c2_live_acceptance.sql`.
8. النتيجة المطلوبة: `PASS: S2-C2 domain RLS baseline acceptance`.

## حدود المرحلة

- Runtime ما زال FastAPI/SQLite.
- لا نقل بيانات SQLite.
- لا Storage policies أو bytes ملفات.
- لا public upload cutover.
- لا browser write على teacher_years/upload_requests/documents/event_media/activities.
- lead_teacher قراءة موسعة لكن لا كتابة مدرسية شاملة قبل وجود عزل قسم/مادة.

التفاصيل: `SUPABASE_DOMAIN_RLS_BASELINE_AR.md`.
