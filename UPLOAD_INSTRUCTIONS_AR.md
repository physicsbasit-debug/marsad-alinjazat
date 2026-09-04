# رفع S3-C3A v0.33.0

1. ارفع محتويات حزمة `changed_files_only` فوق `main`.
2. لا يوجد تعديل على `.env.example` في هذه المرحلة، لتجنب مشكلة الملفات المخفية المتكررة. الوضع المحلي الافتراضي يبقى Legacy عند غياب المتغير.
3. انتظر نجاح `Quality & Live Preview`، بما في ذلك `S3-C3A requests/documents review cutover`.
4. بعد GitHub GREEN فقط شغّل Migration S3-C3A في Supabase SQL Editor.
5. شغّل Live Acceptance وتأكد من ظهور PASS.
6. لا تشغّل أي SQL خاص بـStorage أو Public Upload في هذه المرحلة.
