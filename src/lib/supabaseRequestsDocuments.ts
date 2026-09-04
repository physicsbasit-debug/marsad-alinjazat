import { getSupabaseClient } from './supabase';
import { loadSupabaseTeachersReadSnapshot } from './supabaseTeachers';
import type { SupabaseTeacherReadRecord } from './supabaseTeachers';
import type { TenantSessionContext } from './supabaseSession';
import type { DocumentRecord, RequestStatus, Teacher, UploadRequest } from '../types';

export type SupabaseRequestsDocumentsSnapshot = {
  schoolId: string;
  academicYearId: number;
  academicYear: string;
  teachers: Teacher[];
  requests: UploadRequest[];
  documents: DocumentRecord[];
  openRequestCount: number;
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

const OPEN_REQUEST_STATUSES = new Set<RequestStatus>([
  'waiting_upload', 'received', 'review', 'needs_revision', 'late',
]);

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

function safeId(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} خارج النطاق الرقمي الآمن للواجهة.`);
  }
  return parsed;
}

function assertScope(rowSchoolId: string, rowAcademicYearId: unknown, context: TenantSessionContext, label: string): void {
  if (rowSchoolId !== context.schoolId) throw new Error(`أعاد RLS ${label} من مدرسة أخرى.`);
  if (safeId(rowAcademicYearId, `معرف عام ${label}`) !== context.academicYearId) {
    throw new Error(`خرجت قراءة ${label} عن العام الدراسي الحالي.`);
  }
}

export async function loadSupabaseRequestsDocumentsSnapshot(
  context: TenantSessionContext,
): Promise<SupabaseRequestsDocumentsSnapshot> {
  if (context.role !== 'owner' && context.role !== 'admin') {
    throw new Error('إدارة طلبات الملفات متاحة لمالك النظام أو الإدارة فقط في هذه المرحلة.');
  }

  const [teachersSnapshot, requestResult, documentResult] = await Promise.all([
    loadSupabaseTeachersReadSnapshot(context),
    getSupabaseClient()
      .from('upload_requests')
      .select('id, school_id, academic_year_id, teacher_id, request_type, subject, grade, title, deadline, notes, allowed_files, status, expires_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .order('id', { ascending: false }),
    getSupabaseClient()
      .from('documents')
      .select('id, school_id, academic_year_id, request_id, teacher_id, title, category, subject, grade, original_name, mime_type, size_bytes, storage_provider, storage_path, external_url, status, uploaded_at, approved_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .order('uploaded_at', { ascending: false }),
  ]);

  if (requestResult.error) throw new Error('تعذر قراءة طلبات الملفات عبر RLS.');
  if (documentResult.error) throw new Error('تعذر قراءة سجل الوثائق عبر RLS.');

  const teacherById = new Map<number, SupabaseTeacherReadRecord>(teachersSnapshot.teachers.map((teacher) => [teacher.id, teacher]));
  const teachers: Teacher[] = teachersSnapshot.teachers.map((teacher) => ({
    id: teacher.id,
    name: teacher.name,
    subject: teacher.subject,
    specialization: teacher.specialization,
    qualification: teacher.qualification,
    experienceYears: teacher.experienceYears,
    workload: teacher.workload,
    cvCompletion: teacher.readCompleteness,
    email: teacher.email,
    phone: teacher.phone,
  }));

  const requests = ((requestResult.data || []) as RequestRow[]).map((row): UploadRequest => {
    assertScope(row.school_id, row.academic_year_id, context, 'طلب ملف');
    const teacherId = safeId(row.teacher_id, 'معرف معلم الطلب');
    const teacher = teacherById.get(teacherId);
    if (!teacher) throw new Error('أعاد RLS طلبًا مرتبطًا بمعلم خارج عام العمل الحالي.');
    return {
      id: safeId(row.id, 'معرف الطلب'),
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

  const documents = ((documentResult.data || []) as DocumentRow[]).map((row): DocumentRecord => {
    assertScope(row.school_id, row.academic_year_id, context, 'وثيقة');
    const teacherId = row.teacher_id == null ? null : safeId(row.teacher_id, 'معرف معلم الوثيقة');
    if (teacherId !== null && !teacherById.has(teacherId)) {
      throw new Error('أعاد RLS وثيقة مرتبطة بمعلم خارج عام العمل الحالي.');
    }
    return {
      id: safeId(row.id, 'معرف الوثيقة'),
      requestId: row.request_id == null ? null : safeId(row.request_id, 'معرف طلب الوثيقة'),
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

  return {
    schoolId: context.schoolId,
    academicYearId: context.academicYearId,
    academicYear: context.academicYear,
    teachers,
    requests,
    documents,
    openRequestCount: requests.filter((request) => OPEN_REQUEST_STATUSES.has(request.status)).length,
  };
}

export async function updateSupabaseRequestStatus(
  context: TenantSessionContext,
  requestId: number,
  status: RequestStatus,
): Promise<void> {
  if (context.role !== 'owner' && context.role !== 'admin') {
    throw new Error('تحديث حالة الطلب متاح لمالك النظام أو الإدارة فقط.');
  }
  if (!Number.isSafeInteger(requestId) || requestId <= 0) throw new Error('معرف الطلب غير صالح.');
  const { error } = await getSupabaseClient().rpc('marsad_update_upload_request_status_v1', {
    p_school_id: context.schoolId,
    p_academic_year_id: context.academicYearId,
    p_request_id: requestId,
    p_status: status,
  });
  if (error) throw new Error('تعذر تحديث حالة الطلب عبر Supabase.');
}

export async function loadSupabaseOpenRequestCount(context: TenantSessionContext): Promise<number> {
  if (context.role !== 'owner' && context.role !== 'admin') return 0;
  const { data, error } = await getSupabaseClient()
    .from('upload_requests')
    .select('id, status')
    .eq('school_id', context.schoolId)
    .eq('academic_year_id', context.academicYearId)
    .in('status', [...OPEN_REQUEST_STATUSES]);
  if (error) throw new Error('تعذر قراءة عداد طلبات الملفات عبر RLS.');
  return (data || []).length;
}
