# مرصد الإنجازات — Phase S2-B1: Core Identity & Tenancy

## الهدف

هذه أول migration PostgreSQL تشغيلية في مسار الانتقال إلى Supabase. نطاقها محصور في طبقة الهوية والعزل الأساسية فقط:

- `schools`
- `profiles`
- `school_memberships`
- `academic_years`

لا تنقل هذه المرحلة أي بيانات من SQLite، ولا تربط React بـSupabase، ولا تنفذ RLS. يبقى مسار التشغيل الحالي:

```text
React → src/lib/api.ts → FastAPI → SQLite
```

## ملف migration

```text
supabase/migrations/20260901120000_s2_b1_core_identity_tenancy.sql
```

العقد الآلي للمرحلة:

```text
supabase/schema/s2_b1_core_identity_contract.json
scripts/check_supabase_s2_b1.py
```

## الجداول

### schools

جذر العزل بين المدارس. المفتاح UUID ويولد داخل PostgreSQL، مع اسم غير فارغ وحالة تفعيل وتواريخ إنشاء/تحديث.

### profiles

ملف التطبيق العام للمستخدم. `profiles.id` يطابق `auth.users.id` ويُحذف تلقائيًا عند حذف مستخدم Auth.

لا تنشئ S2-B1 trigger لإنشاء profile تلقائيًا؛ هذا جزء من S2-C عندما نفعل Auth/RLS فعليًا.

### school_memberships

يربط المستخدم بالمدرسة ويحدد دوره وحالة عضويته. الأدوار المجمدة:

```text
owner
admin
lead_teacher
teacher
viewer
```

والحالات:

```text
active
invited
suspended
```

`teacher_id` موجود الآن كـ`bigint NULL`، لكن المفتاح الخارجي إلى `teachers` **مؤجل عمدًا إلى S2-B2** لأن جدول `teachers` لم يُنشأ بعد. في S2-B2 يجب أن يكون الربط مركبًا على `(school_id, teacher_id)` حتى لا يمكن ربط حساب مدرسة بمعلم من مدرسة أخرى.

### academic_years

قاموس الأعوام الدراسية لكل مدرسة. يفرض:

- `end_year = start_year + 1`
- `label` بصيغة `YYYY/YYYY`
- تطابق `label` مع `start_year/end_year`
- عدم تكرار نفس العام داخل المدرسة
- وجود عام واحد فقط `is_current=true` لكل مدرسة عبر Partial Unique Index

لا تدخل S2-B1 تواريخ فصول أو بداية عام دراسي غير مثبتة في المصدر.

## الأمن قبل RLS

RLS نفسه مؤجل إلى S2-C. لكن إنشاء جداول عامة بلا حماية مؤقتة سيكون خطأً أمنيًا، لذلك تنفذ migration قاعدة deny-by-default:

```text
REVOKE ALL ... FROM PUBLIC, anon, authenticated
```

على الجداول الأربعة، وكذلك sequence الخاص بـ`academic_years`.

بالتالي لا تستطيع الواجهة استعمال هذه الجداول عبر Data API حتى S2-C التي ستضيف Grants/RLS بصورة صريحة ومدروسة.

## ما لا تفعله المرحلة

- لا `CREATE POLICY`.
- لا `ENABLE ROW LEVEL SECURITY`.
- لا Edge Functions.
- لا Storage buckets.
- لا بيانات Seed تطبيقية.
- لا نقل SQLite.
- لا تعديل React runtime.
- لا تعديل FastAPI runtime.
- لا إنشاء جدول `teachers` بعد.

## الاختبارات

يجب نجاح:

```bash
python scripts/check_marsad_baseline.py
python scripts/check_supabase_foundation.py
python scripts/check_supabase_schema_freeze.py
python scripts/check_supabase_s2_b1.py
python -m pytest -q
python scripts/marsad_e2e_regression.py
```

`check_supabase_s2_b1.py` يثبت آليًا أن:

- عقد S2-A لم يتغير.
- توجد migration واحدة فقط في S2-B1.
- لا تُنشأ إلا الجداول الأربعة.
- `profiles.id` مرتبط بـ`auth.users`.
- قيود الدور والحالة صحيحة.
- FK الخاص بـ`teacher_id` لم يسبق جدول `teachers`.
- العام الحالي واحد فقط لكل مدرسة.
- الجداول مقفلة عن أدوار المتصفح إلى حين S2-C.
- لا RLS ولا DML ولا Runtime Switch في هذه المرحلة.

## اختبار PostgreSQL الحقيقي

بيئة تجهيز الحزمة لا تملك PostgreSQL/Supabase local stack، لذلك الاختبارات المحلية هنا تثبت العقد البنيوي والـRegression ولا تدّعي تنفيذ migration داخل PostgreSQL فعلي.

بعد أخضر GitHub Actions، يجب تطبيق migration على بيئة Supabase تطويرية أو Local Supabase وتشغيل `db reset`/قبول PostgreSQL الحقيقي قبل إغلاق S2-B1 تشغيليًا. لا تعتبر مجرد نجاح الفحص النصي بديلًا عن تطبيق قاعدة البيانات.

## التالي

بعد تطبيق S2-B1 بنجاح على PostgreSQL واختبارها:

**Phase S2-B2 — Teachers Core**

وتنشئ `teachers`, `teacher_profiles`, `teacher_years`, `teacher_cv_items` ثم تكمل FK المؤجل في `school_memberships.teacher_id`.
