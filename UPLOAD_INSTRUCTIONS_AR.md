# مرصد الإنجازات — v0.2.1 Fix 3

## السبب الحقيقي
الاستيراد `from fastapi.testclient import TestClient` صحيح.
الفشل الحقيقي كان:
`ModuleNotFoundError: No module named 'server'`

## الإصلاح
تشغيل الاختبارات عبر مفسر Python نفسه:

قبل:
`pytest -q`

بعد:
`python -m pytest -q`

هذا يجعل جذر المستودع ضمن مسار الاستيراد، فيتم العثور على حزمة `server`.

## التحقق
تمت إعادة إنتاج المشكلة محليًا:
- `pytest -q` → فشل بنفس `No module named 'server'`
- `python -m pytest -q` → 4 passed

## الرفع
استبدل فقط:
`.github/workflows/quality-pages.yml`

النسخة داخل `GITHUB_WORKFLOW_VISIBLE` احتياطية إذا كان مجلد `.github` غير ظاهر لديك.
لا ترفع النسختين معًا إلى مسارين مختلفين إلا إذا كنت تحتاج النسخة الاحتياطية محليًا.
