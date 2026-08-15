import type {
  BootstrapData,
  CreateEventInput,
  CreateRequestInput,
  CreateTeacherInput,
  PublicUploadInfo,
  RequestStatus,
} from '../types';

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;
  let message = 'تعذر تنفيذ العملية.';
  try {
    const body = (await response.json()) as { detail?: string };
    message = body.detail || message;
  } catch {
    // Keep the generic message when the server does not return JSON.
  }
  throw new Error(message);
}

export async function getBootstrap(): Promise<BootstrapData> {
  return parseResponse(await fetch('/api/bootstrap'));
}

export async function createUploadRequest(input: CreateRequestInput): Promise<{ id: number; uploadUrl: string; expiresAt: string }> {
  return parseResponse(
    await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateRequestStatus(id: number, status: RequestStatus): Promise<void> {
  await parseResponse(
    await fetch(`/api/requests/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }),
  );
}

export async function getPublicUploadInfo(token: string): Promise<PublicUploadInfo> {
  return parseResponse(await fetch(`/api/public/upload/${encodeURIComponent(token)}`));
}

export async function uploadPublicFile(token: string, file: File): Promise<{ ok: boolean; storageProvider: string }> {
  const form = new FormData();
  form.append('file', file);
  return parseResponse(
    await fetch(`/api/public/upload/${encodeURIComponent(token)}`, {
      method: 'POST',
      body: form,
    }),
  );
}

export async function getDriveAuthUrl(): Promise<string> {
  const data = await parseResponse<{ url: string }>(await fetch('/api/integrations/google-drive/auth-url'));
  return data.url;
}


export async function createTeacher(input: CreateTeacherInput): Promise<{ id: number }> {
  return parseResponse(
    await fetch('/api/teachers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createEvent(input: CreateEventInput): Promise<{ id: number }> {
  return parseResponse(
    await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}
