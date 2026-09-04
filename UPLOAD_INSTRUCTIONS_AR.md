# تعليمات رفع مرصد الإنجازات v0.26.0 — S2-E2

1. ارفع محتويات حزمة **Changed Files Only** إلى جذر مستودع GitHub.
2. تأكد أن الملفين التاليين رُفعا معًا وبنفس المحتوى:
   - `.github/workflows/quality-pages.yml`
   - `GITHUB_WORKFLOW_VISIBLE/quality-pages.yml`
3. انتظر نجاح `Quality & Live Preview` وظهور خطوة:
   `S2-E2 production tenant bootstrap contract`.
4. لا تشغّل أي Migration جديدة؛ S2-E2 لا تضيف Migration.
5. بعد GitHub GREEN شغّل ملف **Live Bootstrap** المخصص الذي يُسلّم خارج المستودع في Supabase SQL Editor.
6. النتيجة المطلوبة أولًا:
   `PASS: S2-E2 production tenant bootstrap`
7. بعدها شغّل ملف **Live RLS Acceptance** المخصص.
8. النتيجة المطلوبة:
   `PASS: S2-E2 tenant RLS acceptance`

لا تُرفع ملفات Live الشخصية إلى GitHub لأنها تحتوي معرف المدرسة/بريد المالك التشغيلي.


## S3-A / v0.27.0

ارفع Changed Files Only فوق `main` وانتظر GitHub Actions GREEN. بعد ذلك أضف Repository Variables: `VITE_SUPABASE_URL` و`VITE_SUPABASE_PUBLISHABLE_KEY`، ثم أعد تشغيل Workflow وافتح GitHub Pages مع `?auth-check=1`. لا توجد Migration أو SQL مطلوبان في هذه المرحلة.
