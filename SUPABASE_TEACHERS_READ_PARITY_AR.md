# S3-B1 — قراءة المعلمين من Supabase وبوابة Parity

الإصدار: **v0.28.0**

## الهدف

إنشاء أول Repository مجالّي يقرأ بيانات المعلمين من Supabase عبر RLS، باستخدام سياق S3-A فقط:

`Auth session → school_id + academic_year_id → teachers + teacher_years + teacher_profiles + teacher_cv_items`

## ما تفعله المرحلة

- تقرأ `teachers` داخل المدرسة الحالية.
- تقرأ `teacher_years` للعام الحالي فقط وبحالة `is_active=true`.
- تربط الملف المهني وبنود السيرة بالمعلم.
- تتحقق من عدم تسرب سجل من مدرسة أو عام آخر.
- ترفض معرفات bigint غير الآمنة للمتصفح بدل تحويلها بصمت.
- توفر دالة Parity مستقلة لمقارنة هوية المعلمين عند توفر مصدر Legacy حقيقي.

## ما لا تفعله

- لا Migration جديدة.
- لا تغيير RLS.
- لا INSERT/UPDATE/DELETE/UPSERT في مجال المعلمين.
- لا تغيّر `api.ts`.
- لا تغيّر صفحة `Teachers.tsx` التشغيلية إلى Supabase.
- لا تعتبر بيانات GitHub Preview الوهمية مصدر Legacy صالحًا للمقارنة.
- لا تزرع معلمين وهميين إذا كان Supabase فارغًا.

## بوابة القبول الحي

بعد GitHub Actions GREEN افتح:

`https://physicsbasit-debug.github.io/marsad-alinjazat/?teachers-check=1`

سجّل الدخول بحساب Supabase الحقيقي إذا لم تكن الجلسة محفوظة.

النجاح المتوقع:

`PASS: S3-B1 Teachers Read Repository`

إذا كانت قاعدة المعلمين فارغة، تظهر **قراءة فارغة صحيحة**. هذا PASS لمسار القراءة فقط، وليس إذنًا للـCutover.

## Parity Gate

في هذه المرحلة، إذا لم يوجد مصدر Legacy إنتاجي حقيقي يمكن مقارنته، تبقى البوابة:

`NOT ESTABLISHED`

وهذا مقصود. أي Cutover لصفحة المعلمين يبقى محظورًا حتى تمر مقارنة حقيقية أو يُعتمد مسار تشغيل جديد خالٍ من بيانات Legacy بمرحلة لاحقة صريحة.
