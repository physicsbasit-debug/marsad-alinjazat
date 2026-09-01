# مرصد الإنجازات — Phase S1: Supabase Foundation

## هدف المرحلة

إدخال Supabase إلى المستودع كبنية تطوير رسمية **من دون نقل أي جدول أو تحويل أي شاشة إلى Supabase بعد**.

مصدر التشغيل في نهاية S1 يبقى:

```text
React → src/lib/api.ts → FastAPI → SQLite
```

وفي المقابل تصبح البنية التالية جاهزة للمرحلة اللاحقة:

```text
src/lib/supabase.ts
supabase/config.toml
supabase/migrations/
supabase/functions/
supabase/tests/
```

## ما أضيف

- `@supabase/supabase-js` مثبت مباشرة على `2.112.4`.
- Supabase CLI مثبت كاعتماد تطوير على `2.116.0`.
- Node المطلوب أصبح `>=22` لأن إصدارات Supabase JS الحديثة لم تعد تدعم Node 20.
- `.env.example` يوثق فقط:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_PUBLISHABLE_KEY`
- `src/lib/supabase.ts` يبني عميلًا واحدًا بصورة lazy ولا يستهلكه أي مسار إنتاجي في S1.
- `supabase/config.toml` يثبت هوية المشروع المحلي وإعداد Auth المحلي الأساسي.
- `supabase/seed.sql` موجود لكن بلا بيانات تطبيقية.
- `supabase/migrations/` موجود لكن بلا SQL في S1 عمدًا.
- `scripts/check_supabase_foundation.py` يمنع:
  - إدخال Secret/Service Role إلى `src/`.
  - استخدام Supabase من صفحات التطبيق قبل أوانه.
  - إضافة migration ضمن S1 بصورة عرضية.
  - فقدان مسار FastAPI/SQLite القديم.

## قرار المفاتيح

في الواجهة نستخدم **Publishable Key** فقط. لا يوضع `service_role` ولا أي `sb_secret_*` ولا متغير Vite سري داخل التطبيق. العمليات التي تحتاج صلاحية مرتفعة ستنفذ لاحقًا داخل Edge Functions مع أسرار خادمية فقط.

## حدود المرحلة

S1 لا تفعل أيًا من الآتي:

- لا تنشئ جداول PostgreSQL.
- لا تنقل بيانات SQLite.
- لا تفعل Supabase Auth في واجهة المستخدم.
- لا تنشئ Storage bucket.
- لا تضيف RLS policies.
- لا تغير GitHub Pages من Preview إلى تطبيق حي.
- لا تحذف FastAPI أو SQLite أو Google Drive.

## أوامر التطوير بعد تثبيت الاعتماديات

```bash
npm install
npm run supabase:start
npm run supabase:status
npm run supabase:stop
```

عند بدء المهاجرات في مرحلة لاحقة:

```bash
npm run supabase:db-reset
```

## معيار القبول

يجب أن تمر جميع اختبارات S0 السابقة دون تغيير، ثم ينجح:

```bash
python scripts/check_supabase_foundation.py
```

كما يجب أن ينجح `npm run check` بعد تنزيل الاعتماديات من npm.

## الخطوة التالية بعد إغلاق S1

**Phase S2-A — PostgreSQL Schema Design Freeze**

تُجمّد فيها بنية PostgreSQL والملكية والأعوام والمفاتيح وقواعد تحويل جداول SQLite الـ25 قبل كتابة أي SQL تطبيقي. بعد نجاح S2-A تبدأ S2-B كأول مرحلة migrations فعلية، ثم S2-C للمصادقة وRLS وS2-D لاختبارات القبول.
