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


## S3-B1 v0.28.0
- ارفع Changed Files Only فوق main.
- انتظر GitHub Actions GREEN.
- لا SQL ولا Migration.
- افتح `?teachers-check=1` على GitHub Pages.
- المطلوب `PASS: S3-B1 Teachers Read Repository`.
- `NOT ESTABLISHED` في Parity Gate لا يعد فشلًا في S3-B1؛ معناه أن Cutover ما زال محظورًا.

## S3-B2 v0.29.0
- ارفع Changed Files Only فوق `main`.
- انتظر GitHub Actions GREEN ونجاح خطوة `S3-B2 teachers write repository and RLS acceptance`.
- شغّل Migration `supabase/migrations/20260904130000_s3_b2_teacher_write_foundation.sql` كاملة في Supabase SQL Editor.
- بعد نجاحها شغّل `supabase/tests/s3_b2_live_acceptance.sql`.
- المطلوب: `PASS: S3-B2 teacher write RLS acceptance`.
- اختبار القبول ينتهي بـ`ROLLBACK;` ولا يترك مدارس أو معلمين تجريبيين.
- لا Cutover لواجهة المعلمين في S3-B2؛ `Teachers.tsx` و`api.ts` يظلان على Legacy حتى بوابة مستقلة لاحقة.


## S3-B2R1 v0.29.1
1. ارفع حزمة Changed Files Only فوق `main`.
2. انتظر GitHub Actions GREEN وفيها `S3-B2R1 teacher write ambiguity correction`.
3. شغّل Migration التصحيحية `20260904143000_s3_b2_r1_teacher_write_ambiguity_correction.sql` في Supabase.
4. شغّل `supabase/tests/s3_b2_r1_live_acceptance.sql`.
5. المطلوب: `PASS: S3-B2R1 teacher write ambiguity correction`.
