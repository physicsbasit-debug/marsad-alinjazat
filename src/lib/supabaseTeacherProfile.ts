import type {
  CreateTeacherCvItemInput,
  Teacher,
  TeacherCvItem,
  TeacherProfileDetails,
  UpdateTeacherProfileInput,
} from '../types';
import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';
import { loadSupabaseTeachersReadSnapshot } from './supabaseTeachers';
import { updateSupabaseTeacher } from './supabaseTeachersWrite';

function ensureManager(context: TenantSessionContext): void {
  if (context.role !== 'owner' && context.role !== 'admin') {
    throw new Error('هذه العملية متاحة لمالك النظام أو المدير فقط.');
  }
}

function ensureSafeNumericId(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} خارج النطاق الرقمي الآمن للواجهة.`);
  }
  return parsed;
}

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

function nullable(value: string): string | null {
  const normalized = clean(value);
  return normalized || null;
}

function toTeacher(record: Awaited<ReturnType<typeof loadSupabaseTeachersReadSnapshot>>['teachers'][number]): Teacher {
  return {
    id: record.id,
    name: record.name,
    subject: record.subject,
    specialization: record.specialization,
    qualification: record.qualification,
    experienceYears: record.experienceYears,
    workload: record.workload,
    cvCompletion: record.readCompleteness,
    email: record.email,
    phone: record.phone,
  };
}

type CvRow = {
  id: number;
  teacher_id: number;
  item_type: TeacherCvItem['itemType'];
  title: string;
  organization: string | null;
  start_year: number | null;
  end_year: number | null;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export async function getSupabaseTeacherProfile(
  context: TenantSessionContext,
  teacherId: number,
): Promise<TeacherProfileDetails> {
  const safeTeacherId = ensureSafeNumericId(teacherId, 'معرف المعلم');
  const snapshot = await loadSupabaseTeachersReadSnapshot(context);
  const record = snapshot.teachers.find((item) => item.id === safeTeacherId);
  if (!record) throw new Error('المعلم غير موجود ضمن المدرسة والعام الدراسي الحاليين.');

  const { data: cvRows, error } = await getSupabaseClient()
    .from('teacher_cv_items')
    .select('id, teacher_id, item_type, title, organization, start_year, end_year, description, created_at, updated_at')
    .eq('school_id', context.schoolId)
    .eq('teacher_id', safeTeacherId)
    .order('start_year', { ascending: false, nullsFirst: false })
    .order('id', { ascending: false });

  if (error) throw new Error('تعذر قراءة بنود السيرة المهنية عبر RLS.');

  const cvItems: TeacherCvItem[] = ((cvRows || []) as CvRow[]).map((row) => ({
    id: ensureSafeNumericId(row.id, 'معرف بند السيرة'),
    teacherId: ensureSafeNumericId(row.teacher_id, 'معرف معلم بند السيرة'),
    itemType: row.item_type,
    title: clean(row.title),
    organization: clean(row.organization) || null,
    startYear: row.start_year,
    endYear: row.end_year,
    description: clean(row.description) || null,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }));

  return {
    teacher: toTeacher(record),
    profile: {
      employeeNumber: record.employeeNumber,
      schoolJoinYear: record.schoolJoinYear,
      grades: record.grades,
      responsibilities: record.responsibilities,
      professionalSummary: record.professionalSummary,
    },
    cvItems,
    stats: {
      requestCount: 0,
      documentCount: 0,
      approvedDocumentCount: 0,
      visitCount: 0,
      openFollowupCount: 0,
    },
  };
}

export async function updateSupabaseTeacherProfile(
  context: TenantSessionContext,
  teacherId: number,
  input: UpdateTeacherProfileInput,
): Promise<void> {
  await updateSupabaseTeacher(context, teacherId, input);
}

export async function createSupabaseTeacherCvItem(
  context: TenantSessionContext,
  teacherId: number,
  input: CreateTeacherCvItemInput,
): Promise<{ id: number }> {
  ensureManager(context);
  const safeTeacherId = ensureSafeNumericId(teacherId, 'معرف المعلم');
  const title = clean(input.title);
  if (!title || title.length > 240) throw new Error('عنوان بند السيرة مطلوب ويجب ألا يتجاوز 240 حرفًا.');
  if (clean(input.organization).length > 200) throw new Error('اسم الجهة أطول من الحد المسموح.');
  if (clean(input.description).length > 3000) throw new Error('وصف بند السيرة أطول من الحد المسموح.');
  for (const [value, label] of [[input.startYear, 'سنة البداية'], [input.endYear, 'سنة النهاية']] as const) {
    if (value !== null && value !== undefined && (!Number.isInteger(value) || value < 1950 || value > 2100)) {
      throw new Error(`${label} خارج النطاق المسموح.`);
    }
  }
  if (input.startYear && input.endYear && input.endYear < input.startYear) {
    throw new Error('سنة النهاية لا يمكن أن تسبق سنة البداية.');
  }

  const { data, error } = await getSupabaseClient()
    .from('teacher_cv_items')
    .insert({
      school_id: context.schoolId,
      teacher_id: safeTeacherId,
      item_type: input.itemType,
      title,
      organization: nullable(input.organization),
      start_year: input.startYear ?? null,
      end_year: input.endYear ?? null,
      description: nullable(input.description),
    })
    .select('id')
    .single();
  if (error) throw new Error('تعذر إضافة بند السيرة المهنية في Supabase.');
  return { id: ensureSafeNumericId((data as { id?: unknown } | null)?.id, 'معرف بند السيرة') };
}

export async function deleteSupabaseTeacherCvItem(
  context: TenantSessionContext,
  teacherId: number,
  itemId: number,
): Promise<void> {
  ensureManager(context);
  const safeTeacherId = ensureSafeNumericId(teacherId, 'معرف المعلم');
  const safeItemId = ensureSafeNumericId(itemId, 'معرف بند السيرة');
  const { data, error } = await getSupabaseClient()
    .from('teacher_cv_items')
    .delete()
    .eq('school_id', context.schoolId)
    .eq('teacher_id', safeTeacherId)
    .eq('id', safeItemId)
    .select('id');
  if (error) throw new Error('تعذر حذف بند السيرة المهنية من Supabase.');
  if (!data || data.length !== 1) throw new Error('لم يُحذف بند السيرة لأن السجل غير موجود ضمن نطاق المدرسة.');
}
