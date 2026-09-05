import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';
import type { DirectDocumentInput } from '../types';

async function functionErrorMessage(error: unknown, fallback: string): Promise<string> {
  if (error && typeof error === 'object' && 'context' in error) {
    const context = (error as { context?: unknown }).context;
    if (context instanceof Response) {
      try {
        const body = await context.clone().json() as { message?: unknown };
        const message = String(body.message || '').trim();
        if (message) return message;
      } catch { /* keep Arabic fallback */ }
    }
  }
  return fallback;
}

export async function uploadSupabaseDirectDocument(
  context: TenantSessionContext,
  input: DirectDocumentInput,
  file: File,
): Promise<{ ok: boolean; documentId: number; storageProvider: string }> {
  if (context.role !== 'owner' && context.role !== 'admin') {
    throw new Error('رفع الوثائق المباشر متاح لمالك النظام أو الإدارة فقط.');
  }
  if (input.academicYear !== context.academicYear) {
    throw new Error('الرفع المباشر عبر Supabase متاح للعام الدراسي الحالي فقط.');
  }
  if (!(file instanceof File) || file.size <= 0) throw new Error('اختر ملفًا صالحًا للوثيقة.');

  const form = new FormData();
  form.append('schoolId', context.schoolId);
  form.append('academicYearId', String(context.academicYearId));
  form.append('title', input.title);
  form.append('category', input.category);
  if (input.teacherId) form.append('teacherId', String(input.teacherId));
  form.append('subject', input.subject);
  form.append('grade', input.grade);
  form.append('file', file);

  const { data, error } = await getSupabaseClient().functions.invoke('marsad-direct-document-upload', { body: form });
  if (error) throw new Error(await functionErrorMessage(error, 'تعذر رفع الوثيقة إلى التخزين الآمن.'));
  if (!data || typeof data !== 'object') throw new Error('لم تُرجع خدمة رفع الوثائق نتيجة صالحة.');

  const result = data as { ok?: unknown; documentId?: unknown; storageProvider?: unknown };
  const documentId = Number(result.documentId);
  if (result.ok !== true || !Number.isSafeInteger(documentId) || documentId <= 0 || result.storageProvider !== 'supabase') {
    throw new Error('لم تُرجع خدمة رفع الوثائق بيانات اكتمال صالحة.');
  }
  return { ok: true, documentId, storageProvider: 'supabase' };
}
