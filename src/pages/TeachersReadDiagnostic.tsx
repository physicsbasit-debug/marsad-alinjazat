import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Icon } from '../components/Icon';
import { getSupabaseConfigurationStatus } from '../lib/supabase';
import {
  loadTenantSessionContext,
  signInWithEmail,
  signOutSupabase,
  subscribeToAuthChanges,
  type TenantSessionContext,
} from '../lib/supabaseSession';
import {
  compareTeacherReadParity,
  loadSupabaseTeachersReadSnapshot,
  type SupabaseTeachersReadSnapshot,
} from '../lib/supabaseTeachers';

export function TeachersReadDiagnostic() {
  const config = getSupabaseConfigurationStatus();
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [snapshot, setSnapshot] = useState<SupabaseTeachersReadSnapshot | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(config.configured);
  const [error, setError] = useState('');

  const parity = useMemo(
    () => snapshot ? compareTeacherReadParity(null, snapshot.teachers) : null,
    [snapshot],
  );

  const refresh = useCallback(async () => {
    if (!config.configured) {
      setLoading(false);
      return;
    }
    try {
      setError('');
      setLoading(true);
      const nextContext = await loadTenantSessionContext();
      setContext(nextContext);
      if (!nextContext) {
        setSnapshot(null);
        return;
      }
      setSnapshot(await loadSupabaseTeachersReadSnapshot(nextContext));
    } catch (err) {
      setSnapshot(null);
      setError(err instanceof Error ? err.message : 'تعذر التحقق من قراءة مجال المعلمين.');
    } finally {
      setLoading(false);
    }
  }, [config.configured]);

  useEffect(() => {
    void refresh();
    return subscribeToAuthChanges(() => {
      void refresh();
    });
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setError('');
      setLoading(true);
      await signInWithEmail(email, password);
      setPassword('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذر تسجيل الدخول.');
      setLoading(false);
    }
  }

  async function logout() {
    try {
      setError('');
      setLoading(true);
      await signOutSupabase();
      setContext(null);
      setSnapshot(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذر تسجيل الخروج.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-diagnostic-shell teachers-read-shell" dir="rtl">
      <section className="auth-diagnostic-card teachers-read-card">
        <div className="auth-diagnostic-brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>S3-B1 · قراءة المعلمين من Supabase</small></div></div>
        <div className="auth-diagnostic-heading">
          <span className="eyebrow">بوابة قراءة فقط</span>
          <h1>Teachers Read Repository</h1>
          <p>هذه البوابة تقرأ مجال المعلمين عبر RLS وفي نطاق المدرسة والعام الحاليين. لا تغيّر صفحة المعلمين التشغيلية ولا تنشئ أو تعدل أو تحذف أي سجل.</p>
        </div>

        {!config.configured ? (
          <div className="auth-status auth-status-warning"><Icon name="alert" size={22}/><div><strong>اتصال Supabase غير مهيأ</strong><span>تحقق من Repository Variables ثم أعد بناء GitHub Pages.</span></div></div>
        ) : loading ? (
          <div className="auth-status"><span className="spinner"/><div><strong>جارٍ التحقق</strong><span>نحل الجلسة ثم نقرأ teachers وteacher_years وteacher_profiles وteacher_cv_items.</span></div></div>
        ) : snapshot && context ? (
          <>
            <div className="auth-status auth-status-success"><Icon name="check" size={22}/><div><strong>PASS: S3-B1 Teachers Read Repository</strong><span>نجحت القراءة المقيدة بـRLS للمدرسة والعام الحالي.</span></div></div>
            <dl className="auth-facts teachers-read-facts">
              <div><dt>المدرسة</dt><dd>{snapshot.schoolName}</dd></div>
              <div><dt>العام</dt><dd>{snapshot.academicYear}</dd></div>
              <div><dt>معلمو العام</dt><dd>{snapshot.teachers.length}</dd></div>
              <div><dt>صفوف teachers المرئية عبر RLS</dt><dd>{snapshot.teacherRowsInSchool}</dd></div>
              <div><dt>teacher_years في النطاق</dt><dd>{snapshot.teacherYearRowsInScope}</dd></div>
              <div><dt>teacher_profiles المرئية</dt><dd>{snapshot.profileRowsInSchool}</dd></div>
            </dl>

            <div className="teachers-parity-gate">
              <div><strong>Parity Gate</strong><span>{parity?.status === 'match' ? 'MATCH' : 'NOT ESTABLISHED'}</span></div>
              <p>{parity?.detail}</p>
              <b>التحويل التشغيلي غير معتمد في S3-B1. صفحة المعلمين الحالية تبقى على Legacy.</b>
            </div>

            {snapshot.teachers.length === 0 ? (
              <div className="teachers-empty-read"><Icon name="teachers" size={24}/><div><strong>قراءة فارغة صحيحة</strong><span>لا توجد صفوف معلمين مرتبطة بالعام الحالي في Supabase. هذا يثبت سلامة مسار القراءة، لكنه لا يبرر Cutover ولا يزرع بيانات وهمية.</span></div></div>
            ) : (
              <div className="teachers-read-list">
                {snapshot.teachers.map((teacher) => (
                  <article key={teacher.id}>
                    <div className="avatar">{teacher.name[0] || 'م'}</div>
                    <div><strong>{teacher.name}</strong><span>{teacher.subject || 'المادة غير مسجلة'} · نصاب {teacher.workload}</span></div>
                    <small>{teacher.readCompleteness}% اكتمال مقروء</small>
                  </article>
                ))}
              </div>
            )}

            <button className="ghost-button wide" onClick={() => void logout()}>تسجيل الخروج من جلسة الاختبار</button>
          </>
        ) : (
          <form className="auth-login-form" onSubmit={submit}>
            <label>البريد الإلكتروني<input type="email" autoComplete="email" value={email} onChange={(e: ChangeEvent<HTMLInputElement>)=>setEmail(e.target.value)} required/></label>
            <label>كلمة المرور<input type="password" autoComplete="current-password" value={password} onChange={(e: ChangeEvent<HTMLInputElement>)=>setPassword(e.target.value)} required/></label>
            <button className="primary-button wide" type="submit">تسجيل الدخول وفحص قراءة المعلمين</button>
          </form>
        )}

        {error && <div className="auth-status auth-status-error"><Icon name="alert" size={22}/><div><strong>فشل التحقق</strong><span>{error}</span></div></div>}
        <p className="auth-diagnostic-note">S3-B1 قراءة فقط. لا توجد كتابة مجالّية، ولا Migration، ولا تغيير في RLS.</p>
      </section>
    </main>
  );
}
