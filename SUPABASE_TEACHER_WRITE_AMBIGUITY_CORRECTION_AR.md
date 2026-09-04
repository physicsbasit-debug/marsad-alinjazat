# S3-B2R1 — تصحيح غموض `teacher_id`

أظهر القبول الحي لـ S3-B2 خطأ PostgreSQL `42702` داخل `marsad_create_teacher_v1`. سبب الخطأ أن الدالة تعيد `RETURNS TABLE(teacher_id, linked_existing)`، وبذلك يصبح `teacher_id` متغير PL/pgSQL ضمنيًا، بينما استخدم `ON CONFLICT (school_id, academic_year_id, teacher_id)` الاسم نفسه بلا تأهيل.

## القرار المعماري

لا تُعدّل Migration S3-B2 الأصلية بعد تطبيقها. أضيفت Migration تصحيحية مستقلة تعيد تعريف الدالة نفسها فقط، بنفس التوقيع والعقد، وتستهدف القيد المسمى صراحة:

```sql
ON CONFLICT ON CONSTRAINT teacher_years_pkey DO NOTHING
```

لا تتغير سياسات RLS أو Grants أو بنية الجداول أو مصدر تشغيل صفحة المعلمين.

## القبول

ملف `supabase/tests/s3_b2_r1_live_acceptance.sql` يعيد اختبار إنشاء/تحديث المعلم، العزل بين المدارس، منع lead_teacher، ومنع الحذف، ويتحقق كذلك من اختفاء نمط التعارض الغامض. ينتهي دائمًا بـ `ROLLBACK;`.
