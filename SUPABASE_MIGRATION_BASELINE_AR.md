# مرصد الإنجازات — Phase S0: Supabase Migration Baseline

هذه الوثيقة تثبت خط الأساس الذي يجب الحفاظ على سلوكه أثناء الانتقال من FastAPI + SQLite إلى Supabase. لا تعتبر ملفات Railway الموجودة في المستودع دليلًا على تشغيل Railway؛ لم يتم تشغيل المشروع إنتاجيًا على Railway حتى تاريخ هذا الخط الأساسي.

## 1. نقطة الصفر المعتمدة

- المصدر: الملف المرفوع `marsad-alinjazat-main(1).zip`.
- إصدار الواجهة: `0.14.0`.
- FastAPI يعلن الإصدار `0.14.0`.
- قاعدة البيانات الحالية: SQLite.
- تخزين الملفات الحالي في الاختبار: Local storage.
- GitHub Pages: Preview فقط، والحفظ معطل عبر `VITE_PREVIEW_MODE=true`.
- Railway: تجهيز غير مستخدم تشغيليًا، وليس مصدر بيانات ولا بيئة يجب ترحيلها.

## 2. عقود السلامة المضافة في S0

### عقد البنية القديمة

يشغّل:

```bash
python scripts/check_marsad_baseline.py
```

ويتحقق من:

1. بقاء 25 جدول SQLite في خط الأساس قبل بدء الهجرة.
2. بقاء 63 مسار HTTP في FastAPI قبل استبدالها تدريجيًا.
3. عدم ظهور `fetch()` مباشر في صفحات الواجهة خارج `src/lib/api.ts`.
4. بقاء حارس GitHub Pages Preview.
5. تطابق نسخة GitHub Workflow الحقيقية مع النسخة المرئية الاحتياطية.
6. وجود اختبار HTTP End-to-End في CI.

هذا الحارس مؤقت خلال الهجرة. يتم تحديثه عمدًا في كل مرحلة Supabase عند استبدال عقد قديم بعقد جديد، ولا يحذف بصمت.

### اختبار HTTP End-to-End

يشغّل:

```bash
python scripts/marsad_e2e_regression.py
```

ويشغّل Uvicorn فعليًا على منفذ محلي عشوائي ثم يمر عبر HTTP في السلسلة التالية:

```text
health / ready
→ معلم
→ ملف مهني + CV
→ اجتماع + قرار
→ خطة + وحدة
→ زيارة + متابعة
→ تقويم + تدخل + قياس أثر
→ فعالية + دليل
→ وثيقة مباشرة
→ طلب ملف + رابط رفع عام + رفع ملف
→ بحث
→ التقارير الرسمية
→ الأرشيف والفصل بين السنوات
→ إيقاف الخادم
→ SQLite integrity/fk check
→ إعادة تشغيل الخادم
→ إثبات استمرار السجلات
```

## 3. خريطة البيانات الحالية: 25 جدولًا

### النظام والهوية التشغيلية

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `settings` | إعدادات عامة | جدول إعدادات محدود + RLS |
| `activities` | سجل النشاط | `activities` مع هوية المنفذ لاحقًا |

### المعلمون

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `teachers` | الهوية المهنية الأساسية | `teachers` |
| `teacher_profiles` | تفاصيل الملف المهني | دمج أو `teacher_profiles` بعد مراجعة العقد |
| `teacher_cv_items` | عناصر السيرة الذاتية | `teacher_cv_items` |
| `teacher_record_years` | ارتباط المعلم بالأعوام | `teacher_years` أو علاقة صريحة محسنة |

### الطلبات والوثائق

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `upload_requests` | طلبات الملفات وروابط الرفع | `upload_requests` |
| `request_record_years` | سنة الطلب | مراجعة دمجها في الطلب نفسه |
| `documents` | Metadata للوثائق | `documents` + Supabase Storage |

### الفعاليات

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `events` | سجل الفعالية | `events` |
| `event_record_years` | سنة الفعالية | مراجعة دمجها في `events` |
| `event_teacher_links` | المشاركون من المعلمين | `event_teacher_links` |
| `event_media` | Metadata للأدلة | `event_media` + Storage |
| `event_media_meta` | ترتيب/غلاف/تعليق | دمج مدروس مع `event_media` إن أمكن |

### الاجتماعات

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `meetings` | الاجتماعات | `meetings` |
| `meeting_attendees` | الحضور | `meeting_attendees` |
| `meeting_decisions` | القرارات والمتابعة | `meeting_decisions` |

### التخطيط والمنهج

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `curriculum_plans` | الخطط | `curriculum_plans` |
| `curriculum_units` | الوحدات ونسب الإنجاز | `curriculum_units` |

### الإشراف

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `supervision_visits` | الزيارات | `supervision_visits` |
| `supervision_actions` | إجراءات المتابعة | `supervision_actions` |

### التحصيل والتدخل

| الجدول | الوظيفة | هدف Supabase المتوقع |
|---|---|---|
| `achievement_assessments` | التقويمات والنتائج | `achievement_assessments` |
| `achievement_assessment_standards` | مرجع حد الإتقان | إبقاؤه منفصلًا مبدئيًا للحفاظ على التدقيق |
| `achievement_actions` | التدخلات | `achievement_actions` |
| `achievement_action_metrics` | قياس الأثر | `achievement_action_metrics` |

## 4. خريطة المجالات إلى الحدود الحالية

