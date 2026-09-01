# Supabase acceptance tests

تضاف هنا اختبارات PostgreSQL/RLS الحية مع تقدم مراحل النقل.

في S2-B1 يوجد فحص بنيوي آلي في `scripts/check_supabase_s2_b1.py`. اختبار تطبيق migration داخل PostgreSQL/Supabase فعلي يبقى بوابة إغلاق تشغيلية إلزامية قبل الانتقال من S2-B إلى الاعتماد على القاعدة الجديدة. اختبارات RLS نفسها تبدأ في S2-C/S2-D.
