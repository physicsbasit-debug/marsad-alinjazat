# تعليمات رفع مرصد الإنجازات v0.17.0 — Phase S2-B1

هذه الحزمة تُرفع فوق **v0.16.0 / S2-A GREEN**.

## ما الذي ترفعه؟

ارفع محتويات حزمة `changed-files-only` إلى جذر المستودع مع الاستبدال. لا ترفع المجلد الأب.

## ما الذي تضيفه المرحلة؟

- أول migration PostgreSQL في `supabase/migrations/`.
- الجداول: `schools`, `profiles`, `school_memberships`, `academic_years`.
- عقد آلي خاص بـS2-B1.
- فحص CI جديد لـS2-B1.
- تحديث الإصدار إلى `0.17.0`.

## ما الذي لا يتغير؟

- React runtime يبقى على FastAPI/SQLite.
- لا نقل لبيانات SQLite.
- لا RLS ولا Auth UI.
- لا Storage ولا Edge Functions.
- لا جدول `teachers` بعد.

## بعد الرفع

1. انتظر GitHub Actions حتى تصبح خضراء بالكامل.
2. تحقق من نجاح: S0, S1, S2-A, S2-B1, Pytest, HTTP E2E.
3. لا تبدأ S2-B2 قبل نجاح CI.
4. بعد CI الأخضر نحتاج اختبار PostgreSQL فعلي للمigration على Supabase Development/Local قبل الإغلاق التشغيلي النهائي لـS2-B1.

## الملفات المخفية

الـworkflow الحقيقي موجود في `.github/workflows/quality-pages.yml`، وتوجد نسخة مرئية مطابقة في `GITHUB_WORKFLOW_VISIBLE/quality-pages.yml`. يجب أن يبقيا متطابقين.
