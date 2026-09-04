-- Marsad Al-Injazat — Phase S3-C3A
-- Requests/documents management cutover: read from Supabase + manager-only request status review.
-- Public upload, request creation, and Storage remain explicitly deferred.

begin;

-- Narrow manager review grants. No request/document INSERT is enabled here.
grant update (status) on table public.upload_requests to authenticated;
grant update (status, approved_at) on table public.documents to authenticated;

drop policy if exists upload_requests_update_managers on public.upload_requests;
create policy upload_requests_update_managers
    on public.upload_requests
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

drop policy if exists documents_update_managers on public.documents;
create policy documents_update_managers
    on public.documents
    for update
    to authenticated
    using (private.has_school_role(school_id, array['owner', 'admin']::text[]))
    with check (private.has_school_role(school_id, array['owner', 'admin']::text[]));

create or replace function public.marsad_update_upload_request_status_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_request_id bigint,
    p_status text
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_title text;
begin
    if not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C3A manager role required' using errcode = '42501';
    end if;

    if p_status not in ('waiting_upload', 'received', 'review', 'approved', 'needs_revision', 'late', 'cancelled') then
        raise exception 'invalid upload request status' using errcode = '22023';
    end if;

    select ur.title
      into v_title
      from public.upload_requests ur
     where ur.school_id = p_school_id
       and ur.academic_year_id = p_academic_year_id
       and ur.id = p_request_id
     for update;
    if not found then
        raise exception 'upload request not found in tenant/year scope' using errcode = 'P0002';
    end if;

    update public.upload_requests ur
       set status = p_status
     where ur.school_id = p_school_id
       and ur.academic_year_id = p_academic_year_id
       and ur.id = p_request_id;

    if p_status = 'approved' then
        update public.documents d
           set status = 'approved',
               approved_at = coalesce(d.approved_at, now())
         where d.school_id = p_school_id
           and d.academic_year_id = p_academic_year_id
           and d.request_id = p_request_id;
    end if;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, p_academic_year_id, (select auth.uid()), 'request',
        'تحديث حالة طلب ملف',
        v_title || ' ← ' || p_status,
        'request', p_request_id
    );
end;
$$;

revoke all on function public.marsad_update_upload_request_status_v1(uuid,bigint,bigint,text) from public, anon;
grant execute on function public.marsad_update_upload_request_status_v1(uuid,bigint,bigint,text) to authenticated;

commit;
