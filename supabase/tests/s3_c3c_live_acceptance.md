# S3-C3C Live Acceptance

هذه المرحلة لا تضيف Migration، لذلك قبولها الحي يختبر Edge + Auth + Storage + metadata بدل تشغيل SQL تغييري.

1. سجّل الدخول بحساب `owner` أو `admin`.
2. افتح «الوثائق والمراجع» للعام الجاري.
3. اضغط «إضافة وثيقة» وارفع PDF صغيرًا مع عنوان وتصنيف، مع ربط اختياري بمعلم.
4. يجب أن يظهر الملف في القائمة فور التحديث بحالة `approved` وأن يكون `storage_provider = 'supabase'`.
5. افتح الوثيقة من الإدارة؛ يجب أن تعمل عبر Signed URL مؤقت.
6. تحقق من Storage أن المسار يبدأ بـ `<school_id>/<academic_year_id>/direct/` وأن Bucket ما زالت private.
7. تحقق من `activities` من وجود سجل `document` مرتبط بمعرف الوثيقة وبـactor المستخدم الإداري.
8. جرّب ملفًا بامتداد غير مسموح، ثم ملفًا أكبر من 25MB؛ يجب رفضهما دون إنشاء metadata أو object.
9. جرّب حسابًا بدور `teacher` أو `lead_teacher`; يجب رفض الرفع المباشر.
10. لا تعتبر S3-C3C LIVE GREEN قبل نجاح GitHub Actions والاختبار الحي أعلاه.
