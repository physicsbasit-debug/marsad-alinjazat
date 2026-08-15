# مرصد الإنجازات — v0.2.1 Fix 1

الإصلاح محدود إلى ملف واحد:
- tsconfig.node.json

التغيير:
- إضافة `"noEmit": true` حتى يكون `allowImportingTsExtensions` صالحًا أثناء فحص TypeScript مع Vite.

طريقة الرفع:
1. ارفع `tsconfig.node.json` إلى جذر المستودع.
2. وافق على استبدال الملف الحالي.
3. انتظر GitHub Actions.
4. لا تغيّر أي ملف آخر في هذا الإصلاح.
