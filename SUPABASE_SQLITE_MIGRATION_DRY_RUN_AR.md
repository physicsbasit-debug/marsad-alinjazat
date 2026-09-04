# S2-E1 — SQLite Migration Compiler & Controlled Dry Run

هذه المرحلة تحول **نسخة SQLite متسقة** إلى حزمة Dry Run قابلة للتشغيل يدويًا في Supabase SQL Editor. لا تضيف Migration للمخطط ولا تنقل بيانات إنتاجية نهائيًا.

## لماذا نحتاج Compiler قبل النقل الحقيقي؟

لأن المصدر يحتوي 25 جدول SQLite، بينما الهدف 26 جدول PostgreSQL مع دمج أربع علاقات Legacy وتغيير بنية السنة الدراسية والمعلم. النسخ المباشر صفًا بصف ليس نقلًا، بل طريقة متقدمة لصناعة أخطاء يصعب تفسيرها.

## الإدخال الحقيقي المطلوب

ملف نسخة احتياطية متسقة من:

`marsad_alinjazat.sqlite3`

يُفضّل إنشاؤه باستخدام `scripts/marsad_maintenance.py backup` بدل نسخ ملف قاعدة مفتوح مع WAL.

قاعدة التشغيل الحقيقية لا توجد في GitHub عمدًا لأن `.gitignore` يستبعد `*.sqlite3` و`data/`.

## المخرجات

يشغّل `scripts/marsad_sqlite_migration_compiler.py` ويولد:

1. `marsad_s2_e1_dry_run.sql`
2. `marsad_s2_e1_reconciliation.json`
3. `marsad_s2_e1_report.md`

ملف SQL يبدأ بـ`BEGIN` وينتهي إلزاميًا بـ`ROLLBACK;`، لذلك لا يعتمد أي بيانات دائمة.

## قواعد التحويل الأساسية

- مدرسة Dry Run اصطناعية ومحددة للمعاملة فقط.
- السنة الحالية يجب أن تُعطى صراحة ولا تُخمن.
- cutoff التاريخي للسنة الدراسية يبقى أغسطس كما في Legacy.
- `request_record_years` و`event_record_years` يندمجان في `academic_year_id`.
- `teacher_record_years` يندمج في `teacher_years`، والحقول التاريخية غير المثبتة تبقى `NULL`.
- `event_media_meta` يندمج في `event_media`.
- `local` يتحول إلى `legacy_local`.
- `storage_file_id` يُحفظ داخل `storage_path` فقط عند غياب مسار صريح.
- أسرار Legacy مثل refresh tokens لا تُصدر إلى SQL وتظهر كاستبعاد موثق بالعدد فقط.
- Auth users وschool_memberships وملفات التخزين الفعلية لا تُنقل هنا.

## معنى PASS

`PASS: S2-E1 SQLite migration dry run`

تعني أن نسخة SQLite الحقيقية أمكن تحميلها داخل Transaction مؤقتة مع تطابق أعداد الهدف ثم Rollback. لا تعني أن React تحول إلى Supabase، ولا أن FastAPI/SQLite يمكن حذفه بعد.
