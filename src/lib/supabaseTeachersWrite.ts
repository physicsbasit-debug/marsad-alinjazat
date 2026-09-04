import type { CreateTeacherInput, UpdateTeacherProfileInput } from '../types';
import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';

export type SupabaseTeacherCreateResult = {
  teacherId: number;
  linkedExisting: boolean;
};

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

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

function validateCoreFields(input: {
  name: string;
  subject: string;
  specialization: string;
  qualification: string;
  experienceYears: number;
  workload: number;
  email: string;
  phone: string;
}): void {
  const name = clean(input.name);
  const subject = clean(input.subject);
  if (name.length < 3 || name.length > 120) throw new Error('اسم المعلم يجب أن يكون بين 3 و120 حرفًا.');
  if (subject.length < 2 || subject.length > 80) throw new Error('اسم المادة يجب أن يكون بين حرفين و80 حرفًا.');
  if (clean(input.specialization).length > 120) throw new Error('التخصص أطول من الحد المسموح.');
  if (clean(input.qualification).length > 160) throw new Error('المؤهل أطول من الحد المسموح.');
  if (clean(input.email).length > 160) throw new Error('البريد الإلكتروني أطول من الحد المسموح.');
  if (clean(input.phone).length > 40) throw new Error('رقم الهاتف أطول من الحد المسموح.');
  if (!Number.isInteger(input.experienceYears) || input.experienceYears < 0 || input.experienceYears > 60) {
    throw new Error('سنوات الخبرة يجب أن تكون بين 0 و60.');
  }
  if (!Number.isInteger(input.workload) || input.workload < 0 || input.workload > 40) {
    throw new Error('النصاب يجب أن يكون بين 0 و40.');
  }
}

function nullable(value: string): string | null {
  const normalized = clean(value);
  return normalized || null;
}

export async function createSupabaseTeacher(
  context: TenantSessionContext,
  input: CreateTeacherInput,
): Promise<SupabaseTeacherCreateResult> {
  ensureManager(context);
  validateCoreFields(input);
  if (input.academicYear !== context.academicYear) {
    throw new Error('S3-B2 يسمح بالكتابة في العام الدراسي الحالي للجلسة فقط.');
  }

  const { data, error } = await getSupabaseClient().rpc('marsad_create_teacher_v1', {
    p_school_id: context.schoolId,
    p_academic_year_id: context.academicYearId,
    p_name: clean(input.name),
    p_subject: clean(input.subject),
    p_specialization: nullable(input.specialization),
    p_qualification: nullable(input.qualification),
    p_experience_years: input.experienceYears,
    p_workload: input.workload,
    p_email: nullable(input.email),
    p_phone: nullable(input.phone),
  });

  if (error) throw new Error('تعذر إنشاء المعلم في Supabase ضمن صلاحيات المدرسة الحالية.');
  const row = Array.isArray(data) ? data[0] : data;
  if (!row || typeof row !== 'object') throw new Error('لم تُرجع قاعدة البيانات نتيجة إنشاء صالحة.');
  const candidate = row as { teacher_id?: unknown; linked_existing?: unknown };
  return {
    teacherId: ensureSafeNumericId(candidate.teacher_id, 'معرف المعلم'),
    linkedExisting: candidate.linked_existing === true,
  };
}

export async function updateSupabaseTeacher(
  context: TenantSessionContext,
  teacherId: number,
  input: UpdateTeacherProfileInput,
): Promise<number> {
  ensureManager(context);
  validateCoreFields(input);
  const safeTeacherId = ensureSafeNumericId(teacherId, 'معرف المعلم');
  const employeeNumber = clean(input.employeeNumber);
  const grades = clean(input.grades);
  const responsibilities = clean(input.responsibilities);
  const professionalSummary = clean(input.professionalSummary);

  if (employeeNumber.length > 80) throw new Error('الرقم الوظيفي أطول من الحد المسموح.');
  if (input.schoolJoinYear !== null && input.schoolJoinYear !== undefined) {
    if (!Number.isInteger(input.schoolJoinYear) || input.schoolJoinYear < 1950 || input.schoolJoinYear > 2100) {
      throw new Error('سنة الالتحاق بالمدرسة خارج النطاق المسموح.');
    }
  }
  if (grades.length > 220) throw new Error('بيان الصفوف أطول من الحد المسموح.');
  if (responsibilities.length > 2000) throw new Error('المسؤوليات أطول من الحد المسموح.');
  if (professionalSummary.length > 2500) throw new Error('الملخص المهني أطول من الحد المسموح.');

  const { data, error } = await getSupabaseClient().rpc('marsad_update_teacher_v1', {
    p_school_id: context.schoolId,
    p_academic_year_id: context.academicYearId,
    p_teacher_id: safeTeacherId,
    p_name: clean(input.name),
    p_subject: clean(input.subject),
    p_specialization: nullable(input.specialization),
    p_qualification: nullable(input.qualification),
    p_experience_years: input.experienceYears,
    p_workload: input.workload,
    p_email: nullable(input.email),
    p_phone: nullable(input.phone),
    p_employee_number: nullable(input.employeeNumber),
    p_school_join_year: input.schoolJoinYear ?? null,
    p_grades: nullable(input.grades),
    p_responsibilities: nullable(input.responsibilities),
    p_professional_summary: nullable(input.professionalSummary),
  });

  if (error) throw new Error('تعذر تحديث ملف المعلم في Supabase ضمن صلاحيات المدرسة الحالية.');
  return ensureSafeNumericId(data, 'معرف المعلم المحدّث');
}
