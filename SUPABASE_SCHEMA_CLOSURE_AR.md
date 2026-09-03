# Phase S2-B5 — إغلاق مخطط PostgreSQL قبل Auth/RLS

الإصدار: **v0.21.0**

هذه المرحلة لا تضيف مجالًا جديدًا ولا تنقل بيانات SQLite. هدفها إغلاق طبقة S2-B هندسيًا قبل بدء S2-C.

## ما تم تثبيته

- سلسلة S2-B1..S2-B4 تمثل **26/26** جدولًا من عقد S2-A المجمد، بإجمالي **299 عمودًا**.
- لم يُعد إنشاء جداول Legacy الأربعة: `request_record_years`, `event_record_years`, `teacher_record_years`, `event_media_meta`.
- كل علاقة بين جدولين تابعين لمدرسة تستخدم `school_id` داخل المفتاح الأجنبي نفسه لمنع الربط العابر للمدارس.
- أضيفت دالة trigger موحدة `public.set_row_updated_at()` و22 trigger لتحديث `updated_at` على مستوى PostgreSQL باستخدام `statement_timestamp()`.
- سُحب EXECUTE على دالة الـtrigger من `PUBLIC`, `anon`, و`authenticated` حتى لا تظهر كـRPC قابلة للاستدعاء من المتصفح.
- أضيفت ثلاثة فهارس نهائية فقط:
  - `idx_school_memberships_school_status_role`
  - `idx_academic_years_school_start`
  - `idx_teacher_cv_items_teacher_type`
- لا توجد Policies قبل S2-C، ولا تُمنح صلاحيات Browser roles في S2-B5.
- حالة auto-RLS التي قد يطبقها Supabase خارجيًا لا تُعد فشلًا بحد ذاتها؛ S2-C ستوحّد RLS وتضيف السياسات الرسمية.

## ما لم يحدث

- لا ربط React بـSupabase.
- لا نقل بيانات حقيقية من SQLite.
- لا نقل bytes إلى Supabase Storage.
- لا إنشاء مستخدمي Auth.
- لا إنشاء RLS Policies.
- لا Edge Functions.

## بوابة الإغلاق الحي

بعد GitHub Actions الأخضر وتشغيل migration الخامسة يدويًا في Supabase SQL Editor، شغّل:

`supabase/tests/s2_b5_live_acceptance.sql`

الاختبار يتحقق من الجداول الـ26، توقيع الأعمدة والأنواع الـ299، غياب الجداول Legacy، browser grants والسياسات، سلامة الفهارس والقيود، العزل العام للعلاقات بين المدارس، تسرب صلاحيات sequences، غياب raw token/secret-like columns، وجود 22 trigger، ثم يثبت وظيفيًا أن `updated_at` يتقدم تلقائيًا. وينتهي بـ`ROLLBACK`.

النتيجة المطلوبة:

`PASS: S2-B5 final schema acceptance`

عند نجاحها تصبح بوابة المرحلة:

**S2-B DATABASE SCHEMA COMPLETE**
