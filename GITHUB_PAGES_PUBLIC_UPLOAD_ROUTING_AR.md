# GitHub Pages Public Upload Routing — S3-C3B R1

الإصدار: **0.34.1**

## سبب التصحيح

GitHub Pages لا يملك server-side rewrite لمسارات SPA. لذلك فتح رابط من الشكل:

`/marsad-alinjazat/upload/<token>`

مباشرة يجعل GitHub Pages يبحث عن ملف فعلي في ذلك المسار قبل تشغيل React، وينتهي إلى 404.

## التصميم المعتمد

- الروابط الجديدة تستخدم:
  `/marsad-alinjazat/?upload=<token>`
  وبذلك يصل الطلب أولًا إلى `index.html`.
- التطبيق يقرأ `upload` من query string قبل المسار القديم.
- نحتفظ بدعم `/upload/<token>` للروابط المنشأة سابقًا.
- أثناء نشر Pages يتم إنشاء `dist/404.html` كنسخة من `dist/index.html` حتى تقوم الروابط القديمة بتحميل SPA بدل صفحة 404 الخام.

## حدود التغيير

هذا تصحيح Frontend/Pages فقط. لا يتغير عقد Supabase أو Storage أو RPC أو Edge Function، ولا توجد Migration جديدة.
