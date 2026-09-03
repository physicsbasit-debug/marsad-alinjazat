# Phase S2-C2 — Domain RLS Baseline

الإصدار: **v0.23.0**  
الأساس: **S2-C1 LIVE GREEN / v0.22.0**

توسع S2-C2 عزل Supabase من جداول الهوية الخمسة إلى **الجداول الـ21 المتبقية** دون تحويل React إلى Supabase ودون نقل بيانات SQLite أو bytes التخزين.

## نموذج القراءة

- 14 جدولًا تشغيليًا مدرسيًا: يقرأها أي عضو نشط في المدرسة (`owner/admin/lead_teacher/teacher/viewer`).
- `teachers`, `teacher_profiles`, `teacher_years`, `teacher_cv_items`, `documents`: يقرأها `owner/admin/lead_teacher` داخل المدرسة، أو حساب `teacher` لسجله المرتبط فقط.
- `upload_requests`: قراءة `owner/admin` فقط في هذه المرحلة لأن الجدول يحمل `token_hash` ولا يوجد بعد View آمن لإخفائه.
- `activities`: قراءة `owner/admin` فقط لأنه سجل تدقيق.

## نموذج الكتابة

الكتابة المباشرة من المتصفح محصورة في **owner/admin**، وبالعمليات الموجودة أصلًا في سطح Legacy الموثق. لا يمنح S2-C2 صلاحيات مدرسية شاملة لـ`lead_teacher` لأن S2-A جمّد المدرسة بوصفها tenant الوحيد، ولا يوجد عزل قسم/مادة يمنع معلمًا أول من الكتابة عبر أقسام أخرى.

تبقى خمسة جداول بلا كتابة مباشرة من المتصفح:

- `teacher_years`: حالة سنوية/مشتقة، ولا يوجد لها مسار CRUD مباشر في Legacy.
- `upload_requests`: إصدار token عملية موثوقة وتنتظر Edge Function.
- `documents` و`event_media`: مرتبطان بتخزين فعلي وتنتظر سياسات Storage/المسار الذري.
- `activities`: لا يسمح للعميل بتزوير سجل التدقيق.

## ضوابط إضافية

- لا grants لـ`anon`.
- لا Storage policies.
- لا public upload في هذه المرحلة.
- لا تعديل لـ`auth.users`.
- مصدر الدور الوحيد `school_memberships.role`.
- تحديثات المتصفح column-scoped ولا تسمح بتغيير `school_id` أو PK أو timestamps المدارة من قاعدة البيانات.
- الحذف لا يفتح إلا للكيانات الفرعية التي يوجد لها DELETE route مثبت في Legacy، وليس للجذور مثل event/teacher/meeting.

## القبول الحي

بعد GitHub GREEN شغّل Migration S2-C2 ثم `supabase/tests/s2_c2_live_acceptance.sql`. الاختبار يستخدم أحدث مستخدم Auth موجود، ينشئ مدارس اختبار بأدوار owner/teacher/viewer/lead_teacher، يثبت العزل والقراءة الخاصة ومنع الكتابة الزائدة، ثم ينتهي بـ`ROLLBACK`.

النتيجة المطلوبة:

```text
PASS: S2-C2 domain RLS baseline acceptance
```
