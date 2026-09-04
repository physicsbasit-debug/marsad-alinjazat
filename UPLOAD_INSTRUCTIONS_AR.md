# تعليمات رفع مرصد الإنجازات v0.24.1 — S2-D Fix 1

نقطة الأساس: **v0.24.0 / S2-D package uploaded; live acceptance exposed a fixture-count defect**.

1. ارفع محتويات `changed_files_only` فوق `main`.
2. تأكد من وصول `.github/workflows/quality-pages.yml` والنسخة المرئية المطابقة.
3. انتظر GitHub Actions GREEN، بما في ذلك `S2-D Fix 1 acceptance fixture cleanup`.
4. **لا تشغّل أي Migration في Supabase**؛ هذا الإصدار لا يحتوي Migration جديدة ولا يغير RLS/Schema.
5. أبقِ مستخدم Auth واحدًا موجودًا وله صف مطابق في `public.profiles`.
6. شغّل `supabase/tests/s2_d_live_acceptance.sql` المصحح فقط.
7. النتيجة المطلوبة: `PASS: S2-D database acceptance and migration readiness`.

نجاحه يسمح بالانتقال إلى Dry Run مضبوط لنقل SQLite فقط. لا يعني قطع FastAPI/SQLite بعد.
