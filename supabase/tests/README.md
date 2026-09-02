# Supabase acceptance tests

- S2-B1: مقبول حيًا على Supabase.
- S2-B2: مقبول حيًا على Supabase.
- S2-B3: مقبول حيًا بعد تحديث اختبار القبول ليدعم auto-RLS الآمن. تم التحقق من صفر Policies وصفر browser grants.
- S2-B4: `s2_b4_live_acceptance.sql` يُشغل بعد GitHub Actions الأخضر وتطبيق migration الرابعة.

اختبارات S2-B4 تعمل داخل transaction وتنتهي بـ`ROLLBACK`. سياسات RLS الفعلية تبدأ في S2-C/S2-D.
