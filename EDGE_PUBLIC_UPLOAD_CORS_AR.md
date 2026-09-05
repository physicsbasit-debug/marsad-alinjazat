# S3-C3B R2 — تصحيح CORS للرفع العام

## العطل الحي
بعد نجاح توجيه GitHub Pages، ظهرت واجهة الرفع العامة لكن فشل التحقق من رابط الطلب قبل عرض تفاصيله.

## السبب الجذري
الواجهة تستدعي `marsad-public-upload` عبر `supabase.functions.invoke`. متصفح الويب ينفذ CORS preflight قبل POST، وSupabase JS يرسل رؤوسًا منها `authorization`, `apikey`, `x-client-info`, و`content-type`. النسخة السابقة سمحت يدويًا فقط بـ `apikey, content-type, x-client-info`، فكان المتصفح يمنع الطلب بسبب غياب `authorization` من قائمة الرؤوس المسموحة.

## التصحيح
تستخدم الوظيفة الآن `corsHeaders` المصدرة رسميًا من `@supabase/supabase-js/cors` بدل قائمة يدوية ناقصة، مع الإبقاء على POST/OPTIONS و`Cache-Control: no-store`.

## الحدود
لا تغيير على قاعدة البيانات، bucket، RPCs، token hashing، signed URLs، orphan cleanup، أو واجهة العميل. المطلوب تشغيليًا فقط إعادة نشر Edge Function `marsad-public-upload` بعد اعتماد GitHub Actions.
