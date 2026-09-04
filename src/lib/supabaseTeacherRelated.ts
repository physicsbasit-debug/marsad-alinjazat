import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';
import type {
  DocumentRecord,
  RequestStatus,
  SupervisionVisitEffectiveStatus,
  SupervisionVisitRecord,
  SupervisionVisitStatus,
  UploadRequest,
} from '../types';
import type { SupabaseTeachersReadSnapshot } from './supabaseTeachers';

export type SupabaseTeacherRelatedSnapshot = {
  schoolId: string;
  academicYearId: number;
  academicYear: string;
  requests: UploadRequest[];
  documents: DocumentRecord[];
  visits: SupervisionVisitRecord[];
  requestRowsInScope: number;
  documentRowsInScope: number;
  visitRowsInScope: number;
  actionRowsInScope: number;
};

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
  status: RequestStatus;
  expires_at: string;
  created_at: string;
  updated_at: string;
};

type DocumentRow = {
  id: number;
  school_id: string;
  academic_year_id: number;
  request_id: number | null;
  teacher_id: number | null;
  title: string;
  category: string;
  subject: string | null;
  grade: string | null;
  original_name: string;
  mime_type: string | null;
  size_bytes: number;
  storage_provider: string;
  storage_path: string | null;
  external_url: string | null;
  status: string;
  uploaded_at: string;
  approved_at: string | null;
};

type VisitRow = {
  id: number;
  school_id: string;
  academic_year_id: number;
  teacher_id: number;
  visit_type: string;
  visit_date: string;
  period_label: string | null;
  grade: string | null;
  lesson_title: string | null;
  objectives: string | null;
  strengths: string | null;
  development_areas: string | null;
  recommendations: string | null;
  followup_date: string | null;
  followup_notes: string | null;
  status: SupervisionVisitStatus;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
};

type ActionRow = {
  id: number;
  school_id: string;
  visit_id: number;
  due_date: string | null;
  status: 'new' | 'in_progress' | 'completed' | 'cancelled';
};

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

