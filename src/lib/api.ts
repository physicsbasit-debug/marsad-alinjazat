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
  SupervisionVisitInput,
  SupervisionVisitDetails,
  SupervisionActionInput,
  SupervisionAction,
  AchievementAssessmentInput,
  AchievementAssessmentDetails,
  AchievementActionInput,
  AchievementAction,
  OfficialReport,
  OfficialReportQuery,
  ArchiveYearsIndex,
  ArchiveYearDetail,
} from '../types';
import { getPreviewArchiveYear, getPreviewArchiveYears, getPreviewAssessmentDetails, getPreviewEventDetails, getPreviewMeetingDetails, getPreviewOfficialReport, getPreviewPlanDetails, getPreviewSupervisionVisit, getPreviewTeacherProfile, previewBootstrap } from './preview';

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


export async function getOfficialReport(input: OfficialReportQuery): Promise<OfficialReport> {
  if (PREVIEW_MODE) return getPreviewOfficialReport(input);
  const params = new URLSearchParams({ reportType: input.reportType, academicYear: input.academicYear, term: input.term });
  if (input.teacherId) params.set('teacherId', String(input.teacherId));
  return parseResponse(await fetch(`/api/reports/official?${params.toString()}`));
}


export async function getArchiveYears(): Promise<ArchiveYearsIndex> {
  if (PREVIEW_MODE) return getPreviewArchiveYears();
  return parseResponse(await fetch('/api/archive/years'));
}

export async function getArchiveYear(academicYear: string): Promise<ArchiveYearDetail> {
  if (PREVIEW_MODE) return getPreviewArchiveYear(academicYear);
  const params = new URLSearchParams({ academicYear });
  return parseResponse(await fetch(`/api/archive/year?${params.toString()}`));
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

export async function createSupervisionVisit(input: SupervisionVisitInput): Promise<{ id: number }> {
  requireBackend();
  return parseResponse(
    await fetch('/api/supervision/visits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function getSupervisionVisit(id: number): Promise<SupervisionVisitDetails> {
  if (PREVIEW_MODE) return getPreviewSupervisionVisit(id);
  return parseResponse(await fetch(`/api/supervision/visits/${id}`));
}

export async function updateSupervisionVisit(id: number, input: SupervisionVisitInput): Promise<SupervisionVisitDetails> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/supervision/visits/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function createSupervisionAction(visitId: number, input: SupervisionActionInput): Promise<SupervisionAction> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/supervision/visits/${visitId}/actions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateSupervisionAction(visitId: number, actionId: number, input: SupervisionActionInput): Promise<SupervisionAction> {
  requireBackend();
  return parseResponse(
    await fetch(`/api/supervision/visits/${visitId}/actions/${actionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteSupervisionAction(visitId: number, actionId: number): Promise<void> {
  requireBackend();
  await parseResponse(await fetch(`/api/supervision/visits/${visitId}/actions/${actionId}`, { method: 'DELETE' }));
}

export async function createAchievementAssessment(input: AchievementAssessmentInput): Promise<AchievementAssessmentDetails> {
  requireBackend();
  return parseResponse(await fetch('/api/achievement/assessments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }));
}

export async function getAchievementAssessment(id: number): Promise<AchievementAssessmentDetails> {
  if (PREVIEW_MODE) return getPreviewAssessmentDetails(id);
  return parseResponse(await fetch(`/api/achievement/assessments/${id}`));
}

export async function updateAchievementAssessment(id: number, input: AchievementAssessmentInput): Promise<AchievementAssessmentDetails> {
  requireBackend();
  return parseResponse(await fetch(`/api/achievement/assessments/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }));
}

export async function createAchievementAction(assessmentId: number, input: AchievementActionInput): Promise<AchievementAction> {
  requireBackend();
  return parseResponse(await fetch(`/api/achievement/assessments/${assessmentId}/actions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }));
}

export async function updateAchievementAction(assessmentId: number, actionId: number, input: AchievementActionInput): Promise<AchievementAction> {
  requireBackend();
  return parseResponse(await fetch(`/api/achievement/assessments/${assessmentId}/actions/${actionId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }));
}

export async function deleteAchievementAction(assessmentId: number, actionId: number): Promise<void> {
  requireBackend();
  await parseResponse(await fetch(`/api/achievement/assessments/${assessmentId}/actions/${actionId}`, { method: 'DELETE' }));
}

