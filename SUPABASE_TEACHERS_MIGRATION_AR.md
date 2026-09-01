# مرصد الإنجازات — Phase S2-B2: Teachers Domain Migration

## الهدف

إضافة مجال المعلمين إلى PostgreSQL بعد نجاح S2-B1 حيًا على Supabase، من دون تحويل الواجهة أو نقل بيانات SQLite.

## الجداول الجديدة

- `teachers`: الهوية المهنية المستمرة للمعلم.
- `teacher_profiles`: البيانات المهنية الممتدة مثل الرقم الوظيفي وسنة الانضمام والملخص.
- `teacher_years`: المادة والخبرة والنصاب والصفوف والمسؤوليات الخاصة بعام دراسي محدد.
- `teacher_cv_items`: المؤهلات والدورات والإنجازات والخبرات.

## حماية Tenant

كل علاقة حساسة إلى المعلم تستخدم `(school_id, teacher_id)` بدل `teacher_id` وحده. ويكتمل في هذه المرحلة FK المؤجل من `school_memberships` إلى `teachers`، لذلك لا يمكن ربط عضوية مدرسة بمعلم من مدرسة أخرى.

`teacher_years` يربط كذلك `(school_id, academic_year_id)` بجدول `academic_years` لضمان أن السنة نفسها تنتمي إلى المدرسة نفسها.

## قرار الحذف

ارتباط `school_memberships → teachers` يستخدم `ON DELETE RESTRICT`: إذا كان سجل المعلم مرتبطًا بحساب مستخدم، يجب فك الارتباط أولًا قبل حذف هوية المعلم. أما profile/year/CV فتُحذف تلقائيًا مع المعلم.

## القيود

- اسم المعلم غير فارغ.
- `school_join_year`: من 1950 إلى 2100 عند وجوده.
- الرقم الوظيفي فريد داخل المدرسة عندما يكون غير فارغ.
- الخبرة السنوية: 0..60 عند وجودها.
- النصاب: 0..40 عند وجوده.
- نوع عنصر CV: `qualification/course/achievement/experience`.
- سنوات CV: 1950..2100، والنهاية لا تسبق البداية.

## الأمن

لا RLS في S2-B2. الجداول الجديدة تسحب كل الصلاحيات من `PUBLIC`, `anon`, `authenticated` حتى S2-C. لا توجد أسرار أو service-role في الواجهة.

## ما لا يحدث في هذه المرحلة

- لا نقل معلمين حقيقيين من SQLite.
- لا استدعاء Supabase من React.
- لا Auth UI.
- لا RLS policies.
- لا حذف FastAPI/SQLite.

## القبول

1. GitHub Actions: S0/S1/S2-A/S2-B1/S2-B2 + pytest + HTTP E2E كلها خضراء.
2. بعد ذلك فقط تطبق migration الجديدة على مشروع Supabase التطويري الذي اجتاز S2-B1.
3. يشغّل `supabase/tests/s2_b2_live_acceptance.sql` من SQL Editor؛ يجب أن يعيد `PASS: S2-B2 live acceptance`.
