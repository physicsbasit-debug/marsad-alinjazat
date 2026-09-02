# مرصد الإنجازات — Phase S2-B4: Events / Documents / Requests / Activities

## هدف المرحلة

تكمل S2-B4 **بنية PostgreSQL المجمدة في S2-A بالكامل**. بعد S2-B1 وS2-B2 وS2-B3 بقيت سبعة جداول مستهدفة فقط، وهذه المرحلة تنشئها دون تحويل تشغيل React إلى Supabase ودون نقل بيانات SQLite أو ملفات التخزين الفعلية.

تضيف migration الرابعة:

`supabase/migrations/20260902080000_s2_b4_content_intake_domains.sql`

وتنشئ:

- `school_settings`
- `upload_requests`
- `documents`
- `events`
- `event_media`
- `event_teacher_links`
- `activities`

وبذلك تصبح **جميع جداول العقد المستهدف الـ26 موجودة في سلسلة migrations**.

## ما لا يُعاد إنشاؤه من SQLite

أربع جداول Legacy لا تعود كجداول مستقلة لأن عقد S2-A دمج وظيفتها داخل التصميم الجديد:

- `request_record_years` ← داخل `upload_requests.academic_year_id`.
- `event_record_years` ← داخل `events.academic_year_id`.
- `event_media_meta` ← داخل `event_media.caption / position / is_cover`.
- `teacher_record_years` ← داخل `teacher_years`.

أما `settings` القديمة فتتحول إلى `school_settings` فقط للتهيئة غير السرية. لا تُنسخ OAuth tokens أو الأسرار إلى `public`.

## الطلبات وروابط الرفع العامة

`upload_requests` يحفظ **hash الرمز فقط** في `token_hash` ولا يوجد عمود للرمز الخام. كما يفرض PostgreSQL:

- `token_hash` فريدًا.
- `expires_at` إلزاميًا.
- حالات الطلب محصورة في `waiting_upload`, `received`, `review`, `approved`, `needs_revision`, `late`, `cancelled`.
- السنة والمعلم يجب أن ينتميا إلى المدرسة نفسها.
- حذف المعلم المرتبط بطلب قائم مرفوض بـ`RESTRICT`.

هذه المرحلة لا تبني Edge Function للرفع العام ولا تحول المسار القديم إليها بعد؛ ذلك يأتي عند قطع مسار التشغيل العام لاحقًا.

## الوثائق والتخزين

`documents` لا يخزن bytes داخل PostgreSQL. يحتفظ ببيانات التخزين المعيارية فقط:

- `storage_provider`: أحد `supabase`, `google_drive`, `legacy_local`.
- `storage_bucket` و`storage_path` لمسار التخزين الداخلي.
- `external_url` عند وجود رابط خارجي مثل Google Drive.

حذف طلب لا يحذف الوثيقة التاريخية، بل يجعل `request_id = NULL`. وكذلك ارتباط المعلم الاختياري في الوثيقة يستخدم `SET NULL`.

لا تُنقل ملفات SQLite/المجلدات أو Google Drive في S2-B4.

## الفعاليات والأدلة

`events` مرتبط بالسنة داخل المدرسة نفسها. `event_media` يدمج حقول metadata القديمة مباشرة، ويمنع أكثر من `is_cover=true` واحد لكل فعالية عبر unique partial index. كما ترتبط الوسائط والمعلمون بالفعالية داخل المدرسة نفسها، فلا يمكن تمرير معرف فعالية أو معلم من tenant آخر.

## سجل النشاط

`activities` يحمل `school_id` دائمًا، و`academic_year_id` و`actor_user_id` عند معرفتهما. علاقة المستخدم الفاعل مرتبطة بـ`school_memberships (school_id,user_id)` لضمان أن actor، عندما يكون موجودًا، يعود إلى المدرسة نفسها.

## RLS في مشروع Supabase الحالي

migration نفسها **لا تنشئ RLS policies ولا تنفذ `ENABLE ROW LEVEL SECURITY`**. لكن اختبار S2-B3 الحي كشف أن مشروع Supabase الحالي يفعّل RLS تلقائيًا على الجداول الجديدة. هذا مقبول أمنيًا في هذه المرحلة لأن:

- صلاحيات `anon` و`authenticated` مسحوبة صراحةً.
- لا توجد policies قبل S2-C.
- اختبار القبول يقبل إما RLS معطلًا على كل جداول S2-B4 أو مفعّلًا تلقائيًا على جميعها، ويرفض الحالة المختلطة.

لا نعطل auto-RLS يدويًا لمجرد مطابقة افتراض قديم.

## اختبار القبول

بعد GitHub Actions الأخضر فقط:

1. شغّل `supabase/migrations/20260902080000_s2_b4_content_intake_domains.sql` في Supabase SQL Editor.
2. شغّل `supabase/tests/s2_b4_live_acceptance.sql`.
3. النتيجة المطلوبة: `PASS: S2-B4 live acceptance`.

الاختبار يعمل داخل transaction وينتهي بـ`ROLLBACK`، ويختبر وجود الجداول السبعة، انعدام browser grants والسياسات المبكرة، حالة auto-RLS المتسقة، same-school FKs، `SET NULL` و`RESTRICT`، حالات الطلب، مزودي التخزين، غلاف الفعالية الواحد، وسلامة العدد والسنة.
