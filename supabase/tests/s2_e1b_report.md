# S2-E1 SQLite Migration Dry-Run Report

- Source: `marsad_alinjazat.sqlite3`
- SHA-256: `f856c70a821403b2cfdf8cb142825b8a57ca318be5666281a5087634eb77377c`
- SQLite integrity: **PASS**
- Foreign-key violations: **0**
- Dry-run school UUID: `897b2a8a-4f44-5ce1-b870-cc5bc74f2a7f`
- Current academic year: `2026/2027`
- Source tables: **25/25**
- Target tables represented in dry run: **24/26** (profiles/memberships intentionally excluded)
- Secret settings excluded with audit trail: **1**
- Storage file IDs folded into storage_path metadata: **1**
- Storage bytes moved: **No**
- Runtime cutover: **No**
- Live commit: **No**

## Academic years

- `2025/2026`
- `2026/2027`

## Gate

Run `marsad_s2_e1_dry_run.sql` in Supabase SQL Editor. Required result:

`PASS: S2-E1 SQLite migration dry run`

The SQL ends with `ROLLBACK;`; any missing rollback is a hard failure.
