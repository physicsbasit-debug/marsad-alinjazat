import type {
  BootstrapData,
  CreateEventInput,
  CreateRequestInput,
  CreateTeacherInput,
  PublicUploadInfo,
  RequestStatus,
  CreateTeacherCvItemInput,
  EventDetails,
  EventMediaMetaInput,
  EventMediaRecord,
  UpdateEventInput,
  TeacherProfileDetails,
  UpdateTeacherProfileInput,
  CreateMeetingInput,
  MeetingDecisionInput,
  MeetingDecision,
  MeetingDetails,
  CurriculumPlanInput,
  CurriculumPlanDetails,
  CurriculumUnitInput,
  CurriculumUnit,
} from '../types';
import { getPreviewEventDetails, getPreviewMeetingDetails, getPreviewPlanDetails, getPreviewTeacherProfile, previewBootstrap } from './preview';

const PREVIEW_MODE = import.meta.env.VITE_PREVIEW_MODE === 'true';
const PREVIEW_MESSAGE = 'هذه معاينة GitHub Pages فقط. الحفظ والرفع الفعليان يعملان عند تشغيل خادم مرصد الإنجازات.';

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

function requireBackend(): void {
  if (PREVIEW_MODE) throw new Error(PREVIEW_MESSAGE);
}

export async function getBootstrap(): Promise<BootstrapData> {
  if (PREVIEW_MODE) return previewBootstrap;
  return parseResponse(await fetch('/api/bootstrap'));
}

export async function createUploadRequest(input: CreateRequestInput): Promise<{ id: number; uploadUrl: string; expiresAt: string }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateRequestStatus(id: number, status: RequestStatus): Promise<void> {
  requireBackend();
  await parseResponse(
    await fetch(`/api/requests/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }),
  );
}

export async function getPublicUploadInfo(token: string): Promise<PublicUploadInfo> {
  requireBackend();
  return parseResponse(await fetch(`/api/public/upload/${encodeURIComponent(token)}`));
}

export async function uploadPublicFile(token: string, file: File): Promise<{ ok: boolean; storageProvider: string }> {
  requireBackend();
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
  requireBackend();
  const data = await parseResponse<{ url: string }>(await fetch('/api/integrations/google-drive/auth-url'));
  return data.url;
}

export async function createTeacher(input: CreateTeacherInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/teachers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createEvent(input: CreateEventInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}


export async function getEventDetails(id: number): Promise<EventDetails> {
  if (PREVIEW_MODE) return getPreviewEventDetails(id);
  return parseResponse(await fetch(`/api/events/${id}`));
}

export async function updateEvent(id: number, input: UpdateEventInput): Promise<EventDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/events/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function uploadEventMedia(id: number, files: File[]): Promise<EventMediaRecord[]> {
  requireBackend();
  const uploaded: EventMediaRecord[] = [];
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    uploaded.push(await parseResponse<EventMediaRecord>(await fetch(`/api/events/${id}/media`, { method: 'POST', body: form })));
  }
  return uploaded;
}

export async function updateEventMedia(eventId: number, mediaId: number, input: EventMediaMetaInput): Promise<EventDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/events/${eventId}/media/${mediaId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function reorderEventMedia(eventId: number, mediaIds: number[]): Promise<EventDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/events/${eventId}/media-order`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mediaIds }),
    }),
  );
}

export async function deleteEventMedia(eventId: number, mediaId: number): Promise<void> {
  requireBackend();
  await parseResponse(await fetch(`/api/events/${eventId}/media/${mediaId}`, { method: 'DELETE' }));
}


export async function getTeacherProfile(id: number): Promise<TeacherProfileDetails> {
  if (PREVIEW_MODE) return getPreviewTeacherProfile(id);
  return parseResponse(await fetch(`/api/teachers/${id}/profile`));
}

export async function updateTeacherProfile(id: number, input: UpdateTeacherProfileInput): Promise<void> {
  requireBackend();
  await parseResponse(
    await fetch(`/api/teachers/${id}/profile`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createTeacherCvItem(id: number, input: CreateTeacherCvItemInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/teachers/${id}/cv-items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteTeacherCvItem(teacherId: number, itemId: number): Promise<void> {
  requireBackend();
  await parseResponse(
    await fetch(`/api/teachers/${teacherId}/cv-items/${itemId}`, { method: 'DELETE' }),
  );
}

export async function createMeeting(input: CreateMeetingInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/meetings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function getMeetingDetails(id: number): Promise<MeetingDetails> {
  if (PREVIEW_MODE) return getPreviewMeetingDetails(id);
  return parseResponse(await fetch(`/api/meetings/${id}`));
}

export async function updateMeeting(id: number, input: CreateMeetingInput): Promise<MeetingDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/meetings/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createMeetingDecision(meetingId: number, input: MeetingDecisionInput): Promise<MeetingDecision> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/meetings/${meetingId}/decisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateMeetingDecision(meetingId: number, decisionId: number, input: MeetingDecisionInput): Promise<MeetingDecision> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/meetings/${meetingId}/decisions/${decisionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteMeetingDecision(meetingId: number, decisionId: number): Promise<void> {
  requireBackend();
  await parseResponse(await fetch(`/api/meetings/${meetingId}/decisions/${decisionId}`, { method: 'DELETE' }));
}

export async function createCurriculumPlan(input: CurriculumPlanInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function getCurriculumPlan(id: number): Promise<CurriculumPlanDetails> {
  if (PREVIEW_MODE) return getPreviewPlanDetails(id);
  return parseResponse(await fetch(`/api/plans/${id}`));
}

export async function updateCurriculumPlan(id: number, input: CurriculumPlanInput): Promise<CurriculumPlanDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/plans/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createCurriculumUnit(planId: number, input: CurriculumUnitInput): Promise<CurriculumUnit> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/plans/${planId}/units`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateCurriculumUnit(planId: number, unitId: number, input: CurriculumUnitInput): Promise<CurriculumUnit> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/plans/${planId}/units/${unitId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteCurriculumUnit(planId: number, unitId: number): Promise<void> {
  requireBackend();
  await parseResponse(await fetch(`/api/plans/${planId}/units/${unitId}`, { method: 'DELETE' }));
}
