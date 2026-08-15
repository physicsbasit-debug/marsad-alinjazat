# مرصد الإنجازات v0.2.1 — الفحص التلقائي والمعاينة الحية

هذه الحزمة لا تغيّر منطق FastAPI أو Google Drive. هدفها تثبيت أول مسار GitHub واضح للمشروع.

## بعد رفع الملفات إلى `main`

1. افتح تبويب **Actions** وتأكد من تشغيل workflow باسم **Quality & Live Preview**.
2. يجب أن ينجح بالترتيب:
   - TypeScript and Vite build
   - API tests
   - Build GitHub Pages preview
   - Deploy to GitHub Pages
3. إذا كانت GitHub Pages غير مفعلة بعد:
   - Settings
   - Pages
   - Build and deployment
   - Source: **GitHub Actions**
4. رابط المعاينة الثابت:
   `https://physicsbasit-debug.github.io/marsad-alinjazat/`

## معنى رابط المعاينة

الرابط مخصص لمتابعة تصميم الواجهة والتنقل والتقدم البصري. يستخدم بيانات معاينة ثابتة ولا يحاول تشغيل FastAPI من GitHub Pages.

رفع الملفات الحقيقي، قاعدة SQLite، وروابط الرفع وGoogle Drive تحتاج خادم FastAPI، وستبقى منفصلة عن معاينة Pages إلى أن ننشر الخادم لاحقًا.

## معيار القبول

- GitHub Actions أخضر بالكامل.
- رابط Pages يفتح واجهة مرصد الإنجازات RTL بلا شاشة خطأ API.
- صفحات الرئيسية، المعلمين، الطلبات، الفعاليات، والوثائق تعمل في التنقل.
- أي محاولة حفظ من رابط المعاينة تعطي رسالة عربية توضح أنها معاينة فقط.
- التشغيل المحلي Full-Stack يبقى على `/api` كما كان سابقًا.
