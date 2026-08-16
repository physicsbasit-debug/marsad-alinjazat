# جاهزية التشغيل الإنتاجي — مرصد الإنجازات v0.14-A

هذه المرحلة لا تختار مزود الاستضافة ولا تنقل قاعدة البيانات إلى خدمة أخرى. هدفها جعل المشروع **قابلًا للنشر بأمان** قبل اختيار البيئة النهائية، مع إبقاء GitHub Pages معاينة فقط.

## 1) نمطا النشر المدعومان

### أ. نطاق واحد — الموصى به كبداية

يبني React إلى `dist` ويخدم FastAPI الواجهة والـAPI من نفس النطاق.

```text
https://marsad.example.com/        -> React
https://marsad.example.com/api/... -> FastAPI
```

في هذا النمط:

```text
VITE_API_BASE_URL=
APP_FRONTEND_URL=https://marsad.example.com
APP_CORS_ORIGINS=https://marsad.example.com
```

هذا أبسط نمط وأقلها عرضة لأخطاء CORS ومسارات OAuth.

### ب. واجهة وخادم منفصلان

مثال:

```text
https://marsad.example.com      -> React
https://api.marsad.example.com  -> FastAPI
```

قبل بناء الواجهة:

```text
VITE_API_BASE_URL=https://api.marsad.example.com
```

وعلى الخادم:

```text
APP_FRONTEND_URL=https://marsad.example.com
APP_CORS_ORIGINS=https://marsad.example.com
```

لا تستخدم `*` في CORS للإنتاج إلا لسبب مفهوم ومراجع.

## 2) التخزين الدائم شرط، لا تحسين اختياري

عند `APP_ENV=production` لن تعتبر نقطة `/api/ready` الخدمة جاهزة إذا لم تكن المتغيرات التالية معرفة صراحةً:

```text
APP_DATA_DIR
APP_BACKUP_DIR
```

كما يتحقق الخادم من قابلية الكتابة في مجلد البيانات والنسخ والرفع. وإذا كان `STORAGE_MODE=local` أو `auto` في الإنتاج، يجب تعريف `APP_UPLOADS_DIR` و`APP_EVENT_UPLOADS_DIR` صراحةً أيضًا. وجود المسار داخل حاوية مؤقتة لا يجعله دائمًا؛ يجب ربطه بـPersistent Disk/Volume في منصة الاستضافة.

**تنبيه:** النسخ التي ينشئها `marsad_maintenance.py` في v0.14-A هي نسخ SQLite متسقة للبيانات الوصفية والعلاقات. إذا كنت تستخدم التخزين المحلي للملفات، فملفات `uploads` نفسها يجب أن تكون على Volume دائم وله Snapshot/Backup على مستوى منصة الاستضافة. عند استخدام Google Drive تبقى الملفات الفعلية في Drive، بينما نسخة SQLite تحمي الفهرس والعلاقات.

المجلدات الموصى بها:

```text
/var/lib/marsad/data
/var/lib/marsad/backups
/var/lib/marsad/uploads/inbox
/var/lib/marsad/uploads/events
```

## 3) Health وReadiness

### Liveness

```text
GET /api/health
```

يعني أن التطبيق يعمل ويمكن الوصول إليه.

### Readiness

```text
GET /api/ready
```

يفحص:

- الاتصال بقاعدة SQLite.
- قابلية الكتابة في مجلد البيانات.
- قابلية الكتابة في مجلد النسخ الاحتياطية.
- قابلية الكتابة في مجلدات الرفع.
- نجاح حارس النسخة الاحتياطية عند بدء التشغيل.
- وجود مسارات بيانات ونسخ صريحة في وضع الإنتاج.
- جاهزية Google Drive إذا تم فرض `STORAGE_MODE=google_drive`.

يعيد HTTP `503` عند فشل أي شرط جاهزية.

## 4) النسخ الاحتياطية

قبل `init_db()` يحاول الخادم إنشاء نسخة متسقة من قاعدة البيانات الموجودة باستخدام **SQLite Backup API**. هذا مهم قبل أي ترقية مستقبلية للمخطط.

الإعداد الافتراضي:

```text
APP_AUTO_BACKUP_ON_STARTUP=true
APP_STARTUP_BACKUP_MIN_INTERVAL_MINUTES=60
APP_BACKUP_KEEP=14
```

