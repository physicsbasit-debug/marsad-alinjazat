import { createClient } from 'npm:@supabase/supabase-js@2.112.4';
import { corsHeaders as supabaseCorsHeaders } from 'npm:@supabase/supabase-js@2.112.4/cors';

const BUCKET = 'marsad-documents';
const MAX_BYTES = 25 * 1024 * 1024;
const EXTENSION_MIME: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.doc': 'application/msword',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.xls': 'application/vnd.ms-excel',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.ppt': 'application/vnd.ms-powerpoint',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
};

const corsHeaders = {
  ...supabaseCorsHeaders,
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Cache-Control': 'no-store',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
  });
}

class ResponseError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function parseNamedKey(raw: string | undefined, name: string): string | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, string>;
    return parsed[name] || null;
  } catch {
    return null;
  }
}

function publishableKey(): string {
  const modern = parseNamedKey(Deno.env.get('SUPABASE_PUBLISHABLE_KEYS'), 'default');
  if (modern) return modern;
  const legacy = Deno.env.get('SUPABASE_ANON_KEY');
  if (legacy) return legacy;
  throw new Error('Supabase publishable key is unavailable.');
}

type ServerCredential = { key: string; modern: boolean };

function serverCredential(): ServerCredential {
  const modern = parseNamedKey(Deno.env.get('SUPABASE_SECRET_KEYS'), 'default');
  if (modern) return { key: modern, modern: true };
  const legacy = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (legacy) return { key: legacy, modern: false };
  throw new Error('Supabase server secret is unavailable.');
}

function adminClient() {
  const url = Deno.env.get('SUPABASE_URL');
  if (!url) throw new Error('SUPABASE_URL is unavailable.');
  const credential = serverCredential();
  if (!credential.modern) {
    return createClient(url, credential.key, { auth: { persistSession: false, autoRefreshToken: false } });
  }

  const secretKeyFetch: typeof fetch = async (input, init) => {
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, name) => headers.set(name, value));
    headers.set('apikey', credential.key);
    if (headers.get('authorization') === `Bearer ${credential.key}`) headers.delete('authorization');
    return fetch(input, { ...init, headers });
  };

  return createClient(url, credential.key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { fetch: secretKeyFetch },
  });
}

async function authenticatedUserId(request: Request): Promise<string> {
  const authorization = request.headers.get('authorization') || '';
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match) throw new ResponseError(401, 'يجب تسجيل الدخول قبل رفع الوثيقة.');

  const url = Deno.env.get('SUPABASE_URL');
  if (!url) throw new Error('SUPABASE_URL is unavailable.');
  const authClient = createClient(url, publishableKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await authClient.auth.getUser(match[1]);
  if (error || !data.user) throw new ResponseError(401, 'جلسة المستخدم غير صالحة أو انتهت.');
  return data.user.id;
}

function cleanText(value: FormDataEntryValue | null, max: number, label: string, required = false): string {
  const text = String(value || '').trim();
  if (required && !text) throw new ResponseError(422, `${label} مطلوب.`);
  if (text.length > max) throw new ResponseError(422, `${label} أطول من المسموح.`);
  return text;
}

function positiveInteger(value: FormDataEntryValue | null, label: string): number {
  const parsed = Number(String(value || '').trim());
  if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new ResponseError(422, `${label} غير صالح.`);
  return parsed;
}

function optionalPositiveInteger(value: FormDataEntryValue | null, label: string): number | null {
  const raw = String(value || '').trim();
  if (!raw) return null;
  return positiveInteger(raw, label);
}

