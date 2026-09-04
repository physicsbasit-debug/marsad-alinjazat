import { useCallback, useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { loadTenantSessionContext, signInWithEmail, subscribeToAuthChanges } from '../lib/supabaseSession';
import type { TenantSessionContext } from '../lib/supabaseSession';
import {
  loadSupabaseRequestsDocumentsSnapshot,
  updateSupabaseRequestStatus,
} from '../lib/supabaseRequestsDocuments';
import type { SupabaseRequestsDocumentsSnapshot } from '../lib/supabaseRequestsDocuments';
import type { RequestStatus, UploadRequest } from '../types';
import { Requests } from './Requests';

export type RequestsDocumentsDataMode = 'legacy' | 'supabase';
const rawMode = (import.meta.env.VITE_REQUESTS_DOCUMENTS_DATA_MODE || 'legacy').trim().toLowerCase();
export const REQUESTS_DOCUMENTS_DATA_MODE: RequestsDocumentsDataMode = rawMode === 'supabase' ? 'supabase' : 'legacy';

export function RequestsWorkspace({
  legacyRequests,
  academicYear,
  currentAcademicYear,
  onLegacyNewRequest,
  onLegacyStatus,
  onSupabaseOpenRequestCount,
}: {
  legacyRequests: UploadRequest[];
  academicYear: string;
  currentAcademicYear: string;
  onLegacyNewRequest: () => void;
  onLegacyStatus: (id: number, status: RequestStatus) => Promise<void>;
  onSupabaseOpenRequestCount?: (count: number | null) => void;
}) {
  const eligible = REQUESTS_DOCUMENTS_DATA_MODE === 'supabase' && academicYear === currentAcademicYear;
  const [forceLegacy, setForceLegacy] = useState(false);
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [snapshot, setSnapshot] = useState<SupabaseRequestsDocumentsSnapshot | null>(null);
  const [loading, setLoading] = useState(eligible);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!eligible) return;
    setLoading(true);
    setError('');
    try {
      const nextContext = await loadTenantSessionContext();
      if (!nextContext) {
        setContext(null);
        setSnapshot(null);
        onSupabaseOpenRequestCount?.(null);
        return;
      }
      if (nextContext.academicYear !== academicYear) throw new Error('جلسة Supabase لا تطابق عام العمل الحالي.');
      const nextSnapshot = await loadSupabaseRequestsDocumentsSnapshot(nextContext);
      setContext(nextContext);
      setSnapshot(nextSnapshot);
      onSupabaseOpenRequestCount?.(nextSnapshot.openRequestCount);
    } catch (caught) {
      setSnapshot(null);
      onSupabaseOpenRequestCount?.(null);
      setError(caught instanceof Error ? caught.message : 'تعذر تحميل طلبات الملفات من Supabase.');
    } finally {
      setLoading(false);
    }
  }, [academicYear, eligible, onSupabaseOpenRequestCount]);

  useEffect(() => {
    setForceLegacy(false);
    setContext(null);
    setSnapshot(null);
    if (!eligible) {
      onSupabaseOpenRequestCount?.(null);
      return;
    }
    void load();
    return subscribeToAuthChanges(() => { void load(); });
  }, [academicYear, eligible]);

  if (!eligible || forceLegacy) {
    return <>
      <BoundaryBanner
        source="legacy"
        detail={academicYear !== currentAcademicYear
          ? 'إدارة طلبات الأعوام التاريخية تبقى على Legacy في هذه المرحلة.'
          : 'تم تفعيل الرجوع المؤقت إلى Legacy لهذه الجلسة.'}
        onRestore={eligible ? () => { setForceLegacy(false); void load(); } : undefined}
      />
      <Requests requests={legacyRequests} onNewRequest={onLegacyNewRequest} onStatus={onLegacyStatus} />
    </>;
  }

  if (loading) return <BoundaryState title="جاري تشغيل طلبات الملفات من Supabase" detail="يتم التحقق من الجلسة وRLS وعام العمل." busy />;
  if (!context) return <LoginGate error={error} onSignedIn={load} onLegacy={() => setForceLegacy(true)} />;
  if (error || !snapshot) return <BoundaryState title="تعذر تشغيل طلبات الملفات من Supabase" detail={error || 'لم تكتمل القراءة.'} onRetry={() => void load()} onLegacy={() => setForceLegacy(true)} />;

  async function changeStatus(id: number, status: RequestStatus): Promise<void> {
    if (!context) return;
    await updateSupabaseRequestStatus(context, id, status);
    await load();
  }

  return <>
    <BoundaryBanner
      source="supabase"
      detail={`المصدر: Supabase / RLS • ${context.schoolName} • ${context.academicYear} • الطلبات المفتوحة: ${snapshot.openRequestCount}`}
      onRefresh={() => void load()}
      onLegacy={() => { setForceLegacy(true); onSupabaseOpenRequestCount?.(null); }}
    />
    <Requests
      requests={snapshot.requests}
      onNewRequest={() => undefined}
      onStatus={changeStatus}
      canCreate={false}
      sourceNotice="S3-C3A نقل القراءة والمراجعة فقط. إنشاء رابط رفع جديد ينتظر مرحلة الرفع العام والتخزين حتى لا ننشئ رابطًا لا يستطيع المعلم استخدامه."
    />
  </>;
}

