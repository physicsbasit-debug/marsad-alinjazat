# S3-C3C — الرفع المباشر للوثائق عبر Supabase

تغلق هذه المرحلة الفجوة المتبقية في صفحة «الوثائق والمراجع»: يستطيع مالك النظام أو الإدارة رفع وثيقة مباشرة للعام الدراسي الحالي دون المرور بطلب معلم.

## الحدود الأمنية

- المتصفح يستدعي Edge Function باسم `marsad-direct-document-upload` فقط.
- الدالة تتطلب جلسة مستخدم صالحة، وتعيد التحقق من JWT عبر Supabase Auth.
- بعد التحقق من الهوية تفحص عضوية `school_memberships` وتقبل `owner` و`admin` فقط.
- لا توجد صلاحية INSERT مباشرة للمتصفح على `documents`، ولا سياسة رفع مباشرة إلى `storage.objects`.
- مفتاح الخادم يبقى داخل Edge Function، مع دعم `SUPABASE_SECRET_KEYS` الحالي والـ`SUPABASE_SERVICE_ROLE_KEY` القديم كمسار توافق فقط.

## التخزين

تستخدم المرحلة نفس Bucket الخاصة `marsad-documents` المنشأة في S3-C3B. المسار المباشر:

`<school_id>/<academic_year_id>/direct/<uuid>-<safe_filename>`

الحد الأقصى 25MB، والأنواع المسموحة: PDF وWord وExcel وPowerPoint وJPEG وPNG. لا يُقبل WebP في مسار Supabase الحالي لأن عقد Bucket لا يتضمن `image/webp`.

## التسجيل

بعد نجاح Storage تسجل Edge Function صفًا في `documents` بقيم:
- `request_id = null`
- `storage_provider = 'supabase'`
- `status = 'approved'`
- `approved_at = now()`

ثم تضيف نشاطًا في `activities` باسم الوثيقة وهوية المستخدم الإداري. إذا فشل تسجيل metadata يحذف ملف Storage. وإذا فشل النشاط بعد إنشاء الوثيقة تحذف metadata والملف كتعويض.

## لماذا لا توجد Migration؟

مخطط `documents` الحالي يحتوي أصلًا جميع الحقول المطلوبة، وBucket الحالية مناسبة للأنواع المعتمدة. لذلك إضافة SQL جديدة ستكون حركة زائدة لا تمنحنا شيئًا سوى فرصة إضافية لكسر شيء يعمل.

## النشر

- لا SQL لهذه المرحلة.
- انشر `supabase/functions/marsad-direct-document-upload/index.ts` كـEdge Function باسم `marsad-direct-document-upload`.
- يجب أن يبقى Verify JWT مفعّلًا. عدم وجود قسم خاص بالدالة في `supabase/config.toml` يعني استخدام القيمة الافتراضية الآمنة `verify_jwt = true`.
- بعد النشر نفّذ اختبار القبول الحي الموثق في `supabase/tests/s3_c3c_live_acceptance.md`.
