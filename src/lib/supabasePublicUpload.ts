import { getSupabaseClient } from './supabase';
import type { PublicUploadInfo } from '../types';

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

export async function getSupabasePublicUploadInfo(token: string): Promise<PublicUploadInfo> {
  const { data, error } = await getSupabaseClient().functions.invoke('marsad-public-upload', {
    body: { action: 'info', token },
  });
  if (error) throw new Error(await functionErrorMessage(error, 'تعذر التحقق من رابط الرفع.'));
  if (!data || typeof data !== 'object') throw new Error('لم تُرجع خدمة الرفع بيانات صالحة.');
  return data as PublicUploadInfo;
}

export async function uploadSupabasePublicFile(
  token: string,
  file: File,
): Promise<{ ok: boolean; storageProvider: string }> {
  const form = new FormData();
  form.append('action', 'upload');
  form.append('token', token);
  form.append('file', file);
  const { data, error } = await getSupabaseClient().functions.invoke('marsad-public-upload', { body: form });
  if (error) throw new Error(await functionErrorMessage(error, 'تعذر رفع الملف إلى التخزين الآمن.'));
  if (!data || typeof data !== 'object') throw new Error('لم تُرجع خدمة الرفع نتيجة صالحة.');
  return data as { ok: boolean; storageProvider: string };
}
