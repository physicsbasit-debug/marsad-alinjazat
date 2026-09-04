# S2-E1B — الاختبار التمثيلي الذاتي لتحويل SQLite

هذه المرحلة تجعل قبول S2-E1 مناسبًا لمنهجية المشروع الفعلية: **GitHub + GitHub Actions + Supabase Dashboard**، دون اشتراط تشغيل محلي أو Terminal أو قاعدة SQLite خارجية.

## ما الذي يحدث؟

يبني حارس GitHub Fixture حتمية تمثل جداول Legacy الـ25، ثم يمررها عبر `marsad_sqlite_migration_compiler.py`. المخرجات المرجعية الثلاثة محفوظة داخل المستودع:

- `supabase/tests/s2_e1b_representative_dry_run.sql`
- `supabase/tests/s2_e1b_reconciliation.json`
- `supabase/tests/s2_e1b_report.md`

## التغطية

الـFixture تغطي جميع جداول Legacy الـ25، بما فيها التحويلات الحساسة:

- `teacher_record_years -> teacher_years`
- `request_record_years -> upload_requests.academic_year_id`
- `event_record_years -> events.academic_year_id`
- `event_media_meta -> event_media`
- استبعاد إعداد سري مع Audit count دون تسريب قيمته.
- `local -> legacy_local`.
- مسار `google_drive` metadata.
- سنة حالية 2026/2027 وسنة تاريخية 2025/2026.

## ما الذي لا يحدث؟

- لا Migration جديدة.
- لا تعديل Schema أو RLS.
- لا Auth mutation.
- لا نقل Storage bytes.
- لا Runtime cutover.
- لا COMMIT لبيانات الاختبار.

## القبول الحي

بعد GitHub GREEN شغّل الملف `s2_e1b_representative_dry_run.sql` في Supabase SQL Editor. النتيجة المطلوبة:

`PASS: S2-E1 SQLite migration dry run`

الملف ينتهي إلزاميًا بـ`ROLLBACK;`، لذلك لا تبقى Fixture الاختبار في قاعدة البيانات.

نجاح هذا الاختبار يعني أن **خريطة Legacy الممثلة أصبحت متوافقة مع Schema/RLS الحالية**. لا يعني بعد أن FastAPI/SQLite حُذفا أو أن Storage/Public Upload انتقلا إلى Supabase.
