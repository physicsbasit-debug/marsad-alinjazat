import { FormEvent, useCallback, useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { getSupabaseConfigurationStatus } from '../lib/supabase';
import {
  loadTenantSessionContext,
  signInWithEmail,
  signOutSupabase,
  subscribeToAuthChanges,
  type TenantRole,
  type TenantSessionContext,
} from '../lib/supabaseSession';

const roleLabels: Record<TenantRole, string> = {
  owner: 'مالك النظام',
  admin: 'مدير',
  lead_teacher: 'معلم أول / منسق',
  teacher: 'معلم',
  viewer: 'مشاهد',
};

export function AuthDiagnostic() {
  const config = getSupabaseConfigurationStatus();
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(config.configured);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!config.configured) {
      setLoading(false);
      return;
    }
    try {
      setError('');
      setLoading(true);
      setContext(await loadTenantSessionContext());
    } catch (err) {
      setContext(null);
      setError(err instanceof Error ? err.message : 'تعذر التحقق من جلسة Supabase.');
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذر تسجيل الخروج.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-diagnostic-shell" dir="rtl">
      <section className="auth-diagnostic-card">
        <div className="auth-diagnostic-brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>S3-A · فحص Auth والجلسة المدرسية</small></div></div>
        <div className="auth-diagnostic-heading">
          <span className="eyebrow">بوابة قبول حيّة</span>
          <h1>التحقق من Supabase Auth وRLS</h1>
          <p>هذه الصفحة لا تنقل أي وحدة تشغيلية إلى Supabase. وظيفتها الوحيدة إثبات أن الحساب الحقيقي يصل إلى مدرسته وعضويته وعامه الدراسي عبر RLS.</p>
        </div>

        {!config.configured ? (
          <div className="auth-status auth-status-warning"><Icon name="alert" size={22}/><div><strong>متغيرات Supabase غير مضبوطة في GitHub Pages</strong><span>أضف VITE_SUPABASE_URL وVITE_SUPABASE_PUBLISHABLE_KEY كـRepository Variables ثم أعد تشغيل Workflow.</span></div></div>
        ) : loading ? (
          <div className="auth-status"><span className="spinner"/><div><strong>جارٍ التحقق</strong><span>نقرأ الجلسة والعضوية والمدرسة والسنة الحالية.</span></div></div>
        ) : context ? (
          <>
            <div className="auth-status auth-status-success"><Icon name="check" size={22}/><div><strong>PASS: S3-A Auth & Tenant Session</strong><span>نجحت المصادقة وقراءات RLS الأساسية.</span></div></div>
            <dl className="auth-facts">
              <div><dt>المستخدم</dt><dd>{context.displayName || context.email || 'حساب Supabase'}</dd></div>
              <div><dt>المدرسة</dt><dd>{context.schoolName}</dd></div>
              <div><dt>الدور</dt><dd>{roleLabels[context.role]}</dd></div>
              <div><dt>العام الحالي</dt><dd>{context.academicYear}</dd></div>
            </dl>
            <button className="ghost-button wide" onClick={() => void logout()}>تسجيل الخروج من جلسة الاختبار</button>
          </>
        ) : (
          <form className="auth-login-form" onSubmit={submit}>
            <label>البريد الإلكتروني<input type="email" autoComplete="email" value={email} onChange={(e)=>setEmail(e.target.value)} required/></label>
            <label>كلمة المرور<input type="password" autoComplete="current-password" value={password} onChange={(e)=>setPassword(e.target.value)} required/></label>
            <button className="primary-button wide" type="submit">تسجيل الدخول والتحقق</button>
          </form>
        )}

        {error && <div className="auth-status auth-status-error"><Icon name="alert" size={22}/><div><strong>فشل التحقق</strong><span>{error}</span></div></div>}
        <p className="auth-diagnostic-note">لا تُنشئ هذه الصفحة مستخدمًا، ولا تغيّر العضويات، ولا تكتب بيانات مجالّية.</p>
      </section>
    </main>
  );
}
