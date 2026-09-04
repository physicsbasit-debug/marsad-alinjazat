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