function safeName(value: string): string {
  const base = value.split(/[\\/]/).pop()?.trim() || 'file';
  return base.replace(/[\u0000-\u001f<>:"|?*]+/g, '_').slice(0, 180) || 'file';
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.');
  return index >= 0 ? name.slice(index).toLowerCase() : '';
}

async function rollbackCreatedDocument(
  supabase: ReturnType<typeof adminClient>,
  documentId: number | null,
  storagePath: string | null,
): Promise<void> {
  if (documentId) {
    const deletion = await supabase.from('documents').delete().eq('id', documentId);
    if (deletion.error) console.error('direct document metadata cleanup failed', deletion.error);
  }
  if (storagePath) {
    const removal = await supabase.storage.from(BUCKET).remove([storagePath]);
    if (removal.error) console.error('direct document storage cleanup failed', removal.error);
  }
}

async function upload(request: Request): Promise<Response> {
  const userId = await authenticatedUserId(request);
  const form = await request.formData();
  const schoolId = cleanText(form.get('schoolId'), 64, 'معرف المدرسة', true);
  const academicYearId = positiveInteger(form.get('academicYearId'), 'معرف العام الدراسي');
  const teacherId = optionalPositiveInteger(form.get('teacherId'), 'معرف المعلم');
  const title = cleanText(form.get('title'), 220, 'عنوان الوثيقة', true);
  const category = cleanText(form.get('category'), 120, 'تصنيف الوثيقة', true) || 'وثيقة';
  const subject = cleanText(form.get('subject'), 80, 'المادة');
  const grade = cleanText(form.get('grade'), 40, 'الصف');
  if (title.length < 3) throw new ResponseError(422, 'عنوان الوثيقة يجب أن يكون بين 3 و220 حرفًا.');

  const candidate = form.get('file');
  if (!(candidate instanceof File) || candidate.size <= 0) throw new ResponseError(422, 'اختر ملفًا صالحًا للوثيقة.');
  if (candidate.size > MAX_BYTES) throw new ResponseError(413, 'الحد الأقصى للملف 25 MB.');

  const originalName = safeName(candidate.name || 'file');
  const extension = extensionOf(originalName);
  const mimeType = EXTENSION_MIME[extension];
  if (!mimeType) throw new ResponseError(415, 'نوع الوثيقة غير مسموح به.');

  const supabase = adminClient();
  const membership = await supabase
    .from('school_memberships')
    .select('role, status')
    .eq('school_id', schoolId)
    .eq('user_id', userId)
    .eq('status', 'active')
    .in('role', ['owner', 'admin'])
    .maybeSingle();
  if (membership.error || !membership.data) {
    throw new ResponseError(403, 'رفع الوثائق المباشر متاح لمالك النظام أو الإدارة فقط.');
  }

  const year = await supabase
    .from('academic_years')
    .select('id, is_current')
    .eq('school_id', schoolId)
    .eq('id', academicYearId)
    .eq('is_current', true)
    .maybeSingle();
  if (year.error || !year.data) throw new ResponseError(422, 'الرفع المباشر متاح للعام الدراسي الحالي فقط.');

  if (teacherId !== null) {
    const [teacher, teacherYear] = await Promise.all([
      supabase.from('teachers').select('id').eq('school_id', schoolId).eq('id', teacherId).eq('is_active', true).maybeSingle(),
      supabase.from('teacher_years').select('teacher_id').eq('school_id', schoolId).eq('academic_year_id', academicYearId).eq('teacher_id', teacherId).eq('is_active', true).maybeSingle(),
    ]);
    if (teacher.error || teacherYear.error || !teacher.data || !teacherYear.data) {
      throw new ResponseError(422, 'المعلم المرتبط بالوثيقة غير موجود في عام العمل الحالي.');
    }
  }

  const objectName = `${crypto.randomUUID()}-${originalName}`;
  const storagePath = `${schoolId}/${academicYearId}/direct/${objectName}`;
  const storageUpload = await supabase.storage.from(BUCKET).upload(storagePath, candidate, {
    contentType: mimeType,
    upsert: false,
  });
  if (storageUpload.error) throw new ResponseError(502, 'تعذر حفظ الوثيقة في التخزين الآمن.');

  let documentId: number | null = null;
  try {
    const now = new Date().toISOString();
    const documentInsert = await supabase
      .from('documents')
      .insert({
        school_id: schoolId,
        academic_year_id: academicYearId,
        request_id: null,
        teacher_id: teacherId,
        title,
        category,
        subject: subject || null,
        grade: grade || null,
        original_name: originalName,
        mime_type: mimeType,
        size_bytes: candidate.size,
        storage_provider: 'supabase',
        storage_bucket: BUCKET,
        storage_path: storagePath,
        external_url: null,
        status: 'approved',
        approved_at: now,
      })
      .select('id')
      .single();
    if (documentInsert.error || !documentInsert.data) {
      await rollbackCreatedDocument(supabase, null, storagePath);
      throw new ResponseError(502, 'تم إلغاء الرفع لأن تسجيل الوثيقة لم يكتمل.');
    }

    documentId = Number(documentInsert.data.id);
    if (!Number.isSafeInteger(documentId) || documentId <= 0) {
      await rollbackCreatedDocument(supabase, null, storagePath);
      throw new ResponseError(502, 'تعذر تثبيت معرف الوثيقة الجديدة.');
    }

    const activity = await supabase.from('activities').insert({
      school_id: schoolId,
      academic_year_id: academicYearId,
      actor_user_id: userId,
      activity_type: 'document',
      title: `إضافة وثيقة: ${title}`,
      detail: category,
      entity_type: 'document',
      entity_id: documentId,
    });
    if (activity.error) {
      await rollbackCreatedDocument(supabase, documentId, storagePath);
      throw new ResponseError(502, 'تم إلغاء الرفع لأن تسجيل نشاط الوثيقة لم يكتمل.');
    }
  } catch (error) {
    if (error instanceof ResponseError) throw error;
    await rollbackCreatedDocument(supabase, documentId, storagePath);
    throw error;
  }

  return json({ ok: true, documentId, storageProvider: 'supabase' }, 201);
}

Deno.serve(async (request) => {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders });
  if (request.method !== 'POST') return json({ message: 'الطريقة غير مسموح بها.' }, 405);
  try {
    return await upload(request);
  } catch (error) {
    if (error instanceof ResponseError) return json({ message: error.message }, error.status);
    console.error('marsad-direct-document-upload failed', error);
    return json({ message: 'تعذر تنفيذ رفع الوثيقة المباشر.' }, 500);
  }
});
