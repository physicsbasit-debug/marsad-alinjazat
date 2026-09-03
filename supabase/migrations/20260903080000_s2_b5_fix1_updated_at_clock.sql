-- Marsad Al-Injazat — Phase S2-B5 Fix 1
-- Correct updated_at trigger clock semantics after live acceptance exposed
-- statement_timestamp() being constant for the whole SQL statement.
-- No tables, triggers, policies, grants, auth data, or storage data are changed.

begin;

create or replace function public.set_row_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
    new.updated_at := clock_timestamp();
    return new;
end;
$$;

-- Keep the helper trigger-only.
revoke all on function public.set_row_updated_at() from public, anon, authenticated;

commit;
