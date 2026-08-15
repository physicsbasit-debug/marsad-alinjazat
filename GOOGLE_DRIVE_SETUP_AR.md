# إعداد Google Drive

## الفكرة

المعلم الأول يربط حساب Google مرة واحدة عبر OAuth. بعد ذلك يستطيع المعلمون استلام روابط رفع عامة، والخادم يرفع ملفاتهم إلى Drive باسم الحساب المرتبط دون أن يحتاجوا دخولًا إلى لوحة الإدارة.

## النطاق المستخدم

```text
https://www.googleapis.com/auth/drive.file
```

وهو نطاق محدود بدل طلب الوصول إلى كل محتويات Drive.

## بنية Drive التي ينشئها التطبيق

```text
مرصد الإنجازات/
└── 2026/2027/
    └── 01 - صندوق الوارد/
        ├── طلب 15/
        ├── طلب 16/
        └── ...
```

بعد اعتماد دورة الأرشفة لاحقًا ستضاف مجلدات الخطط والاختبارات والفعاليات والتقارير، مع نقل الملفات المعتمدة من صندوق الوارد.

## القيم المطلوبة في `.env`

```env
APP_ENCRYPTION_KEY=<سر طويل عشوائي>
GOOGLE_CLIENT_ID=<OAuth Client ID>
GOOGLE_CLIENT_SECRET=<OAuth Client Secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/google-drive/oauth/callback
STORAGE_MODE=google_drive
```

لا ترفع ملف `.env` إلى GitHub.
