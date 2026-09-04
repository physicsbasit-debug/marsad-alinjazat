# تعليمات رفع S3-C2 — v0.32.0

1. ارفع محتويات حزمة `changed_files_only` فوق الفرع `main`.
2. تأكد من رفع `.env.example` و`.github/workflows/quality-pages.yml`. النسختان المرئيتان موجودتان في `ENV_EXAMPLE_VISIBLE.txt` و`GITHUB_WORKFLOW_VISIBLE/quality-pages.yml` للحماية من تجاهل الملفات المخفية.
3. انتظر `Quality & Live Preview` حتى تصبح `quality` و`build-preview` و`deploy-preview` خضراء.
4. بعد GitHub GREEN فقط، شغّل Migration S3-C2 مرة واحدة في Supabase SQL Editor.
5. شغّل بعدها `supabase/tests/s3_c2_live_acceptance.sql` وتأكد من ظهور `PASS: S3-C2 supervision write RLS acceptance`.
6. افتح GitHub Pages ثم «الإشراف والمتابعة» واختبر إنشاء وتعديل زيارة وإجراء متابعة، ثم أعد تحميل الصفحة.
