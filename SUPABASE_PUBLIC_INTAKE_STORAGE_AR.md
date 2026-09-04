# S3-C3B — Public Intake & Supabase Storage

الإصدار: `0.34.0`

## الحدود المعتمدة

- إنشاء الطلب للعام الدراسي الحالي فقط ومن حساب `owner` أو `admin`.
- يولد المتصفح رمزًا عشوائيًا 32 بايت ويحسب SHA-256 محليًا؛ لا يصل إلى قاعدة البيانات إلا الـhash.
- الرفع العام يمر عبر Edge Function باسم `marsad-public-upload` مع `verify_jwt = false` لأن الرمز نفسه capability سرية للطلب.
- Edge Function وحدها تستخدم مفتاح الخادم، ولا يوجد أي Secret/Service Role داخل `src/` أو متغير `VITE_*`.
- Bucket `marsad-documents` خاصة، وحد الملف 25MB.
- بعد رفع Storage تستدعي Edge Function RPC ذريًا لتسجيل الوثيقة وتحويل الطلب إلى `review` وتسجيل النشاط.
- إذا فشل RPC تزال قطعة Storage فورًا لتجنب ملف يتيم.
- فتح وثائق Supabase من لوحة الإدارة يستخدم Signed URL لمدة 300 ثانية؛ سياسة `storage.objects` تسمح SELECT للـowner/admin فقط.
- الرفع المباشر من صفحة الوثائق لم ينتقل في هذه المرحلة.
- Legacy fallback والأعوام التاريخية لم تتغير.

## ترتيب النشر

1. نجاح GitHub Actions كاملاً.
2. تنفيذ migration الخاصة بـS3-C3B مرة واحدة.
3. نشر `supabase/functions/marsad-public-upload/index.ts`.
4. تنفيذ `supabase/tests/s3_c3b_live_acceptance.sql` والتحقق من PASS ثم ROLLBACK.
5. اختبار حي واحد: إنشاء طلب، فتح الرابط دون تسجيل دخول، رفع ملف، ظهور `review`، ثم فتح الوثيقة من الإدارة.