الحد الزمني يمنع إنتاج عشرات النسخ عند Hot Reload أو إعادة تشغيل متقاربة.

### نسخة يدوية

من جذر المشروع:

```bash
python scripts/marsad_maintenance.py backup --label before-release
```

### التحقق من نسخة

```bash
python scripts/marsad_maintenance.py verify /path/to/marsad-....sqlite3
```

الفحص يتحقق من:

- `PRAGMA integrity_check`.
- `PRAGMA foreign_key_check`.
- وجود جداول معروفة لمرصد الإنجازات.
- SHA-256 وحجم الملف.

### الاستعادة

**أوقف خادم FastAPI أولًا.** الاستعادة عملية Offline عمدًا حتى لا نستبدل قاعدة مستخدمة باتصال نشط.

```bash
python scripts/marsad_maintenance.py restore /path/to/backup.sqlite3 --confirm RESTORE
```

قبل الاستبدال ينشئ السكربت نسخة `pre-restore` من القاعدة الحالية، ثم يزيل ملفات WAL/SHM القديمة ويستبدل القاعدة ذريًا. عند تشغيل الخادم بعد ذلك تُطبق أي ترقيات إضافية عبر `init_db()` كالمعتاد.

لا يوجد Endpoint عام للاستعادة في v0.14-A؛ تعمدنا ذلك لأن المشروع لا يملك بعد طبقة مصادقة وصلاحيات إنتاجية، وفتح Restore عبر HTTP بلا إدارة مستخدمين مخاطرة غير مبررة.

## 5) GitHub Pages

Workflow الحالي يبني Pages مع:

```text
VITE_PREVIEW_MODE=true
```

لذلك تبقى GitHub Pages **معاينة آمنة** ولا تحفظ سجلات حقيقية. لا تغيّر ذلك لمجرد تجربة الحفظ. التشغيل الفعلي سيكون في v0.14-B على خادم FastAPI ذي تخزين دائم.

## 6) عنوان الـAPI في الواجهة

كل استدعاءات الواجهة تمر الآن عبر `VITE_API_BASE_URL`.

- فارغ = Same Origin.
- `https://api.example.com` = Backend منفصل.

حتى روابط صور/أدلة الفعاليات القادمة من `/api/...` تُحل عبر نفس العنوان، فلا تنكسر عند فصل الواجهة عن الخادم.

## 7) روابط الرفع الخارجية

رابط تسليم المعلم يُبنى من `APP_FRONTEND_URL` لأنه رابط واجهة، وليس من عنوان API. وبذلك يعمل أيضًا إذا انفصلت الواجهة عن FastAPI.

## 8) أسرار Google Drive

لا تضع أي Secret في متغير يبدأ بـ`VITE_`، لأن متغيرات Vite تدخل في حزمة المتصفح.

الأسرار التالية تبقى على الخادم فقط:

```text
GOOGLE_CLIENT_SECRET
APP_ENCRYPTION_KEY
```

راجع `GOOGLE_DRIVE_SETUP_AR.md` قبل تفعيل Drive في الإنتاج.

## 9) بوابة قبول v0.14-B لاحقًا

لا نعتبر التطبيق إنتاجيًا حتى ينجح سيناريو حي كامل على تخزين دائم:

```text
إنشاء اجتماع
→ اختيار الحضور
→ حفظ
→ إعادة تشغيل الخدمة
→ فتح التطبيق
→ الاجتماع والحضور ما زالا موجودين
```

ثم نكرر المسار لخطة، نتيجة، زيارة، فعالية، وثيقة، وسجل سنة تاريخية.

## 10) البيئة المعتمدة في v0.14-B

تم اعتماد Railway كأول بيئة تشغيل فعلية. الإعداد التنفيذي موجود في `RAILWAY_DEPLOYMENT_AR.md`. عند Railway لا يلزم تعريف مسارات `APP_*_DIR` إذا كان Volume مربوطًا؛ v0.14-B يكتشف `RAILWAY_VOLUME_MOUNT_PATH` ويشتق المسارات تحته. كذلك يمكن ترك `APP_PUBLIC_URL` فارغًا ليستخدم `RAILWAY_PUBLIC_DOMAIN` تلقائيًا.

في الإنتاج يجب تعريف `APP_ACCESS_PASSWORD` بكلمة مرور قوية. `/api/ready` يرفض الجاهزية إذا كانت بوابة الدخول غير مهيأة.
