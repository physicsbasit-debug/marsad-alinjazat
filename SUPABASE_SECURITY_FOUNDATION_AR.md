# S2-C1 — أساس المصادقة والعزل الأمني

الإصدار: **v0.22.0**

هذه المرحلة هي أول مرحلة تفويض فعلية في انتقال «مرصد الإنجازات» إلى Supabase. لا تغيّر مسار التشغيل بعد: الواجهة ما زالت تستخدم FastAPI/SQLite، لكن PostgreSQL أصبح يملك أساس Supabase Auth وRLS الذي ستُبنى عليه التحويلات العمودية لاحقًا.

## لماذا قُسم S2-C؟

بدل إضافة سياسات إلى 26 جدولًا دفعة واحدة، يقفل S2-C1 النواة الأمنية على خمسة جداول فقط:

- `schools`
- `profiles`
- `school_memberships`
- `academic_years`
- `school_settings`

تبقى الجداول الـ21 الأخرى بلا browser grants أو policies جديدة حتى S2-C2. هذا يجعل اختبار العزل بين المدارس واكتشاف أخطاء الصلاحيات ممكنًا قبل توسيع السطح.

## مصدر الحقيقة للصلاحيات

مصدر الدور الوحيد هو:

```text
public.school_memberships.role
```

القيم المعتمدة من S2-A تبقى:

```text
owner / admin / lead_teacher / teacher / viewer
```

ولا تُقرأ `role` أو `status` من `auth.users.raw_user_meta_data`. بيانات المستخدم القابلة للتعديل ليست مكانًا لصلاحية أمنية.

## دوال RLS

أضيف schema داخلية غير مخصصة للـData API:

```text
private
```

وتحوي ثلاث دوال `SECURITY DEFINER` محدودة:

```text
private.is_active_school_member(uuid)
private.has_school_role(uuid, text[])
private.can_view_profile(uuid)
```

الدوال تستخدم `auth.uid()` وتقرأ العضويات الفعلية. مُنح `authenticated` حق EXECUTE عليها لأنها مطلوبة لتقييم policies، لكن schema `private` لا تُضاف إلى exposed schemas ولا إلى Extra Search Path.

## ملف المستخدم العام

أضيف trigger بعد إنشاء مستخدم جديد في Supabase Auth:

```text
on_marsad_auth_user_created
```

وينشئ `public.profiles` تلقائيًا. المسموح نسخه من metadata هو اسم العرض فقط (`display_name` أو `name`). لا تُنسخ الأدوار أو حالة العضوية.

## مصفوفة الوصول في S2-C1

| المورد | قراءة | كتابة مباشرة من المتصفح |
|---|---|---|
| المدرسة | عضو نشط | owner يعدّل الاسم/الحالة فقط |
| الملف العام | المستخدم نفسه، والمدير/المالك لحسابات مدرسته | المستخدم يعدّل `display_name` لنفسه فقط |
| العضويات | العضوية الذاتية، وowner/admin لمدرسته | **ممنوعة بالكامل** |
| الأعوام الدراسية | كل عضو نشط | owner/admin إنشاء وتعديل، لا حذف |
| الإعدادات غير السرية | كل عضو نشط | owner/admin إنشاء وتعديل، لا حذف |

إنشاء/حذف مدرسة، وإضافة الحسابات، وتغيير `role/status` لا تُفتح للمتصفح في هذه المرحلة. ستنفذ لاحقًا عبر مسار موثوق مثل Edge Function مع تحقق صريح من الصلاحية.

## Auth وRLS لا يكفي أحدهما وحده

تم ضبط الاثنين معًا:

1. **GRANT** يحدد أي عملية يستطيع دور PostgreSQL محاولة تنفيذها.
2. **RLS policy** يحدد أي صفوف يسمح للعملية أن تمسها.

لا توجد أي grants لـ`anon` على جداول المرصد في S2-C1.

## اختبار القبول الحي

بعد رفع GitHub ونجاح Actions ثم تطبيق migration:

1. أنشئ **مستخدم Auth مؤقتًا واحدًا** من Supabase Dashboard > Authentication > Users. لا نكتب مباشرة في `auth.users` من SQL.
2. شغّل `supabase/tests/s2_c1_live_acceptance.sql`.
3. يجب أن تنتهي النتيجة بـ:

```text
PASS: S2-C1 security foundation acceptance
```

الاختبار يثبت فعليًا:

- إنشاء `profiles` تلقائيًا للمستخدم الجديد.
- رؤية مدرسة العضوية فقط وعدم رؤية مدرسة ثانية.
- قدرة owner على تعديل مدرسته وعدم تعديل مدرسة أخرى.
- السماح بإضافة عام/إعداد لمدرسته ومنع نفس العملية في مدرسة أخرى.
- منع تعديل `school_memberships` مباشرة حتى للـowner.
- منع إنشاء مدرسة وحذف عام من المتصفح.
- بقاء الجداول الـ21 خارج نطاق S2-C1.

كل بيانات المدرسة/العضوية التجريبية داخل transaction وتنتهي بـ`ROLLBACK`. مستخدم Auth المؤقت نفسه لا يحذفه SQL؛ يمكن حذفه من شاشة Authentication بعد الاختبار.

## ما لم يتغير

- لا تحويل لمسار React إلى Supabase.
- لا نقل لبيانات SQLite.
- لا سياسات Storage.
- لا bytes ملفات من Google Drive أو التخزين المحلي.
- لا إنشاء مستخدم Auth داخل migration.
- لا Secret أو service key في المتصفح.

المرحلة التالية بعد القبول الحي: **S2-C2 — توسيع RLS إلى بقية جداول المجالات**.
