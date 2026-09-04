# Supabase acceptance tests

هذه الملفات تُشغل يدويًا في **Supabase SQL Editor** بعد migration المرحلة المقابلة وبعد GitHub Actions الأخضر.

- `s2_b2_live_acceptance.sql` — مجال المعلمين.
- `s2_b3_live_acceptance.sql` — المجالات التشغيلية.
- `s2_b4_live_acceptance.sql` — الطلبات/الوثائق/الفعاليات.
- `s2_b5_live_acceptance.sql` — قبول نهائي لكل مخطط S2-B قبل Auth/RLS.

كل اختبار حي يستخدم transaction وينتهي بـ`ROLLBACK` حتى لا يترك بيانات اختبار. S2-B5 لا يفترض حالة RLS موحدة لأن Supabase قد يفعّله تلقائيًا؛ لكنه يفرض أن browser grants والسياسات ما زالت صفرًا قبل S2-C.

### S2-B5 Fix 1

`s2_b5_live_acceptance.sql` intentionally performs INSERT + sleep + UPDATE inside one DO statement. This proves the trigger uses a wall-clock source (`clock_timestamp()`) rather than statement-scoped time.

### S2-C1 — Auth/RLS foundation

`s2_c1_live_acceptance.sql` requires one temporary Supabase Auth user created from Dashboard after the S2-C1 migration. It never mutates `auth.users` directly, tests real authenticated RLS behavior with that user, and rolls back all public tenant fixtures. Expected result: `PASS: S2-C1 security foundation acceptance`.

### S2-C2 — Domain RLS baseline

`s2_c2_live_acceptance.sql` reuses one real Auth user, tests owner/teacher/viewer/lead_teacher contexts across separate schools, verifies private-record isolation and locked trusted/storage writes, then rolls back all public fixtures. Expected result: `PASS: S2-C2 domain RLS baseline acceptance`.

### S2-D — Database acceptance and migration readiness

`s2_d_live_acceptance.sql` is acceptance-only and has no paired migration. It reuses one real Auth user, builds a rollback-protected complete fixture across the 26-table target and two schools, validates year isolation, RLS roles, critical constraints and referential behavior, and returns `PASS: S2-D database acceptance and migration readiness`. PASS authorizes only a controlled SQLite data-migration dry run, not runtime cutover.

- S2-D Fix 1 v0.24.1: corrected the SET NULL temporary-document fixture cleanup before role visibility assertions.
