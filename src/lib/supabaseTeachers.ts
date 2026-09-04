import type { Teacher } from '../types';
import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';

export type SupabaseTeacherReadRecord = {
  id: number;
  schoolId: string;
  academicYearId: number;
  name: string;
  subject: string;
  specialization: string | null;
  qualification: string | null;
  experienceYears: number;
  workload: number;
  email: string | null;
  phone: string | null;
  employeeNumber: string | null;
  schoolJoinYear: number | null;
  professionalSummary: string | null;
  grades: string | null;
  responsibilities: string | null;
  cvItemCount: number;
  readCompleteness: number;
};

export type SupabaseTeachersReadSnapshot = {
  schoolId: string;
  schoolName: string;
  academicYearId: number;
  academicYear: string;
  role: TenantSessionContext['role'];
  teacherRowsInSchool: number;
  teacherYearRowsInScope: number;
  profileRowsInSchool: number;
  cvItemRowsInSchool: number;
  teachers: SupabaseTeacherReadRecord[];
};

export type LegacyTeacherParitySource = {
  kind: 'real_legacy';
  teachers: Teacher[];
};

export type TeacherParityResult = {
  status: 'match' | 'mismatch' | 'not_comparable';
  legacyCount: number | null;
  supabaseCount: number;
  matchedCount: number;
  missingInSupabase: string[];
  extraInSupabase: string[];
  detail: string;
};

type TeacherRow = {
  id: number;
  school_id: string;
  name: string;
  specialization: string | null;
  qualification: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean;
};

type TeacherYearRow = {
  school_id: string;
  academic_year_id: number;
  teacher_id: number;
  subject: string | null;
  experience_years: number | null;
  workload: number | null;
  grades: string | null;
  responsibilities: string | null;
  is_active: boolean;
};

type TeacherProfileRow = {
  teacher_id: number;
  school_id: string;
  employee_number: string | null;
  school_join_year: number | null;
  professional_summary: string | null;
};

type TeacherCvRow = {
  id: number;
  school_id: string;
  teacher_id: number;
};

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

function calculateReadCompleteness(
  teacher: TeacherRow,
  year: TeacherYearRow,
  profile: TeacherProfileRow | undefined,
  cvItemCount: number,
): number {
  let score = 20;
  score += clean(teacher.specialization) ? 10 : 0;
  score += clean(teacher.qualification) ? 15 : 0;
  score += clean(teacher.email) ? 10 : 0;
  score += clean(teacher.phone) ? 5 : 0;
  score += clean(profile?.professional_summary) ? 10 : 0;
  score += clean(year.responsibilities) ? 10 : 0;
  score += clean(year.grades) ? 5 : 0;
  score += clean(profile?.employee_number) ? 5 : 0;
  score += cvItemCount > 0 ? 10 : 0;
  return Math.min(100, score);
}

