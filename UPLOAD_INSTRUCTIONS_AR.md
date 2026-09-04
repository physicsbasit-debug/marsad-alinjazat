# تعليمات رفع مرصد الإنجازات v0.25.1 — S2-E1B

نقطة الأساس: **v0.25.0 / S2-E1 GitHub GREEN**، وS2-D LIVE GREEN.

1. ارفع محتويات `changed_files_only` فوق `main`.
2. تأكد من وصول `.github/workflows/quality-pages.yml` والنسخة المرئية المطابقة.
3. انتظر GitHub Actions GREEN، بما في ذلك:
   `S2-E1B representative legacy dry-run pack`.
4. **لا تشغّل أي Migration في Supabase**؛ S2-E1B لا تضيف Migration.
5. لا تحتاج Terminal ولا ملف SQLite خارجي.
6. بعد GREEN افتح Supabase > SQL Editor > New query وشغّل كامل الملف:
   `supabase/tests/s2_e1b_representative_dry_run.sql`.
7. النتيجة المطلوبة:
   `PASS: S2-E1 SQLite migration dry run`.
8. الملف ينتهي بـ`ROLLBACK;`، لذلك لا تبقى بيانات Fixture.

نجاح S2-E1B يثبت أن خريطة Legacy الممثلة متوافقة مع قاعدة Supabase الحالية. لا يوجد Runtime cutover ولا نقل Storage bytes في هذه المرحلة.
