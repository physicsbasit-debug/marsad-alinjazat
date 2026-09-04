-- Marsad Al-Injazat — Phase S3-C3B
-- Public intake and private Supabase Storage for request-linked documents.

begin;

-- Private bucket. Storage object mutations stay behind the Storage API; only signed-in
-- owner/admin users receive SELECT permission through RLS for short-lived signed URLs.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'marsad-documents',
    'marsad-documents',
    false,
    26214400,
    array[
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'image/jpeg',
        'image/png'
    ]::text[]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists marsad_documents_manager_select on storage.objects;
create policy marsad_documents_manager_select
    on storage.objects
    for select
    to authenticated
    using (
        bucket_id = 'marsad-documents'
        and exists (
            select 1
              from public.school_memberships sm
             where sm.school_id::text = (storage.foldername(name))[1]
               and sm.user_id = (select auth.uid())
               and sm.status = 'active'
               and sm.role in ('owner', 'admin')
        )
    );

-- Authenticated managers create a request through a narrow RPC. The browser generates
-- the raw random token and sends only its SHA-256 digest to this function.
create or replace function public.marsad_create_upload_request_v1(
    p_school_id uuid,
    p_academic_year_id bigint,
    p_teacher_id bigint,
    p_request_type text,
    p_subject text,
    p_grade text,
    p_title text,
    p_deadline date,
    p_notes text,
    p_allowed_files text,
    p_token_hash text
)
returns table(id bigint, expires_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_id bigint;
    v_expires_at timestamptz;
    v_teacher_name text;
begin
    if (select auth.uid()) is null
       or not private.has_school_role(p_school_id, array['owner', 'admin']::text[]) then
        raise exception 'S3-C3B manager role required' using errcode = '42501';
    end if;

    if p_teacher_id is null or p_teacher_id <= 0 then
        raise exception 'invalid teacher id' using errcode = '22023';
    end if;
    if length(btrim(coalesce(p_request_type,''))) not between 1 and 120
       or length(btrim(coalesce(p_subject,''))) not between 1 and 80
       or length(btrim(coalesce(p_grade,''))) not between 1 and 40
       or length(btrim(coalesce(p_title,''))) not between 3 and 220
       or length(btrim(coalesce(p_allowed_files,''))) not between 1 and 200 then
        raise exception 'invalid request fields' using errcode = '22023';
    end if;
    if p_notes is not null and length(p_notes) > 2500 then
        raise exception 'request notes too long' using errcode = '22023';
    end if;
    if p_token_hash !~ '^[0-9a-f]{64}$' then
        raise exception 'invalid token hash' using errcode = '22023';
    end if;

    select t.name
      into v_teacher_name
      from public.teachers t
      join public.teacher_years ty
        on ty.school_id = t.school_id
       and ty.teacher_id = t.id
       and ty.academic_year_id = p_academic_year_id
       and ty.is_active
     where t.school_id = p_school_id
       and t.id = p_teacher_id
       and t.is_active;
    if not found then
        raise exception 'teacher not found in tenant/year scope' using errcode = 'P0002';
    end if;

    if not exists (
        select 1 from public.academic_years ay
         where ay.school_id = p_school_id
           and ay.id = p_academic_year_id
           and ay.is_current
    ) then
        raise exception 'request creation is limited to current academic year' using errcode = '22023';
    end if;

    v_expires_at := now() + interval '30 days';
    if p_deadline is not null then
        v_expires_at := greatest(v_expires_at, (p_deadline + 2)::timestamptz);
    end if;

    insert into public.upload_requests (
        school_id, academic_year_id, teacher_id, request_type, subject, grade,
        title, deadline, notes, allowed_files, token_hash, status, expires_at
    ) values (
        p_school_id, p_academic_year_id, p_teacher_id,
        btrim(p_request_type), btrim(p_subject), btrim(p_grade), btrim(p_title),
        p_deadline, nullif(btrim(coalesce(p_notes,'')),''), btrim(p_allowed_files),
        p_token_hash, 'waiting_upload', v_expires_at
    ) returning upload_requests.id into v_id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        p_school_id, p_academic_year_id, (select auth.uid()), 'request',
        'طلب ملف من ' || v_teacher_name, btrim(p_title), 'request', v_id
    );

    return query select v_id, v_expires_at;
end;
$$;

revoke all on function public.marsad_create_upload_request_v1(uuid,bigint,bigint,text,text,text,text,date,text,text,text)
    from public, anon;
grant execute on function public.marsad_create_upload_request_v1(uuid,bigint,bigint,text,text,text,text,date,text,text,text)
    to authenticated;

-- Called only by the server-side Edge Function after Storage upload. This function makes
-- metadata registration + request transition + activity insertion one transaction.
create or replace function public.marsad_register_public_upload_v1(
    p_request_id bigint,
    p_token_hash text,
    p_original_name text,
    p_mime_type text,
    p_size_bytes bigint,
    p_storage_bucket text,
    p_storage_path text
)
returns bigint
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_request public.upload_requests%rowtype;
    v_document_id bigint;
begin
    if p_token_hash !~ '^[0-9a-f]{64}$'
       or p_size_bytes <= 0 or p_size_bytes > 26214400
       or p_storage_bucket <> 'marsad-documents'
       or btrim(coalesce(p_storage_path,'')) = ''
       or btrim(coalesce(p_original_name,'')) = '' then
        raise exception 'invalid public upload registration' using errcode = '22023';
    end if;

    select ur.*
      into v_request
      from public.upload_requests ur
     where ur.id = p_request_id
       and ur.token_hash = p_token_hash
       and ur.expires_at >= now()
       and ur.status not in ('approved','cancelled')
     for update;
    if not found then
        raise exception 'public upload request unavailable' using errcode = 'P0002';
    end if;

    if p_storage_path not like v_request.school_id::text || '/' || v_request.academic_year_id::text || '/' || v_request.id::text || '/%' then
        raise exception 'storage path outside request scope' using errcode = '22023';
    end if;

    insert into public.documents (
        school_id, academic_year_id, request_id, teacher_id, title, category,
        subject, grade, original_name, mime_type, size_bytes, storage_provider,
        storage_bucket, storage_path, status
    ) values (
        v_request.school_id, v_request.academic_year_id, v_request.id, v_request.teacher_id,
        v_request.title, v_request.request_type, v_request.subject, v_request.grade,
        btrim(p_original_name), nullif(btrim(coalesce(p_mime_type,'')),''), p_size_bytes,
        'supabase', p_storage_bucket, p_storage_path, 'inbox'
    ) returning id into v_document_id;

    update public.upload_requests
       set status = 'review'
     where id = v_request.id;

    insert into public.activities (
        school_id, academic_year_id, actor_user_id, activity_type,
        title, detail, entity_type, entity_id
    ) values (
        v_request.school_id, v_request.academic_year_id, null, 'document',
        'استلام ' || btrim(p_original_name),
        'رفع عام آمن لطلب #' || v_request.id::text,
        'document', v_document_id
    );

    return v_document_id;
end;
$$;

revoke all on function public.marsad_register_public_upload_v1(bigint,text,text,text,bigint,text,text)
    from public, anon, authenticated;
grant execute on function public.marsad_register_public_upload_v1(bigint,text,text,text,bigint,text,text)
    to service_role;

commit;