function ensureSafeNumericId(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} خارج النطاق الرقمي الآمن للواجهة.`);
  }
  return parsed;
}

function normalizeName(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLocaleLowerCase('ar');
}

function parityKeyFromSupabase(item: SupabaseTeacherReadRecord): string {
  const email = clean(item.email).toLowerCase();
  if (email) return `email:${email}`;
  return `name-subject:${normalizeName(item.name)}|${normalizeName(item.subject)}`;
}

function parityKeyFromLegacy(item: Teacher): string {
  const email = clean(item.email).toLowerCase();
  if (email) return `email:${email}`;
  return `name-subject:${normalizeName(item.name)}|${normalizeName(item.subject)}`;
}

export function compareTeacherReadParity(
  legacySource: LegacyTeacherParitySource | null,
  supabaseTeachers: SupabaseTeacherReadRecord[],
): TeacherParityResult {
  if (legacySource === null) {
    return {
      status: 'not_comparable',
      legacyCount: null,
      supabaseCount: supabaseTeachers.length,
      matchedCount: 0,
      missingInSupabase: [],
      extraInSupabase: [],
      detail: 'مصدر Legacy الحقيقي غير متاح لهذه المعاينة، لذلك لا يُسمح بالتحويل التشغيلي بعد.',
    };
  }

  const legacyTeachers = legacySource.teachers;
  const legacyKeys = new Set(legacyTeachers.map(parityKeyFromLegacy));
  const supabaseKeys = new Set(supabaseTeachers.map(parityKeyFromSupabase));
  const missingInSupabase = [...legacyKeys].filter((key) => !supabaseKeys.has(key)).sort();
  const extraInSupabase = [...supabaseKeys].filter((key) => !legacyKeys.has(key)).sort();
  const matchedCount = [...legacyKeys].filter((key) => supabaseKeys.has(key)).length;
  const status = missingInSupabase.length === 0 && extraInSupabase.length === 0 ? 'match' : 'mismatch';
  return {
    status,
    legacyCount: legacyTeachers.length,
    supabaseCount: supabaseTeachers.length,
    matchedCount,
    missingInSupabase,
    extraInSupabase,
    detail: status === 'match'
      ? 'تطابقت هويات المعلمين بين المصدرين ضمن نطاق المقارنة.'
      : 'يوجد اختلاف بين المصدرين، لذلك يبقى التحويل التشغيلي محظورًا.',
  };
}

export async function loadSupabaseTeachersReadSnapshot(
  context: TenantSessionContext,
): Promise<SupabaseTeachersReadSnapshot> {
  const client = getSupabaseClient();

  const [teachersResult, yearsResult, profilesResult, cvResult] = await Promise.all([
    client
      .from('teachers')
      .select('id, school_id, name, specialization, qualification, email, phone, is_active')
      .eq('school_id', context.schoolId)
      .order('name', { ascending: true }),
    client
      .from('teacher_years')
      .select('school_id, academic_year_id, teacher_id, subject, experience_years, workload, grades, responsibilities, is_active')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .eq('is_active', true)
      .order('teacher_id', { ascending: true }),
    client
      .from('teacher_profiles')
      .select('teacher_id, school_id, employee_number, school_join_year, professional_summary')
      .eq('school_id', context.schoolId),
    client
      .from('teacher_cv_items')
      .select('id, school_id, teacher_id')
      .eq('school_id', context.schoolId),
  ]);

  if (teachersResult.error) throw new Error('تعذر قراءة جدول المعلمين عبر RLS.');
  if (yearsResult.error) throw new Error('تعذر قراءة ربط المعلمين بالعام الدراسي عبر RLS.');
  if (profilesResult.error) throw new Error('تعذر قراءة الملفات المهنية للمعلمين عبر RLS.');
  if (cvResult.error) throw new Error('تعذر قراءة بنود السيرة المهنية عبر RLS.');

  const teacherRows = (teachersResult.data || []) as TeacherRow[];
  const yearRows = (yearsResult.data || []) as TeacherYearRow[];
  const profileRows = (profilesResult.data || []) as TeacherProfileRow[];
  const cvRows = (cvResult.data || []) as TeacherCvRow[];

  const teachersById = new Map<number, TeacherRow>();
  for (const row of teacherRows) {
    const id = ensureSafeNumericId(row.id, 'معرف المعلم');
    if (row.school_id !== context.schoolId) throw new Error('أعاد RLS سجل معلم من مدرسة أخرى.');
    teachersById.set(id, { ...row, id });
  }

  const profilesByTeacher = new Map<number, TeacherProfileRow>();
  for (const row of profileRows) {
    if (row.school_id !== context.schoolId) throw new Error('أعاد RLS ملفًا مهنيًا من مدرسة أخرى.');
    profilesByTeacher.set(ensureSafeNumericId(row.teacher_id, 'معرف ملف المعلم'), row);
  }

  const cvCountByTeacher = new Map<number, number>();
  for (const row of cvRows) {
    if (row.school_id !== context.schoolId) throw new Error('أعاد RLS بند سيرة من مدرسة أخرى.');
    const teacherId = ensureSafeNumericId(row.teacher_id, 'معرف معلم السيرة');
    cvCountByTeacher.set(teacherId, (cvCountByTeacher.get(teacherId) || 0) + 1);
  }

  const teachers: SupabaseTeacherReadRecord[] = yearRows.map((yearRow) => {
    if (yearRow.school_id !== context.schoolId) throw new Error('أعاد RLS سجل سنة من مدرسة أخرى.');
    const academicYearId = ensureSafeNumericId(yearRow.academic_year_id, 'معرف العام الدراسي');
    if (academicYearId !== context.academicYearId) throw new Error('خرجت قراءة المعلمين عن العام الدراسي الحالي.');
    const teacherId = ensureSafeNumericId(yearRow.teacher_id, 'معرف المعلم السنوي');
    const teacher = teachersById.get(teacherId);
    if (!teacher) throw new Error(`تعذر ربط سجل السنة بالمعلم رقم ${teacherId}.`);
    const profile = profilesByTeacher.get(teacherId);
    const cvItemCount = cvCountByTeacher.get(teacherId) || 0;
    return {
      id: teacherId,
      schoolId: context.schoolId,
      academicYearId,
      name: clean(teacher.name),
      subject: clean(yearRow.subject),
      specialization: clean(teacher.specialization) || null,
      qualification: clean(teacher.qualification) || null,
      experienceYears: Number(yearRow.experience_years || 0),
      workload: Number(yearRow.workload || 0),
      email: clean(teacher.email) || null,
      phone: clean(teacher.phone) || null,
      employeeNumber: clean(profile?.employee_number) || null,
      schoolJoinYear: profile?.school_join_year ?? null,
      professionalSummary: clean(profile?.professional_summary) || null,
      grades: clean(yearRow.grades) || null,
      responsibilities: clean(yearRow.responsibilities) || null,
      cvItemCount,
      readCompleteness: calculateReadCompleteness(teacher, yearRow, profile, cvItemCount),
    };
  });

  teachers.sort((a, b) => a.name.localeCompare(b.name, 'ar'));

  return {
    schoolId: context.schoolId,
    schoolName: context.schoolName,
    academicYearId: context.academicYearId,
    academicYear: context.academicYear,
    role: context.role,
    teacherRowsInSchool: teacherRows.length,
    teacherYearRowsInScope: yearRows.length,
    profileRowsInSchool: profileRows.length,
    cvItemRowsInSchool: cvRows.length,
    teachers,
  };
}
