# تعليمات رفع مرصد الإنجازات v0.24.0 — Phase S2-D

نقطة الأساس: **v0.23.0 / S2-C LIVE GREEN**.

1. ارفع محتويات `changed_files_only` فوق `main`.
2. تأكد من وصول `.github/workflows/quality-pages.yml` والنسخة المرئية المطابقة.
3. انتظر GitHub Actions GREEN. المطلوب نجاح جميع الحراس حتى `S2-D` وHTTP E2E.
4. **لا تشغّل أي Migration في Supabase**؛ S2-D Acceptance-only ولا تضيف SQL migration.
5. أبقِ مستخدم Auth واحدًا موجودًا وله صف مطابق في `public.profiles`.
6. شغّل `supabase/tests/s2_d_live_acceptance.sql` فقط.
7. النتيجة المطلوبة: `PASS: S2-D database acceptance and migration readiness`.

## معنى الإغلاق

نجاح S2-D يسمح بالانتقال إلى **Dry Run لنقل بيانات SQLite** مع reconciliation وعدّ الصفوف. لا يسمح بعد بقطع FastAPI/SQLite أو نقل bytes الملفات أو تشغيل Public Upload على Supabase.

التفاصيل: `SUPABASE_DATABASE_ACCEPTANCE_AR.md` و`supabase/schema/s2_d_data_migration_manifest.json`.
