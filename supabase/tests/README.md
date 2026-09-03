# Supabase acceptance tests

هذه الملفات تُشغل يدويًا في **Supabase SQL Editor** بعد migration المرحلة المقابلة وبعد GitHub Actions الأخضر.

- `s2_b2_live_acceptance.sql` — مجال المعلمين.
- `s2_b3_live_acceptance.sql` — المجالات التشغيلية.
- `s2_b4_live_acceptance.sql` — الطلبات/الوثائق/الفعاليات.
- `s2_b5_live_acceptance.sql` — قبول نهائي لكل مخطط S2-B قبل Auth/RLS.

كل اختبار حي يستخدم transaction وينتهي بـ`ROLLBACK` حتى لا يترك بيانات اختبار. S2-B5 لا يفترض حالة RLS موحدة لأن Supabase قد يفعّله تلقائيًا؛ لكنه يفرض أن browser grants والسياسات ما زالت صفرًا قبل S2-C.

### S2-B5 Fix 1

`s2_b5_live_acceptance.sql` intentionally performs INSERT + sleep + UPDATE inside one DO statement. This proves the trigger uses a wall-clock source (`clock_timestamp()`) rather than statement-scoped time.
