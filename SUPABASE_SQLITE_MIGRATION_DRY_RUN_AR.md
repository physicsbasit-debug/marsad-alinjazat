# S2-E1 / S2-E1B — SQLite Migration Compiler & Controlled Dry Run

S2-E1 أنشأت Migration Compiler لتحويل بنية Legacy ذات 25 جدولًا إلى نموذج Supabase الحالي. S2-E1B تجعل بوابة القبول **ذاتية التشغيل** ومطابقة لمنهجية المشروع الفعلية: GitHub + GitHub Actions + Supabase Dashboard.

## المسار المعتمد الآن

لا نطلب من المستخدم Terminal ولا ملف SQLite خارجيًا. بدل ذلك يبني CI Fixture حتمية تمثل كل جداول Legacy الـ25، ثم يمررها عبر نفس Compiler المستخدم لأي مصدر SQLite مستقبلي.

المخرجات المرجعية المحفوظة:

1. `supabase/tests/s2_e1b_representative_dry_run.sql`
2. `supabase/tests/s2_e1b_reconciliation.json`
3. `supabase/tests/s2_e1b_report.md`

## ما تغطيه Fixture

- جدولان دراسيان: 2025/2026 و2026/2027.
- معلم + ملف مهني + CV.
- `teacher_record_years -> teacher_years` مع إبقاء البيانات التاريخية غير المثبتة NULL.
- `request_record_years -> upload_requests.academic_year_id`.
- `event_record_years -> events.academic_year_id`.
- `event_media_meta -> event_media`.
- وثيقة Legacy محلية تتحول `local -> legacy_local`.
- أصل `google_drive` metadata.
- إعداد عادي + إعداد سري مستبعد Audit-only دون تسريب القيمة.
- الاجتماعات، التخطيط، الإشراف، التحصيل، الإجراءات، المقاييس، الأنشطة.

## حدود المرحلة

- لا Schema migration جديدة.
- لا تعديل RLS.
- لا Auth user mutation.
- لا Storage bytes migration.
- لا Runtime cutover.
- لا COMMIT.

## القبول الحي

بعد GitHub Actions GREEN شغّل:

`supabase/tests/s2_e1b_representative_dry_run.sql`

في Supabase SQL Editor. النتيجة المطلوبة:

`PASS: S2-E1 SQLite migration dry run`

ثم ينفذ الملف `ROLLBACK;`، فلا تبقى بيانات الاختبار.