function BoundaryBanner({ source, detail, onLegacy, onRestore, onRefresh }: { source: 'supabase' | 'legacy'; detail: string; onLegacy?: () => void; onRestore?: () => void; onRefresh?: () => void }) {
  return <div className={`teacher-source-banner ${source}`}><div><span className="teacher-source-dot"/><div><strong>{source === 'supabase' ? 'S3-C3A • طلبات Supabase' : 'مصدر Legacy مؤقت'}</strong><span>{detail}</span></div></div><div className="teacher-source-actions">{onRefresh&&<button type="button" onClick={onRefresh}><Icon name="arrow" size={15}/> تحديث</button>}{onLegacy&&<button type="button" onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}{onRestore&&<button type="button" onClick={onRestore}>إعادة Supabase</button>}</div></div>;
}

function BoundaryState({ title, detail, busy, onRetry, onLegacy }: { title: string; detail: string; busy?: boolean; onRetry?: () => void; onLegacy?: () => void }) {
  return <div className="teacher-cutover-state"><div className="teacher-cutover-card">{busy?<div className="spinner"/>:<Icon name="alert" size={28}/>}<h2>{title}</h2><p>{detail}</p><div className="teacher-source-actions">{onRetry&&<button className="primary-button" onClick={onRetry}>إعادة المحاولة</button>}{onLegacy&&<button className="ghost-button" onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}</div></div></div>;
}

function LoginGate({ error, onSignedIn, onLegacy }: { error: string; onSignedIn: () => Promise<void>; onLegacy: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(error);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setMessage('');
    try { await signInWithEmail(String(form.get('email') || ''), String(form.get('password') || '')); await onSignedIn(); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : 'تعذر تسجيل الدخول.'); }
    finally { setBusy(false); }
  }
  return <div className="teacher-cutover-state"><div className="teacher-cutover-card"><span className="eyebrow">S3-C3A • Supabase</span><h2>تسجيل الدخول لإدارة طلبات الملفات</h2><form onSubmit={submit} className="teacher-login-form"><label>البريد الإلكتروني<input type="email" name="email" autoComplete="email" required/></label><label>كلمة المرور<input type="password" name="password" autoComplete="current-password" required/></label>{message&&<div className="inline-error"><Icon name="alert" size={16}/>{message}</div>}<button className="primary-button" disabled={busy}>{busy?'جاري التحقق...':'تسجيل الدخول'}</button></form><button type="button" className="ghost-button" onClick={onLegacy}>استخدام Legacy مؤقتًا</button></div></div>;
}
