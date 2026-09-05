import { createClient } from 'npm:@supabase/supabase-js@2.112.4';
import { corsHeaders as supabaseCorsHeaders } from 'npm:@supabase/supabase-js@2.112.4/cors';

const BUCKET = 'marsad-documents';
const MAX_BYTES = 25 * 1024 * 1024;
const CLOSED = new Set(['approved', 'cancelled']);
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

type ServerCredential = { key: string; modern: boolean };

function serverCredential(): ServerCredential {
  const modern = Deno.env.get('SUPABASE_SECRET_KEYS');
  if (modern) {
    try {
      const parsed = JSON.parse(modern) as Record<string, string>;
      if (parsed.default) return { key: parsed.default, modern: true };
    } catch { /* use legacy fallback below */ }
  }
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

  // New sb_secret_* keys are sent as apikey only. supabase-js normally also mirrors
  // its key into Authorization, so strip only that generated bearer header here.
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

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

function safeToken(value: unknown): string {
  const token = String(value || '').trim();
  if (token.length < 20 || token.length > 200 || !/^[A-Za-z0-9_-]+$/.test(token)) {
    throw new ResponseError(404, 'رابط الرفع غير صالح.');
  }
  return token;
}

function safeName(value: string): string {
  const base = value.split(/[\\/]/).pop()?.trim() || 'file';
  return base.replace(/[\u0000-\u001f<>:"|?*]+/g, '_').slice(0, 180) || 'file';
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.');
  return index >= 0 ? name.slice(index).toLowerCase() : '';
}

class ResponseError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

type RequestRow = {
  id: number;
  school_id: string;
  academic_year_id: number;
  teacher_id: number;
  request_type: string;
  subject: string;
  grade: string;
  title: string;
  deadline: string | null;
  notes: string | null;
  allowed_files: string;
  status: string;
  expires_at: string;
};

async function resolveRequest(token: string): Promise<{ row: RequestRow; tokenHash: string; teacherName: string }> {
  const tokenHash = await sha256Hex(token);
  const supabase = adminClient();
  const { data, error } = await supabase
    .from('upload_requests')
    .select('id, school_id, academic_year_id, teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, status, expires_at')
    .eq('token_hash', tokenHash)
    .maybeSingle();
  if (error || !data) throw new ResponseError(404, 'رابط الرفع غير صالح.');
  const row = data as RequestRow;
  if (new Date(row.expires_at).getTime() < Date.now()) throw new ResponseError(410, 'انتهت صلاحية رابط الرفع.');
  if (CLOSED.has(row.status)) throw new ResponseError(409, 'هذا الطلب مغلق ولا يستقبل ملفات جديدة.');
  const teacherResult = await supabase
    .from('teachers')
    .select('name')
    .eq('school_id', row.school_id)
    .eq('id', row.teacher_id)
    .maybeSingle();
  if (teacherResult.error || !teacherResult.data) throw new ResponseError(404, 'تعذر التحقق من صاحب الطلب.');
  return { row, tokenHash, teacherName: String(teacherResult.data.name || '') };
}

async function info(tokenValue: unknown): Promise<Response> {
  const token = safeToken(tokenValue);
  const { row, teacherName } = await resolveRequest(token);
  return json({
    id: row.id,
    teacherName,
    title: row.title,
    requestType: row.request_type,
    subject: row.subject,
    grade: row.grade,
    deadline: row.deadline,
    notes: row.notes,
    allowedFiles: row.allowed_files,
    maxUploadMb: 25,
  });
}

async function upload(form: FormData): Promise<Response> {
  const token = safeToken(form.get('token'));
  const candidate = form.get('file');
  if (!(candidate instanceof File) || candidate.size <= 0) throw new ResponseError(422, 'اختر ملفًا صالحًا للرفع.');
  if (candidate.size > MAX_BYTES) throw new ResponseError(413, 'الحد الأقصى للملف 25 MB.');

  const originalName = safeName(candidate.name || 'file');
  const extension = extensionOf(originalName);
  const mimeType = EXTENSION_MIME[extension];
  if (!mimeType) throw new ResponseError(415, 'نوع الملف غير مسموح به.');

  const { row, tokenHash } = await resolveRequest(token);
  const objectName = `${crypto.randomUUID()}-${originalName}`;
  const storagePath = `${row.school_id}/${row.academic_year_id}/${row.id}/${objectName}`;
  const supabase = adminClient();

  const uploadResult = await supabase.storage.from(BUCKET).upload(storagePath, candidate, {
    contentType: mimeType,
    upsert: false,
  });
  if (uploadResult.error) throw new ResponseError(502, 'تعذر حفظ الملف في التخزين الآمن.');

  const registration = await supabase.rpc('marsad_register_public_upload_v1', {
    p_request_id: row.id,
    p_token_hash: tokenHash,
    p_original_name: originalName,
    p_mime_type: mimeType,
    p_size_bytes: candidate.size,
    p_storage_bucket: BUCKET,
    p_storage_path: storagePath,
  });
  if (registration.error) {
    await supabase.storage.from(BUCKET).remove([storagePath]);
    throw new ResponseError(502, 'تم إلغاء الرفع لأن تسجيل الوثيقة لم يكتمل.');
  }

  return json({ ok: true, documentId: Number(registration.data), storageProvider: 'supabase' }, 201);
}

Deno.serve(async (request) => {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders });
  if (request.method !== 'POST') return json({ message: 'الطريقة غير مسموح بها.' }, 405);
  try {
    const contentType = request.headers.get('content-type') || '';
    if (contentType.includes('multipart/form-data')) {
      return await upload(await request.formData());
    }
    const body = await request.json() as { action?: unknown; token?: unknown };
    if (body.action !== 'info') throw new ResponseError(400, 'عملية الرفع العام غير معروفة.');
    return await info(body.token);
  } catch (error) {
    if (error instanceof ResponseError) return json({ message: error.message }, error.status);
    console.error('marsad-public-upload failed', error);
    return json({ message: 'تعذر تنفيذ عملية الرفع العام.' }, 500);
  }
});
