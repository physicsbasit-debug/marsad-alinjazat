import type { AuthChangeEvent, Session } from '@supabase/supabase-js';
import { getSupabaseClient, SUPABASE_CONFIGURED } from './supabase';

export type TenantRole = 'owner' | 'admin' | 'lead_teacher' | 'teacher' | 'viewer';
export type SupabaseSessionMode = 'off' | 'diagnostic' | 'required';

export interface TenantSessionContext {
  session: Session;
  userId: string;
  email: string | null;
  displayName: string | null;
  schoolId: string;
  schoolName: string;
  role: TenantRole;
  teacherId: number | null;
  academicYearId: number;
  academicYear: string;
}

const rawMode = (import.meta.env.VITE_SUPABASE_SESSION_MODE || 'off').trim().toLowerCase();
export const SUPABASE_SESSION_MODE: SupabaseSessionMode =
  rawMode === 'diagnostic' || rawMode === 'required' ? rawMode : 'off';

function describeAuthError(error: unknown): string {
  const code = typeof error === 'object' && error && 'code' in error ? String(error.code || '') : '';
  const status = typeof error === 'object' && error && 'status' in error ? Number(error.status || 0) : 0;
  if (code === 'invalid_credentials' || status === 400) return 'البريد الإلكتروني أو كلمة المرور غير صحيحة.';
  if (code === 'email_not_confirmed') return 'الحساب موجود لكن البريد الإلكتروني لم يُؤكَّد بعد.';
  if (status === 429) return 'تمت محاولات دخول كثيرة. انتظر قليلًا ثم أعد المحاولة.';
  return 'تعذر إكمال المصادقة مع Supabase. أعد المحاولة بعد قليل.';
}

function ensureConfigured(): void {
  if (!SUPABASE_CONFIGURED) {
    throw new Error('اتصال Supabase غير مهيأ في هذه النسخة.');
  }
}

export async function signInWithEmail(email: string, password: string): Promise<void> {
  ensureConfigured();
  const client = getSupabaseClient();
  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail || !password) throw new Error('أدخل البريد الإلكتروني وكلمة المرور.');
  const { error } = await client.auth.signInWithPassword({ email: normalizedEmail, password });
  if (error) throw new Error(describeAuthError(error));
}

export async function signOutSupabase(): Promise<void> {
  if (!SUPABASE_CONFIGURED) return;
  const { error } = await getSupabaseClient().auth.signOut();
  if (error) throw new Error('تعذر تسجيل الخروج من Supabase.');
}

export async function getCurrentAuthSession(): Promise<Session | null> {
  ensureConfigured();
  const { data, error } = await getSupabaseClient().auth.getSession();
  if (error) throw new Error(describeAuthError(error));
  return data.session;
}

export async function loadTenantSessionContext(): Promise<TenantSessionContext | null> {
  ensureConfigured();
  const client = getSupabaseClient();
  const { data: sessionData, error: sessionError } = await client.auth.getSession();
  if (sessionError) throw new Error(describeAuthError(sessionError));
  const session = sessionData.session;
  if (!session) return null;

  const userId = session.user.id;

  const { data: profile, error: profileError } = await client
    .from('profiles')
    .select('id, display_name')
    .eq('id', userId)
    .maybeSingle();
  if (profileError) throw new Error('تعذر قراءة ملف المستخدم عبر سياسات RLS.');
  if (!profile) throw new Error('الحساب مسجل في Auth لكنه لا يملك ملفًا في profiles.');

  const { data: memberships, error: membershipError } = await client
    .from('school_memberships')
    .select('school_id, user_id, teacher_id, role, status')
    .eq('user_id', userId)
    .eq('status', 'active');
  if (membershipError) throw new Error('تعذر قراءة عضوية المدرسة عبر سياسات RLS.');
  if (!memberships || memberships.length === 0) throw new Error('لا توجد عضوية مدرسية نشطة لهذا الحساب.');
  if (memberships.length > 1) {
    throw new Error('الحساب مرتبط بأكثر من مدرسة نشطة. اختيار المدرسة سيُنفذ في مرحلة لاحقة.');
  }

  const membership = memberships[0] as {
    school_id: string;
    user_id: string;
    teacher_id: number | null;
    role: TenantRole;
    status: string;
  };

  const { data: school, error: schoolError } = await client
    .from('schools')
    .select('id, name, is_active')
    .eq('id', membership.school_id)
    .maybeSingle();
  if (schoolError) throw new Error('تعذر قراءة المدرسة المرتبطة بالحساب.');
  if (!school || school.is_active !== true) throw new Error('المدرسة المرتبطة بالحساب غير متاحة أو غير نشطة.');

  const { data: years, error: yearError } = await client
    .from('academic_years')
    .select('id, label, is_current')
    .eq('school_id', membership.school_id)
    .eq('is_current', true);
  if (yearError) throw new Error('تعذر قراءة العام الدراسي الحالي عبر RLS.');
  if (!years || years.length !== 1) throw new Error('يجب أن يكون للمدرسة عام دراسي حالي واحد بالضبط.');

  const currentYear = years[0] as { id: number; label: string; is_current: boolean };
  return {
    session,
    userId,
    email: session.user.email || null,
    displayName: (profile as { display_name: string | null }).display_name || null,
    schoolId: membership.school_id,
    schoolName: (school as { name: string }).name,
    role: membership.role,
    teacherId: membership.teacher_id,
    academicYearId: currentYear.id,
    academicYear: currentYear.label,
  };
}

export function subscribeToAuthChanges(
  callback: (event: AuthChangeEvent, session: Session | null) => void,
): () => void {
  if (!SUPABASE_CONFIGURED) return () => undefined;
  const { data } = getSupabaseClient().auth.onAuthStateChange((event, session) => callback(event, session));
  return () => data.subscription.unsubscribe();
}
