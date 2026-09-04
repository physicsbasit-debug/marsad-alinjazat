# S3-A — Supabase Auth والجلسة المدرسية

الإصدار: **v0.27.0**

## الهدف

إثبات أن واجهة مرصد الإنجازات تستطيع استخدام Supabase Auth ثم حل سياق المستخدم المدرسي عبر RLS قبل نقل أي وحدة تشغيلية من FastAPI/SQLite.

المسار المقصود:

`Auth session → profile → active school_membership → school → current academic_year`

## ما لا تفعله المرحلة

- لا تضيف Migration.
- لا تغير RLS.
- لا تنشئ مستخدمين أو عضويات.
- لا تنقل المعلمين أو الاجتماعات أو الوثائق أو أي مجال آخر.
- لا تغير `getBootstrap`; بيانات التطبيق التشغيلية ما تزال من FastAPI/SQLite.
- لا تستخدم role من Auth metadata. مصدر الصلاحية الوحيد هو `public.school_memberships`.

## GitHub Pages Live Diagnostic

Workflow يبقي `VITE_PREVIEW_MODE=true`، لكنه يمرر قيمتين browser-safe من **GitHub Repository Variables**:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

ولا تستخدم service-role أو secret key في المتصفح.

بعد ضبط المتغيرين وإعادة تشغيل GitHub Actions، افتح رابط GitHub Pages المعتاد وأضف:

`?auth-check=1`

مثال شكلي:

`https://<account>.github.io/marsad-alinjazat/?auth-check=1`

سجّل الدخول بحساب Auth الحقيقي. النجاح يجب أن يعرض:

`PASS: S3-A Auth & Tenant Session`

مع اسم المدرسة والدور والعام الدراسي الحالي.

## قيود مقصودة

S3-A تدعم عضوية مدرسية نشطة واحدة فقط للحساب. إذا ظهر أكثر من Tenant نشط تتوقف مغلقة بدل اختيار أحدها تلقائيًا. اختيار المدرسة المتعدد يؤجل لمرحلة مستقلة إذا أصبح مطلوبًا.
