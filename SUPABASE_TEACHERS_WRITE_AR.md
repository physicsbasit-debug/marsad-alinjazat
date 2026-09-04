# S3-B2 — Teachers Write Repository & RLS Acceptance

الإصدار: **v0.29.0**

## الهدف

تهيئة كتابة مجال المعلمين في Supabase قبل أي تحويل لواجهة المعلمين التشغيلية. تبقى `Teachers.tsx` و`src/lib/api.ts` على FastAPI/SQLite في هذه المرحلة.

## لماذا توجد Migration في S3-B2؟

في S2-C2 كان جدول `teacher_years` ضمن الجداول المقفلة للكتابة المباشرة من المتصفح. إنشاء معلم في النموذج الجديد يحتاج كتابة ذرية في:

- `teachers`
- `teacher_years`

وتحديث الملف المهني يحتاج أيضًا:

- `teacher_profiles`

لذلك تضيف S3-B2 Migration محدودة بدل محاولة الالتفاف على RLS من الواجهة.

## ما الذي تفتحه Migration؟

- `INSERT` و`UPDATE` على أعمدة `teacher_years` اللازمة فقط.
- سياسات RLS جديدة لدوري `owner` و`admin` فقط.
- لا `DELETE` للمعلمين أو `teacher_years`.
- لا كتابة لـ`lead_teacher`.
- لا صلاحية `anon`.

## الكتابة الذرية

تضيف Migration دالتين عامتين عبر Supabase RPC:

- `marsad_create_teacher_v1`
- `marsad_update_teacher_v1`

كلتاهما `SECURITY INVOKER`، لذلك صلاحيات المستخدم وسياسات RLS الحالية تبقى هي المرجع. لا تستخدم Service Role في المتصفح.

### create

يحاول الربط بهوية معلم موجودة بالبريد أولًا، ثم الاسم + المادة من سجلات `teacher_years`. إذا كانت الهوية جديدة ينشئ `teachers` ثم `teacher_years` داخل العملية نفسها. تكرار إنشاء هوية موجودة لا يكرر المعلم ولا يكتب فوق سجل عام موجود.

### update

يحدّث داخل عملية واحدة:

- الهوية المستمرة في `teachers`
- البيانات السنوية في `teacher_years`
- الملف المهني في `teacher_profiles`

ولا يعيد تفعيل سجل معلم أو سنة دراسية معطلة ضمنيًا؛ حالة `is_active` القائمة تُحفظ عند التحديث.

## حدود المرحلة

- لا Cutover لواجهة المعلمين.
- لا تعديل `api.ts` لاستخدام Supabase.
- لا حذف معلمين.
- لا CV item write cutover في هذه المرحلة.
- لا Storage أو Meetings أو Events أو Documents.

## خطوات القبول

1. ارفع Changed Files Only إلى GitHub.
2. انتظر GitHub Actions GREEN.
3. شغّل Migration:
   `supabase/migrations/20260904130000_s3_b2_teacher_write_foundation.sql`
4. شغّل:
   `supabase/tests/s3_b2_live_acceptance.sql`
5. المطلوب:
   `PASS: S3-B2 teacher write RLS acceptance`

ملف القبول يستخدم Fixtures داخل Transaction وينتهي بـ`ROLLBACK;`، لذلك لا يترك معلم اختبار أو مدرسة اختبار في المشروع.