function ensureSafeNumericId(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} خارج النطاق الرقمي الآمن للواجهة.`);
  }
  return parsed;
}

function ensureScope(rowSchoolId: string, rowAcademicYearId: unknown, context: TenantSessionContext, label: string): void {
  if (rowSchoolId !== context.schoolId) throw new Error(`أعاد RLS ${label} من مدرسة أخرى.`);
  if (ensureSafeNumericId(rowAcademicYearId, `معرف عام ${label}`) !== context.academicYearId) {
    throw new Error(`خرجت قراءة ${label} عن العام الدراسي الحالي.`);
  }
}

function omanTodayIso(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Muscat',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const get = (type: 'year' | 'month' | 'day') => parts.find((part) => part.type === type)?.value || '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

function effectiveVisitStatus(
  visit: VisitRow,
  overdueActionCount: number,
  today: string,
): SupervisionVisitEffectiveStatus {
  if (visit.status !== 'closed' && overdueActionCount > 0) return 'overdue';
  if (visit.status === 'planned' && visit.visit_date && visit.visit_date < today) return 'overdue';
  if (visit.status === 'needs_followup' && visit.followup_date && visit.followup_date < today) return 'overdue';
  return visit.status;
}

export async function loadSupabaseTeacherRelatedSnapshot(
  context: TenantSessionContext,
  teachersSnapshot: SupabaseTeachersReadSnapshot,
): Promise<SupabaseTeacherRelatedSnapshot> {
  if (teachersSnapshot.schoolId !== context.schoolId || teachersSnapshot.academicYearId !== context.academicYearId) {
    throw new Error('نطاق المعلمين لا يطابق نطاق البيانات المرتبطة.');
  }

  const client = getSupabaseClient();
  const [requestsResult, documentsResult, visitsResult] = await Promise.all([
    client
      .from('upload_requests')
      .select('id, school_id, academic_year_id, teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, status, expires_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .order('id', { ascending: false }),
    client
      .from('documents')
      .select('id, school_id, academic_year_id, request_id, teacher_id, title, category, subject, grade, original_name, mime_type, size_bytes, storage_provider, storage_path, external_url, status, uploaded_at, approved_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .order('uploaded_at', { ascending: false }),
    client
      .from('supervision_visits')
      .select('id, school_id, academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .order('visit_date', { ascending: false }),
  ]);

  if (requestsResult.error) throw new Error('تعذر قراءة طلبات الملفات المرتبطة بالمعلمين عبر RLS.');
  if (documentsResult.error) throw new Error('تعذر قراءة الوثائق المرتبطة بالمعلمين عبر RLS.');
  if (visitsResult.error) throw new Error('تعذر قراءة الزيارات الإشرافية المرتبطة بالمعلمين عبر RLS.');

  const teacherById = new Map(teachersSnapshot.teachers.map((teacher) => [teacher.id, teacher]));
  const requestRows = (requestsResult.data || []) as RequestRow[];
  const documentRows = (documentsResult.data || []) as DocumentRow[];
  const visitRows = (visitsResult.data || []) as VisitRow[];

  const visibleVisitIds = new Set<number>();
  for (const visit of visitRows) {
    ensureScope(visit.school_id, visit.academic_year_id, context, 'زيارة إشرافية');
    const visitId = ensureSafeNumericId(visit.id, 'معرف الزيارة');
    const teacherId = ensureSafeNumericId(visit.teacher_id, 'معرف معلم الزيارة');
    if (!teacherById.has(teacherId)) throw new Error('أعادت القراءة زيارة لمعلم خارج عام العمل الحالي.');
    visibleVisitIds.add(visitId);
  }

  let actionRows: ActionRow[] = [];
  if (visibleVisitIds.size > 0) {
    const actionsResult = await client
      .from('supervision_actions')
      .select('id, school_id, visit_id, due_date, status')
      .eq('school_id', context.schoolId)
      .in('visit_id', [...visibleVisitIds]);
    if (actionsResult.error) throw new Error('تعذر قراءة إجراءات المتابعة الإشرافية عبر RLS.');
    actionRows = (actionsResult.data || []) as ActionRow[];
  }

  const actionsByVisit = new Map<number, ActionRow[]>();
  for (const action of actionRows) {
    if (action.school_id !== context.schoolId) throw new Error('أعاد RLS إجراء متابعة من مدرسة أخرى.');
    const visitId = ensureSafeNumericId(action.visit_id, 'معرف زيارة إجراء المتابعة');
    if (!visibleVisitIds.has(visitId)) continue;
    const list = actionsByVisit.get(visitId) || [];
    list.push(action);
    actionsByVisit.set(visitId, list);
  }

  const requests: UploadRequest[] = requestRows.map((row) => {
    ensureScope(row.school_id, row.academic_year_id, context, 'طلب ملف');
    const teacherId = ensureSafeNumericId(row.teacher_id, 'معرف معلم الطلب');
    const teacher = teacherById.get(teacherId);
    if (!teacher) throw new Error('أعادت القراءة طلبًا لمعلم خارج عام العمل الحالي.');
    return {
      id: ensureSafeNumericId(row.id, 'معرف الطلب'),
      teacherId,
      teacherName: teacher.name,
      requestType: clean(row.request_type),
      subject: clean(row.subject),
      grade: clean(row.grade),
      title: clean(row.title),
      deadline: row.deadline,
      notes: clean(row.notes) || null,
      allowedFiles: clean(row.allowed_files),
      status: row.status,
      academicYear: context.academicYear,
      expiresAt: row.expires_at,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  });

  const documents: DocumentRecord[] = documentRows.map((row) => {
    ensureScope(row.school_id, row.academic_year_id, context, 'وثيقة');
    const teacherId = row.teacher_id == null ? null : ensureSafeNumericId(row.teacher_id, 'معرف معلم الوثيقة');
    if (teacherId !== null && !teacherById.has(teacherId)) throw new Error('أعادت القراءة وثيقة لمعلم خارج عام العمل الحالي.');
    return {
      id: ensureSafeNumericId(row.id, 'معرف الوثيقة'),
      requestId: row.request_id == null ? null : ensureSafeNumericId(row.request_id, 'معرف طلب الوثيقة'),
      teacherId,
      title: clean(row.title),
      category: clean(row.category),
      subject: clean(row.subject) || null,
      grade: clean(row.grade) || null,
      academicYear: context.academicYear,
      originalName: clean(row.original_name),
      mimeType: clean(row.mime_type) || null,
      sizeBytes: Number(row.size_bytes || 0),
      storageProvider: clean(row.storage_provider),
      storageFileId: null,
      storagePath: clean(row.storage_path) || null,
      webViewLink: clean(row.external_url) || null,
      status: clean(row.status),
      uploadedAt: row.uploaded_at,
      approvedAt: row.approved_at,
    };
  });

  const today = omanTodayIso();
  const visits: SupervisionVisitRecord[] = visitRows.map((row) => {
    const visitId = ensureSafeNumericId(row.id, 'معرف الزيارة');
    const teacherId = ensureSafeNumericId(row.teacher_id, 'معرف معلم الزيارة');
    const teacher = teacherById.get(teacherId);
    if (!teacher) throw new Error('تعذر ربط الزيارة بمعلم عام العمل الحالي.');
    const actions = actionsByVisit.get(visitId) || [];
    const openActions = actions.filter((action) => action.status !== 'completed' && action.status !== 'cancelled');
    const completedActions = actions.filter((action) => action.status === 'completed');
    const overdueActions = openActions.filter((action) => action.due_date && action.due_date < today);
    return {
      id: visitId,
      teacherId,
      teacherName: teacher.name,
      teacherSubject: teacher.subject,
      visitType: clean(row.visit_type),
      visitDate: row.visit_date,
      periodLabel: clean(row.period_label) || null,
      grade: clean(row.grade) || null,
      lessonTitle: clean(row.lesson_title) || null,
      objectives: clean(row.objectives) || null,
      strengths: clean(row.strengths) || null,
      developmentAreas: clean(row.development_areas) || null,
      recommendations: clean(row.recommendations) || null,
      followupDate: row.followup_date,
      followupNotes: clean(row.followup_notes) || null,
      academicYear: context.academicYear,
      status: row.status,
      effectiveStatus: effectiveVisitStatus(row, overdueActions.length, today),
      actionCount: actions.length,
      openActionCount: openActions.length,
      completedActionCount: completedActions.length,
      overdueActionCount: overdueActions.length,
      closedAt: row.closed_at,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  });

  return {
    schoolId: context.schoolId,
    academicYearId: context.academicYearId,
    academicYear: context.academicYear,
    requests,
    documents,
    visits,
    requestRowsInScope: requests.length,
    documentRowsInScope: documents.length,
    visitRowsInScope: visits.length,
    actionRowsInScope: [...actionsByVisit.values()].reduce((sum, rows) => sum + rows.length, 0),
  };
}

export function teacherRelatedStats(
  snapshot: SupabaseTeacherRelatedSnapshot,
  teacherId: number,
): {
  requestCount: number;
  documentCount: number;
  approvedDocumentCount: number;
  visitCount: number;
  openFollowupCount: number;
} {
  const requests = snapshot.requests.filter((item) => item.teacherId === teacherId);
  const documents = snapshot.documents.filter((item) => item.teacherId === teacherId);
  const visits = snapshot.visits.filter((item) => item.teacherId === teacherId);
  return {
    requestCount: requests.length,
    documentCount: documents.length,
    approvedDocumentCount: documents.filter((item) => item.status === 'approved').length,
    visitCount: visits.length,
    openFollowupCount: visits.filter((visit) => visit.status !== 'closed' && (visit.status === 'needs_followup' || visit.openActionCount > 0)).length,
  };
}
