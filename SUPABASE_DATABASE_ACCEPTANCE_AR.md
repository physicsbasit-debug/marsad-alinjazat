# S2-D — قبول قاعدة البيانات وجاهزية نقل البيانات

الإصدار: **v0.24.0**  
نقطة الأساس: **v0.23.0 / S2-C LIVE GREEN**.

## الهدف

هذه مرحلة قبول فقط. لا تضيف Migration جديدة، ولا تغيّر Schema أو RLS أو Runtime، ولا تنقل أي صف من SQLite. نجاحها يعني فقط أن PostgreSQL/Auth/RLS جاهزة لبدء **Dry Run مضبوط لنقل بيانات SQLite**.

## ما يثبته الاختبار الحي

- وجود الجداول الـ26 وتفعيل RLS عليها جميعًا، مع 69 Policy وغياب صلاحيات `anon`.
- وجود 22 Trigger لـ`updated_at` واستمرار استخدام `clock_timestamp()`.
- بناء بيانات مترابطة عبر الجداول الـ26 داخل مدرستين، ثم إثبات عزل المدرسة الثانية عبر كل الجداول الـ21 الدومينية.
- وجود عامين دراسيين واختبار عزل السنة في الجداول السنوية التسعة.
- صلاحيات `owner`, `admin`, `lead_teacher`, `teacher`, `viewer` وحالة `suspended`.
- قيود السنة الحالية الواحدة، `token_hash`، غلاف الفعالية الواحد، same-school FKs، حسابات التحصيل، قياس الأثر، ومزود التخزين.
- سلوك `CASCADE`, `SET NULL`, و`RESTRICT` الحرج.
- استمرار منع الكتابة المباشرة على الجداول المرتبطة بالـtrusted/storage flows.
- جميع بيانات الاختبار داخل Transaction واحدة وتنتهي بـ`ROLLBACK`.

## Manifest نقل البيانات

`supabase/schema/s2_d_data_migration_manifest.json` يغطي جداول SQLite الـ25 والجداول المستهدفة الـ26 ويثبت قواعد التحويل المجمدة من S2-A. لا يسمح بإسقاط صفوف بصمت أو اختلاق خصائص سنوية تاريخية للمعلم.

النقاط الجديدة `schools`, `academic_years`, `profiles`, و`school_memberships` لا تُملأ بالتخمين: هوية المدرسة مدخل صريح، الأعوام تُستخرج وفق قواعد التوافق المجمدة، وحسابات Auth/العضويات تُجهز عبر مسار موثوق مستقل.

## ما لا يعنيه PASS

PASS لا يعني أن React تحولت إلى Supabase ولا أن FastAPI/SQLite أزيلت. كما لا يشمل نقل bytes الملفات أو Storage Policies أو Public Upload Edge Function. هذه بوابة جاهزية **لنقل البيانات التجريبي فقط**.

النتيجة المطلوبة من Supabase SQL Editor:

```text
PASS: S2-D database acceptance and migration readiness
```