| المجال | واجهة React | طبقة الشبكة | FastAPI | الجداول الأساسية |
|---|---|---|---|---|
| Dashboard | `Dashboard.tsx` | `api.ts:getBootstrap` | `/api/bootstrap` | معظم الجداول عبر التجميع |
| المعلمون | `Teachers.tsx` | Teacher API functions | `/api/teachers*` | teachers/profile/cv/year |
| التخطيط | `Planning.tsx` | Planning API functions | `/api/plans*` | curriculum_plans/units |
| التحصيل | `Achievement.tsx` | Achievement API functions | `/api/achievement*` | assessments/actions/metrics/standards |
| الإشراف | `Supervision.tsx` | Supervision API functions | `/api/supervision*` | visits/actions |
| الطلبات | `Requests.tsx`, `PublicUpload.tsx` | Request API functions | `/api/requests*`, `/api/public/upload*` | requests/documents/year |
| الاجتماعات | `Meetings.tsx` | Meeting API functions | `/api/meetings*` | meetings/attendees/decisions |
| الفعاليات | `Events.tsx` | Event API functions | `/api/events*` | events/teacher links/media/meta/year |
| الوثائق | `Documents.tsx` | Document API functions | `/api/documents` | documents |
| التقارير | `Reports.tsx` | `getOfficialReport` | `/api/reports/official` | تجميع متعدد المجالات |
| الأرشيف | `Archive.tsx` | Archive API functions | `/api/archive/*` | تجميع حسب العام |
| البحث | `GlobalSearch.tsx` | `searchGlobal` | `/api/search` | بحث متعدد المجالات |

## 5. عقود Parity التي لا يجوز كسرها

الهجرة إلى Supabase لا تعد ناجحة بمجرد ظهور البيانات. يجب إثبات العقود التالية لكل مجال قبل إيقاف مساره القديم:

1. **عزل العام الدراسي:** السجل التاريخي لا يظهر في Dashboard العام الجاري.
2. **هوية المعلم عبر السنوات:** لا تنشأ نسخة معلم مكررة لمجرد استخدامه في عام سابق.
3. **سلامة العلاقات:** منع المراجع إلى معلم/اجتماع/خطة/زيارة/تقويم غير موجود.
4. **التحصيل:** مجموع mastered + near mastery + intervention لا يتجاوز عدد الطلبة، والدرجات لا تتجاوز الدرجة الكلية.
5. **مرجع الإتقان:** لا تجمع نسب إتقان من معايير غير متكافئة وكأنها معيار واحد.
6. **التدخل وقياس الأثر:** baseline/target/outcome واتجاه المؤشر تبقى مترابطة ولا ينتج حكم أثر بلا قياس صالح.
7. **طلبات الرفع:** token صالح، انتهاء صلاحية، إغلاق الطلب، نوع الملف وحجمه كلها تتحقق قبل التخزين.
8. **الملفات:** Metadata والسجل الفعلي في Storage يبقيان متسقين.
9. **البحث:** النتيجة تحمل المجال والعام والكيان الصحيح ويمكن فتح السجل الأصلي.
10. **التقارير:** الأرقام مشتقة من بيانات المجال نفسها ولا تعتمد على أرقام Preview.
11. **Restart / Persistence:** بعد التحويل يصبح المكافئ هو بقاء البيانات بعد refresh/logout/login وإعادة فتح التطبيق، مع التحقق من Postgres/Storage بدل SQLite.
12. **GitHub Pages:** لا يتحول إلى تطبيق حقيقي قبل اكتمال Auth + RLS للمرحلة المنشورة.

## 6. ترتيب الهجرة المعتمد بعد S0

```text
S1  Supabase Foundation
S2  PostgreSQL schema + migrations + RLS skeleton
S3  Auth / profiles / ownership model
S4  Teachers vertical slice
S5  Meetings
S6  Planning
S7  Supervision
S8  Achievement
S9  Events + Storage
S10 Documents + public upload Edge Function
S11 Reports + archive + search
S12 SQLite migration + parity audit
S13 Legacy FastAPI/SQLite retirement
```

قد تقسم أي مرحلة إلى A/B إذا أظهر فحص End-to-End أن نطاقها أكبر من تغيير آمن واحد.

## 7. ما لا نفعله في S0

- لا نحذف FastAPI.
- لا نحذف SQLite.
- لا نحذف ملفات Railway بعد؛ تعتبر Legacy غير مستخدمة إلى مرحلة تنظيف مستقلة.
- لا نغيّر المنطق التربوي.
- لا ننقل ملفات إلى Supabase Storage.
- لا نضيف Auth أو RLS بعد.
- لا نغيّر GitHub Pages من Preview إلى Production.

## 8. ملاحظة dependency lock

المستودع الأصلي لا يحتوي `package-lock.json`. يجب إنشاء lockfile موثوق باستخدام npm registry ثم تحويل CI إلى `npm ci`. بيئة إعداد S0 الحالية لم تستطع الوصول إلى npm registry بصورة مستقرة، لذلك **لم يتم تصنيع lockfile يدوي أو مزيف**. يبقى هذا بندًا مفتوحًا يجب إغلاقه قبل S1 أو في أول بيئة CI/CodeSpace قادرة على توليده والتحقق من `npm ci`.

هذا أفضل من إدخال lockfile غير موثوق فقط لإغلاق مربع في قائمة مهام.
