# مرصد الإنجازات — Phase S2-B3: Operational Domains Migration

## هدف المرحلة

نقل بنية المجالات التشغيلية الأساسية إلى PostgreSQL وفق عقد S2-A المجمد، من دون تحويل تشغيل React إلى Supabase ومن دون نقل بيانات SQLite الفعلية بعد.

تضيف المرحلة migration ثالثة:

`supabase/migrations/20260901210000_s2_b3_operational_domains.sql`

وتنشئ 11 جدولًا:

- الاجتماعات: `meetings`, `meeting_attendees`, `meeting_decisions`.
- التخطيط: `curriculum_plans`, `curriculum_units`.
- الإشراف: `supervision_visits`, `supervision_actions`.
- التحصيل: `achievement_assessments`, `achievement_assessment_standards`, `achievement_actions`, `achievement_action_metrics`.

## العزل المدرسي

كل علاقة تشغيلية حساسة تستخدم `school_id` مع المفتاح المرتبط، مثل `(school_id, teacher_id)` و`(school_id, academic_year_id)` و`(school_id, meeting_id)`. لذلك لا يكفي أن يكون رقم السجل صحيحًا؛ يجب أن ينتمي إلى المدرسة نفسها.

المراجع الاختيارية للمعلم مثل مسؤول القرار أو مالك الخطة تستخدم `ON DELETE SET NULL` للمعرف فقط مع إبقاء `school_id`، بينما الزيارة الإشرافية تستخدم `RESTRICT` لأن المعلم جزء أساسي من سجل الزيارة.

## الأعوام الدراسية

الجداول الجذرية السنوية `meetings`, `curriculum_plans`, `supervision_visits`, و`achievement_assessments` ترتبط بـ`academic_years` عبر `(school_id, academic_year_id)`. حذف العام الدراسي الذي يملك سجلات تشغيلية مرفوض بدل حذف التاريخ المؤسسي معه.

## سلامة التحصيل

يحافظ PostgreSQL على قيود التحصيل السابقة، ومنها:

- الدرجة القصوى أكبر من صفر.
- أعداد الطلبة والفئات غير سالبة.
- مجموع فئات المتابعة لا يتجاوز عدد الطلبة.
- المتوسط والأعلى والأدنى ضمن الدرجة القصوى.
- حد الإتقان بين 0 و100.
- قياس أثر التدخل لا يملك `outcome_value` بلا `measured_at` والعكس.

## الأمان في هذه المرحلة

migration S2-B3 نفسها لا تنشئ Policies ولا تنفذ `ENABLE ROW LEVEL SECURITY`. تسحب كل صلاحيات `anon` و`authenticated` من الجداول والتسلسلات الجديدة. أثناء القبول الحي ظهر أن مشروع Supabase يفعّل RLS تلقائيًا على الجداول الجديدة عبر إعداد خارجي؛ تم اعتماد ذلك كما هو لأن عدد Policies بقي صفرًا وbrowser grants بقي صفرًا. سياسات التفويض الفعلية ما زالت مؤجلة إلى S2-C.

## اختبار القبول الحي

بعد GitHub Actions الأخضر فقط:

1. شغّل `20260901210000_s2_b3_operational_domains.sql` في Supabase SQL Editor.
2. شغّل `supabase/tests/s2_b3_live_acceptance.sql`.
3. النتيجة المطلوبة: `PASS: S2-B3 live acceptance`.

اختبار القبول يعمل داخل transaction وينتهي بـ`ROLLBACK`، ويختبر وجود الجداول، انعدام صلاحيات المتصفح والسياسات المبكرة، اتساق حالة auto-RLS (إما 0 أو 11 جدولًا)، العزل بين المدارس، قيود نسب الإنجاز والتحصيل، وسلوك `SET NULL` و`RESTRICT`. وقد اجتاز الاختبار الحي بصيغة v2 على مشروع Supabase.
