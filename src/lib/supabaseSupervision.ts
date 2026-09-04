import { getSupabaseClient } from './supabase';
import type { TenantSessionContext } from './supabaseSession';
import type { SupabaseTeachersReadSnapshot } from './supabaseTeachers';
import type {
  Activity,
  SupervisionAction,
  SupervisionActionBaseStatus,
  SupervisionActionInput,
  SupervisionActionStatus,
  SupervisionVisitDetails,
  SupervisionVisitEffectiveStatus,
  SupervisionVisitInput,
  SupervisionVisitRecord,
  SupervisionVisitStatus,
} from '../types';

export type SupabaseSupervisionSnapshot = {
  schoolId: string;
  academicYearId: number;
  academicYear: string;
  visits: SupervisionVisitRecord[];
  attention: SupervisionVisitRecord[];
  actionRowsInScope: number;
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
  title: string;
  responsible_teacher_id: number | null;
  due_date: string | null;
  status: SupervisionActionBaseStatus;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

type ActivityRow = {
  id: number;
  school_id: string;
  academic_year_id: number | null;
  activity_type: string;
  title: string;
  detail: string | null;
  entity_type: string | null;
  entity_id: number | null;
  created_at: string;
};

function clean(value: string | null | undefined): string {
  return (value || '').trim();
}

function ensureManager(context: TenantSessionContext): void {
  if (context.role !== 'owner' && context.role !== 'admin') {
    throw new Error('صلاحية التعديل في الإشراف متاحة لمالك النظام أو الإدارة فقط.');
  }
}

function ensureSafeNumericId(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} خارج النطاق الرقمي الآمن للواجهة.`);
  }
  return parsed;
}

function omanTodayIso(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Muscat', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const value = (type: 'year' | 'month' | 'day') => parts.find((part) => part.type === type)?.value || '';
  return `${value('year')}-${value('month')}-${value('day')}`;
}

function validateVisitInput(context: TenantSessionContext, input: SupervisionVisitInput): void {
  if (input.academicYear !== context.academicYear) throw new Error('عام الزيارة لا يطابق عام جلسة Supabase الحالية.');
  if (!Number.isSafeInteger(input.teacherId) || input.teacherId <= 0) throw new Error('اختر معلمًا صحيحًا للزيارة.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.visitDate)) throw new Error('تاريخ الزيارة غير صالح.');
  if (input.followupDate && input.followupDate < input.visitDate) throw new Error('موعد المتابعة يجب ألا يسبق تاريخ الزيارة.');
  const [start, end] = context.academicYear.split('/').map(Number);
  const visitYear = Number(input.visitDate.slice(0, 4));
  const followupYear = input.followupDate ? Number(input.followupDate.slice(0, 4)) : null;
  if (![start, end].includes(visitYear) || (followupYear !== null && ![start, end].includes(followupYear))) {
    throw new Error(`تاريخ الزيارة أو المتابعة لا ينسجم مع العام الدراسي ${context.academicYear}.`);
  }
  if (clean(input.visitType).length < 2 || clean(input.visitType).length > 100) throw new Error('نوع الزيارة غير صالح.');
}

function validateActionInput(input: SupervisionActionInput): void {
  if (clean(input.title).length < 3 || clean(input.title).length > 500) throw new Error('عنوان إجراء المتابعة يجب أن يكون بين 3 و500 حرف.');
  if (clean(input.notes).length > 2500) throw new Error('ملاحظات إجراء المتابعة أطول من الحد المسموح.');
  if (input.responsibleTeacherId != null && (!Number.isSafeInteger(input.responsibleTeacherId) || input.responsibleTeacherId <= 0)) {
    throw new Error('المعلم المسؤول عن الإجراء غير صالح.');
  }
}

function effectiveActionStatus(row: ActionRow, today: string): SupervisionActionStatus {
  if (row.status !== 'completed' && row.status !== 'cancelled' && row.due_date && row.due_date < today) return 'overdue';
  return row.status;
}

function effectiveVisitStatus(row: VisitRow, overdueActionCount: number, today: string): SupervisionVisitEffectiveStatus {
  if (row.status !== 'closed' && overdueActionCount > 0) return 'overdue';
  if (row.status === 'planned' && row.visit_date < today) return 'overdue';
  if (row.status === 'needs_followup' && row.followup_date && row.followup_date < today) return 'overdue';
  return row.status;
}

function teacherMap(snapshot: SupabaseTeachersReadSnapshot) {
  return new Map(snapshot.teachers.map((teacher) => [teacher.id, teacher]));
}

function mapVisit(
  row: VisitRow,
  teachers: ReturnType<typeof teacherMap>,
  actions: ActionRow[],
  academicYear: string,
  today: string,
): SupervisionVisitRecord {
  const id = ensureSafeNumericId(row.id, 'معرف الزيارة');
  const teacherId = ensureSafeNumericId(row.teacher_id, 'معرف معلم الزيارة');
  const teacher = teachers.get(teacherId);
  if (!teacher) throw new Error('أعادت RLS زيارة لمعلم خارج عام العمل الحالي.');
  const open = actions.filter((item) => item.status !== 'completed' && item.status !== 'cancelled');
  const overdue = open.filter((item) => item.due_date && item.due_date < today);
  return {
    id,
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
    academicYear,
    status: row.status,
    effectiveStatus: effectiveVisitStatus(row, overdue.length, today),
    actionCount: actions.length,
    openActionCount: open.length,
    completedActionCount: actions.filter((item) => item.status === 'completed').length,
    overdueActionCount: overdue.length,
    closedAt: row.closed_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

async function loadRows(context: TenantSessionContext): Promise<{ visits: VisitRow[]; actions: ActionRow[] }> {
  const client = getSupabaseClient();
  const visitsResult = await client
    .from('supervision_visits')
    .select('id, school_id, academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at, created_at, updated_at')
    .eq('school_id', context.schoolId)
    .eq('academic_year_id', context.academicYearId)
    .order('visit_date', { ascending: false })
    .order('id', { ascending: false });
  if (visitsResult.error) throw new Error('تعذر قراءة الزيارات الإشرافية عبر RLS.');
  const visits = (visitsResult.data || []) as VisitRow[];
  const ids = visits.map((row) => ensureSafeNumericId(row.id, 'معرف الزيارة'));
  let actions: ActionRow[] = [];
  if (ids.length) {
    const actionsResult = await client
      .from('supervision_actions')
      .select('id, school_id, visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .in('visit_id', ids);
    if (actionsResult.error) throw new Error('تعذر قراءة إجراءات المتابعة الإشرافية عبر RLS.');
    actions = (actionsResult.data || []) as ActionRow[];
  }
  return { visits, actions };
}

export async function loadSupabaseSupervisionSnapshot(
  context: TenantSessionContext,
  teachersSnapshot: SupabaseTeachersReadSnapshot,
): Promise<SupabaseSupervisionSnapshot> {
  if (teachersSnapshot.schoolId !== context.schoolId || teachersSnapshot.academicYearId !== context.academicYearId) {
    throw new Error('نطاق المعلمين لا يطابق نطاق الإشراف.');
  }
  const { visits: visitRows, actions } = await loadRows(context);
  const teachers = teacherMap(teachersSnapshot);
  const today = omanTodayIso();
  const byVisit = new Map<number, ActionRow[]>();
  for (const row of actions) {
    if (row.school_id !== context.schoolId) throw new Error('أعادت RLS إجراء متابعة من مدرسة أخرى.');
    const visitId = ensureSafeNumericId(row.visit_id, 'معرف زيارة الإجراء');
    const list = byVisit.get(visitId) || [];
    list.push(row);
    byVisit.set(visitId, list);
  }
  const visits = visitRows.map((row) => {
    if (row.school_id !== context.schoolId || ensureSafeNumericId(row.academic_year_id, 'معرف عام الزيارة') !== context.academicYearId) {
      throw new Error('أعادت RLS زيارة خارج نطاق المدرسة أو العام الحالي.');
    }
    return mapVisit(row, teachers, byVisit.get(ensureSafeNumericId(row.id, 'معرف الزيارة')) || [], context.academicYear, today);
  });
  const attention = visits
    .filter((visit) => visit.status !== 'closed' && visit.effectiveStatus === 'overdue')
    .sort((a, b) => (a.followupDate || a.visitDate).localeCompare(b.followupDate || b.visitDate));
  return {
    schoolId: context.schoolId,
    academicYearId: context.academicYearId,
    academicYear: context.academicYear,
    visits,
    attention,
    actionRowsInScope: actions.length,
  };
}

export async function getSupabaseSupervisionVisit(
  context: TenantSessionContext,
  teachersSnapshot: SupabaseTeachersReadSnapshot,
  visitId: number,
): Promise<SupervisionVisitDetails> {
  const safeVisitId = ensureSafeNumericId(visitId, 'معرف الزيارة');
  const client = getSupabaseClient();
  const [visitResult, actionsResult, timelineResult] = await Promise.all([
    client
      .from('supervision_visits')
      .select('id, school_id, academic_year_id, teacher_id, visit_type, visit_date, period_label, grade, lesson_title, objectives, strengths, development_areas, recommendations, followup_date, followup_notes, status, closed_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .eq('id', safeVisitId)
      .maybeSingle(),
    client
      .from('supervision_actions')
      .select('id, school_id, visit_id, title, responsible_teacher_id, due_date, status, notes, completed_at, created_at, updated_at')
      .eq('school_id', context.schoolId)
      .eq('visit_id', safeVisitId),
    client
      .from('activities')
      .select('id, school_id, academic_year_id, activity_type, title, detail, entity_type, entity_id, created_at')
      .eq('school_id', context.schoolId)
      .eq('academic_year_id', context.academicYearId)
      .eq('entity_type', 'supervision_visit')
      .eq('entity_id', safeVisitId)
      .order('created_at', { ascending: false })
      .order('id', { ascending: false })
      .limit(40),
  ]);
  if (visitResult.error) throw new Error('تعذر فتح الزيارة الإشرافية عبر RLS.');
  if (!visitResult.data) throw new Error('الزيارة غير موجودة ضمن المدرسة والعام الحاليين.');
  if (actionsResult.error) throw new Error('تعذر قراءة إجراءات متابعة الزيارة.');
  if (timelineResult.error) throw new Error('تعذر قراءة السجل الزمني للزيارة.');

  const row = visitResult.data as VisitRow;
  const actionRows = (actionsResult.data || []) as ActionRow[];
  const teachers = teacherMap(teachersSnapshot);
  const today = omanTodayIso();
  const base = mapVisit(row, teachers, actionRows, context.academicYear, today);
  const actions: SupervisionAction[] = actionRows
    .map((action) => {
      const responsibleId = action.responsible_teacher_id == null ? null : ensureSafeNumericId(action.responsible_teacher_id, 'معرف مسؤول الإجراء');
      const responsible = responsibleId == null ? null : teachers.get(responsibleId);
      return {
        id: ensureSafeNumericId(action.id, 'معرف الإجراء'),
        visitId: safeVisitId,
        title: clean(action.title),
        responsibleTeacherId: responsibleId,
        responsibleName: responsible?.name || null,
        dueDate: action.due_date,
        status: effectiveActionStatus(action, today),
        baseStatus: action.status,
        notes: clean(action.notes) || null,
        completedAt: action.completed_at,
        createdAt: action.created_at,
        updatedAt: action.updated_at,
      };
    })
    .sort((a, b) => {
      const aDone = a.baseStatus === 'completed' ? 1 : 0;
      const bDone = b.baseStatus === 'completed' ? 1 : 0;
      if (aDone !== bDone) return aDone - bDone;
      return (a.dueDate || '9999-12-31').localeCompare(b.dueDate || '9999-12-31') || a.id - b.id;
    });
  const timeline: Activity[] = ((timelineResult.data || []) as ActivityRow[]).map((item) => ({
    id: ensureSafeNumericId(item.id, 'معرف النشاط'),
    activity_type: clean(item.activity_type),
    title: clean(item.title),
    detail: clean(item.detail) || null,
    created_at: item.created_at,
  }));
  return {
    ...base,
    actions,
    timeline,
    reportReady: base.status !== 'planned'
      && Boolean(clean(base.lessonTitle))
      && Boolean(clean(base.strengths) || clean(base.developmentAreas))
      && Boolean(clean(base.recommendations)),
  };
}

export async function createSupabaseSupervisionVisit(context: TenantSessionContext, input: SupervisionVisitInput): Promise<{ id: number }> {
  ensureManager(context);
  validateVisitInput(context, input);
  const { data, error } = await getSupabaseClient().rpc('marsad_create_supervision_visit_v1', {
    p_school_id: context.schoolId,
    p_academic_year_id: context.academicYearId,
    p_teacher_id: input.teacherId,
    p_visit_type: clean(input.visitType),
    p_visit_date: input.visitDate,
    p_period_label: clean(input.periodLabel),
    p_grade: clean(input.grade),
    p_lesson_title: clean(input.lessonTitle),
    p_objectives: clean(input.objectives),
    p_strengths: clean(input.strengths),
    p_development_areas: clean(input.developmentAreas),
    p_recommendations: clean(input.recommendations),
    p_followup_date: input.followupDate || null,
    p_followup_notes: clean(input.followupNotes),
    p_status: input.status,
  });
  if (error) throw new Error('تعذر إنشاء الزيارة في Supabase. تحقق من الصلاحيات وبيانات العام والمعلم.');
  return { id: ensureSafeNumericId(data, 'معرف الزيارة الجديدة') };
}

export async function updateSupabaseSupervisionVisit(context: TenantSessionContext, visitId: number, input: SupervisionVisitInput): Promise<void> {
  ensureManager(context);
  validateVisitInput(context, input);
  const { error } = await getSupabaseClient().rpc('marsad_update_supervision_visit_v1', {
    p_school_id: context.schoolId,
    p_academic_year_id: context.academicYearId,
    p_visit_id: ensureSafeNumericId(visitId, 'معرف الزيارة'),
    p_teacher_id: input.teacherId,
    p_visit_type: clean(input.visitType),
    p_visit_date: input.visitDate,
    p_period_label: clean(input.periodLabel),
    p_grade: clean(input.grade),
    p_lesson_title: clean(input.lessonTitle),
    p_objectives: clean(input.objectives),
    p_strengths: clean(input.strengths),
    p_development_areas: clean(input.developmentAreas),
    p_recommendations: clean(input.recommendations),
    p_followup_date: input.followupDate || null,
    p_followup_notes: clean(input.followupNotes),
    p_status: input.status,
  });
  if (error) throw new Error('تعذر تحديث الزيارة في Supabase.');
}

export async function createSupabaseSupervisionAction(
  context: TenantSessionContext,
  visitId: number,
  input: SupervisionActionInput,
): Promise<SupervisionAction> {
  ensureManager(context);
  validateActionInput(input);
  const safeVisitId = ensureSafeNumericId(visitId, 'معرف الزيارة');
  const { data, error } = await getSupabaseClient().rpc('marsad_create_supervision_action_v1', {
    p_school_id: context.schoolId,
    p_visit_id: safeVisitId,
    p_title: clean(input.title),
    p_responsible_teacher_id: input.responsibleTeacherId ?? null,
    p_due_date: input.dueDate || null,
    p_status: input.status,
    p_notes: clean(input.notes),
  });
  if (error) throw new Error('تعذر إنشاء إجراء المتابعة في Supabase.');
  return {
    id: ensureSafeNumericId(data, 'معرف إجراء المتابعة'), visitId: safeVisitId,
    title: clean(input.title), responsibleTeacherId: input.responsibleTeacherId ?? null,
    responsibleName: null, dueDate: input.dueDate || null, status: input.status,
    baseStatus: input.status, notes: clean(input.notes) || null, completedAt: null,
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
}

export async function updateSupabaseSupervisionAction(
  context: TenantSessionContext,
  visitId: number,
  actionId: number,
  input: SupervisionActionInput,
): Promise<SupervisionAction> {
  ensureManager(context);
  validateActionInput(input);
  const safeVisitId = ensureSafeNumericId(visitId, 'معرف الزيارة');
  const safeActionId = ensureSafeNumericId(actionId, 'معرف الإجراء');
  const { error } = await getSupabaseClient().rpc('marsad_update_supervision_action_v1', {
    p_school_id: context.schoolId,
    p_visit_id: safeVisitId,
    p_action_id: safeActionId,
    p_title: clean(input.title),
    p_responsible_teacher_id: input.responsibleTeacherId ?? null,
    p_due_date: input.dueDate || null,
    p_status: input.status,
    p_notes: clean(input.notes),
  });
  if (error) throw new Error('تعذر تحديث إجراء المتابعة في Supabase.');
  return {
    id: safeActionId, visitId: safeVisitId, title: clean(input.title),
    responsibleTeacherId: input.responsibleTeacherId ?? null, responsibleName: null,
    dueDate: input.dueDate || null, status: input.status, baseStatus: input.status,
    notes: clean(input.notes) || null, completedAt: null,
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
}

export async function deleteSupabaseSupervisionAction(context: TenantSessionContext, visitId: number, actionId: number): Promise<void> {
  ensureManager(context);
  const { error } = await getSupabaseClient().rpc('marsad_delete_supervision_action_v1', {
    p_school_id: context.schoolId,
    p_visit_id: ensureSafeNumericId(visitId, 'معرف الزيارة'),
    p_action_id: ensureSafeNumericId(actionId, 'معرف الإجراء'),
  });
  if (error) throw new Error('تعذر حذف إجراء المتابعة من Supabase.');
}
