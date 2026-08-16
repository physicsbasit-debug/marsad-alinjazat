# تعليمات رفع مرصد الإنجازات v0.14-B — Railway والتشغيل الحقيقي

هذه الحزمة مبنية فوق آخر نقطة استقرار خضراء في `main`:

```text
6cf297f2bff620f79719cadce48a17f2cc544397
```

## ما الذي ترفعه؟

ارفع **محتويات Changed Files Only** إلى جذر المستودع مع الاستبدال. لا ترفع المجلد الأب.

## ما الذي تضيفه المرحلة؟

- `Dockerfile` يبني React ثم يشغّل FastAPI في صورة واحدة.
- `railway.json` يستخدم Dockerfile ويضع Healthcheck على `/api/ready`.
- `.dockerignore` يمنع دخول الأسرار وقواعد البيانات والملفات التشغيلية إلى صورة Docker.
- دعم تلقائي لـ`RAILWAY_VOLUME_MOUNT_PATH` كجذر دائم للبيانات والنسخ والملفات المحلية.
- دعم تلقائي لـ`RAILWAY_PUBLIC_DOMAIN` عندما لا يُحدد `APP_PUBLIC_URL` يدويًا.
- بوابة دخول إنتاجية مؤقتة بكلمة مرور من `APP_ACCESS_PASSWORD`.
- حماية الواجهة والـAPI الإداريين بالجلسة، مع إبقاء مسارات رفع المعلمين العامة ذات token متاحة.
- وثيقة `RAILWAY_DEPLOYMENT_AR.md` وقالب `RAILWAY_ENV_TEMPLATE.txt`.

## ما الذي لم يتغير؟

- لا جدول SQLite جديد.
- لا SQL يدوي.
- لا تغيير في منطق التحصيل أو الإتقان أو أي معيار تربوي.
- لا تغيير في Google Drive أو OAuth.
- GitHub Pages تبقى Preview فقط.

## بعد الرفع

1. انتظر GitHub Actions حتى تصبح خضراء.
2. لا تدخل بيانات حقيقية في GitHub Pages.
3. بعدها اتبع `RAILWAY_DEPLOYMENT_AR.md` خطوة بخطوة لإنشاء خدمة Railway وربط Volume على `/app/persist`.
4. ضع كلمة مرور قوية بدل قيمة `APP_ACCESS_PASSWORD` النموذجية.
5. لا تعتبر المرحلة مغلقة حتى ينجح اختبار: إنشاء اجتماع وحضور → Restart → بقاء الاجتماع والحضور.

## تنبيه

لا ترفع `RAILWAY_ENV_TEMPLATE.txt` بعد ملئه بأسرارك. الملف الموجود في المستودع قالب فقط؛ القيم الحقيقية توضع في Railway Variables.
