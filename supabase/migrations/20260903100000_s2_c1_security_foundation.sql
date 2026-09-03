-- Marsad Al-Injazat — Phase S2-C1
-- Supabase Auth + RLS security foundation for the five core identity/tenancy tables.
-- Runtime remains React -> FastAPI -> SQLite. No domain runtime switches happen here.

begin;

-- Keep policy helper functions outside the exposed public schema.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to authenticated;
grant usage on schema private to supabase_auth_admin;

-- Active membership is the tenant-access primitive. Roles/status are read only from
-- public.school_memberships, never from mutable user_metadata claims.
create or replace function private.is_active_school_member(p_school_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.school_memberships sm
        where sm.school_id = p_school_id
          and sm.user_id = (select auth.uid())
          and sm.status = 'active'
    );
$$;

create or replace function private.has_school_role(p_school_id uuid, p_roles text[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.school_memberships sm
        where sm.school_id = p_school_id
          and sm.user_id = (select auth.uid())
          and sm.status = 'active'
          and sm.role = any (p_roles)
    );
$$;

-- A user may view their own public profile. School owners/admins may also resolve
-- public profile display names for accounts in a school they actively manage.
create or replace function private.can_view_profile(p_profile_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select
        p_profile_id = (select auth.uid())
        or exists (
            select 1
            from public.school_memberships caller
            join public.school_memberships target
              on target.school_id = caller.school_id
             and target.user_id = p_profile_id
            where caller.user_id = (select auth.uid())
              and caller.status = 'active'
              and caller.role in ('owner', 'admin')
        );
$$;

revoke all on function private.is_active_school_member(uuid) from public, anon, authenticated;
revoke all on function private.has_school_role(uuid, text[]) from public, anon, authenticated;
revoke all on function private.can_view_profile(uuid) from public, anon, authenticated;
grant execute on function private.is_active_school_member(uuid) to authenticated;
grant execute on function private.has_school_role(uuid, text[]) to authenticated;
grant execute on function private.can_view_profile(uuid) to authenticated;

-- Create the public profile automatically for future Supabase Auth users.
-- Only display-name metadata is copied. Authorization role/status is never trusted
-- from Auth user_metadata and is provisioned separately in school_memberships.
create or replace function private.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_display_name text;
begin
    v_display_name := nullif(
        btrim(
            coalesce(
                new.raw_user_meta_data ->> 'display_name',
                new.raw_user_meta_data ->> 'name',
                ''
            )
        ),
        ''
    );

    insert into public.profiles (id, display_name)
    values (new.id, v_display_name)
    on conflict (id) do nothing;

    return new;
end;
$$;

revoke all on function private.handle_new_auth_user() from public, anon, authenticated;
grant execute on function private.handle_new_auth_user() to supabase_auth_admin;

drop trigger if exists on_marsad_auth_user_created on auth.users;
create trigger on_marsad_auth_user_created
    after insert on auth.users
    for each row
    execute function private.handle_new_auth_user();

-- S2-C1 explicitly enables RLS on the five core tables even when a hosted project
-- has already auto-enabled it. The statement is idempotent.
alter table public.schools enable row level security;
alter table public.profiles enable row level security;
alter table public.school_memberships enable row level security;
alter table public.academic_years enable row level security;
alter table public.school_settings enable row level security;

-- Reset browser grants to a deterministic least-privilege baseline first.
revoke all on table public.schools from public, anon, authenticated;
revoke all on table public.profiles from public, anon, authenticated;
revoke all on table public.school_memberships from public, anon, authenticated;
revoke all on table public.academic_years from public, anon, authenticated;
revoke all on table public.school_settings from public, anon, authenticated;
revoke all on sequence public.academic_years_id_seq from public, anon, authenticated;

-- Signed-in users can read only rows admitted by RLS.
grant select on table public.schools to authenticated;
grant select on table public.profiles to authenticated;
grant select on table public.school_memberships to authenticated;
grant select on table public.academic_years to authenticated;
grant select on table public.school_settings to authenticated;

-- Narrow write grants. No browser role can create/delete a school, mutate
-- memberships, or create/delete profiles in S2-C1.
grant update (name, is_active) on table public.schools to authenticated;
grant update (display_name) on table public.profiles to authenticated;
grant insert (school_id, label, start_year, end_year, is_current)
    on table public.academic_years to authenticated;
grant update (label, start_year, end_year, is_current)
    on table public.academic_years to authenticated;
grant usage on sequence public.academic_years_id_seq to authenticated;
grant insert (school_id, key, value, updated_by)
    on table public.school_settings to authenticated;
grant update (value, updated_by)
    on table public.school_settings to authenticated;

-- Clean policy namespace for this phase. These names are phase-owned and are safe
-- to drop/recreate if the migration is replayed in an isolated test database.
drop policy if exists schools_select_active_members on public.schools;
drop policy if exists schools_update_owner on public.schools;
drop policy if exists profiles_select_self_or_school_managers on public.profiles;
drop policy if exists profiles_update_self on public.profiles;
drop policy if exists memberships_select_self_or_school_managers on public.school_memberships;
drop policy if exists academic_years_select_active_members on public.academic_years;
drop policy if exists academic_years_insert_managers on public.academic_years;
drop policy if exists academic_years_update_managers on public.academic_years;
drop policy if exists school_settings_select_active_members on public.school_settings;
drop policy if exists school_settings_insert_managers on public.school_settings;
drop policy if exists school_settings_update_managers on public.school_settings;

create policy schools_select_active_members
    on public.schools
    for select
    to authenticated
    using (private.is_active_school_member(id));

create policy schools_update_owner
    on public.schools
    for update
    to authenticated
    using (private.has_school_role(id, array['owner']::text[]))
    with check (private.has_school_role(id, array['owner']::text[]));

create policy profiles_select_self_or_school_managers
    on public.profiles
    for select
    to authenticated
    using (private.can_view_profile(id));

create policy profiles_update_self
    on public.profiles
    for update
    to authenticated
    using (id = (select auth.uid()))
    with check (id = (select auth.uid()));

create policy memberships_select_self_or_school_managers
    on public.school_memberships
    for select
    to authenticated
    using (
        user_id = (select auth.uid())
        or private.has_school_role(school_id, array['owner', 'admin']::text[])
    );

create policy academic_years_select_active_members
    on public.academic_years
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy academic_years_insert_managers
    on public.academic_years
    for insert
    to authenticated
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy academic_years_update_managers
    on public.academic_years
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create policy school_settings_select_active_members
    on public.school_settings
    for select
    to authenticated
    using (private.is_active_school_member(school_id));

create policy school_settings_insert_managers
    on public.school_settings
    for insert
    to authenticated
    with check (
        private.has_school_role(school_id, array['owner', 'admin']::text[])
        and (updated_by is null or updated_by = (select auth.uid()))
    );

create policy school_settings_update_managers
    on public.school_settings
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (
        private.has_school_role(school_id, array['owner', 'admin']::text[])
        and (updated_by is null or updated_by = (select auth.uid()))
    );

commit;
