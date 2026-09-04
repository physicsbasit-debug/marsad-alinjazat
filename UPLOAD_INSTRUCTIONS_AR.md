# تعليمات رفع مرصد الإنجازات v0.25.0 — S2-E1

نقطة الأساس: **v0.24.1 / S2-D Fix 1 LIVE GREEN**.

1. ارفع محتويات `changed_files_only` فوق `main`.
2. تأكد من وصول `.github/workflows/quality-pages.yml` والنسخة المرئية المطابقة.
3. انتظر GitHub Actions GREEN، بما في ذلك `S2-E1 SQLite migration compiler dry-run tooling`.
4. **لا تشغّل أي Migration في Supabase**؛ هذه المرحلة لا تضيف Migration.
5. بعد GREEN، استخدم نسخة SQLite متسقة وحقيقية لتوليد Dry Run Pack.
6. لا تُستخدم قاعدة GitHub لأن ملفات `*.sqlite3` و`data/` مستبعدة عمدًا.
7. ملف Dry Run الناتج يجب أن ينتهي بـ`ROLLBACK;` والنتيجة المطلوبة في Supabase هي:
   `PASS: S2-E1 SQLite migration dry run`.

نجاح S2-E1 يسمح ببناء خطة النقل الإنتاجي فقط. Runtime ما يزال FastAPI/SQLite حتى مرحلة قطع مستقلة لاحقًا.
