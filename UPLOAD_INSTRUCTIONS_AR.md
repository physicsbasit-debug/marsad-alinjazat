# مرصد الإنجازات — v0.2.1 Fix 2

## سبب الإصلاح
GitHub Actions نجح في TypeScript/Vite ثم توقف عند:
`pytest: command not found`

## التعديل
ملفان فقط:
1. `requirements-dev.txt`
2. `.github/workflows/quality-pages.yml`

`requirements-dev.txt` يضيف متطلبات الاختبارات فقط:
- pytest
- httpx
مع إعادة استخدام `requirements.txt` الأساسي.

## طريقة الرفع
1. ارفع `requirements-dev.txt` إلى جذر المستودع.
2. استبدل `.github/workflows/quality-pages.yml` بالنسخة الجديدة.
3. إذا لم يظهر لك مجلد `.github` في الهاتف، توجد نسخة مرئية احتياطية داخل `GITHUB_WORKFLOW_VISIBLE/quality-pages.yml`.
4. لا ترفع النسخة المرئية إذا كنت قد رفعت المسار الحقيقي `.github/workflows/quality-pages.yml`.
5. انتظر GitHub Actions.

لا يوجد أي تعديل على كود التطبيق أو قاعدة البيانات أو Google Drive في هذا الإصلاح.
