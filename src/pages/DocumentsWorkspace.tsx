import { useCallback, useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { loadTenantSessionContext, signInWithEmail, subscribeToAuthChanges } from '../lib/supabaseSession';
import type { TenantSessionContext } from '../lib/supabaseSession';
import { loadSupabaseRequestsDocumentsSnapshot } from '../lib/supabaseRequestsDocuments';
import type { SupabaseRequestsDocumentsSnapshot } from '../lib/supabaseRequestsDocuments';
import type { DocumentRecord, Teacher } from '../types';
import { Documents } from './Documents';
import { REQUESTS_DOCUMENTS_DATA_MODE } from './RequestsWorkspace';

export function DocumentsWorkspace({
  legacyDocuments,
  legacyTeachers,
  academicYear,
  currentAcademicYear,
  onLegacyRefresh,
}: {
  legacyDocuments: DocumentRecord[];
  legacyTeachers: Teacher[];
  academicYear: string;
  currentAcademicYear: string;
  onLegacyRefresh: () => Promise<void>;
}) {
  const eligible = REQUESTS_DOCUMENTS_DATA_MODE === 'supabase' && academicYear === currentAcademicYear;
  const [forceLegacy, setForceLegacy] = useState(false);
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [snapshot, setSnapshot] = useState<SupabaseRequestsDocumentsSnapshot | null>(null);
  const [loading, setLoading] = useState(eligible);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!eligible) return;
    setLoading(true); setError('');
    try {
      const nextContext = await loadTenantSessionContext();
      if (!nextContext) { setContext(null); setSnapshot(null); return; }
      if (nextContext.academicYear !== academicYear) throw new Error('جلسة Supabase لا تطابق عام العمل الحالي.');
      const nextSnapshot = await loadSupabaseRequestsDocumentsSnapshot(nextContext);
      setContext(nextContext); setSnapshot(nextSnapshot);
    } catch (caught) {
      setSnapshot(null);
      setError(caught instanceof Error ? caught.message : 'تعذر تحميل الوثائق من Supabase.');
    } finally { setLoading(false); }
  }, [academicYear, eligible]);

  useEffect(() => {
    setForceLegacy(false); setContext(null); setSnapshot(null);
    if (!eligible) return;
    void load();
    return subscribeToAuthChanges(() => { void load(); });
  }, [academicYear, eligible]);

  if (!eligible || forceLegacy) return <>
    <SourceBanner source="legacy" detail={academicYear !== currentAcademicYear ? 'وثائق الأعوام التاريخية تبقى على Legacy.' : 'تم الرجوع المؤقت إلى Legacy.'} onRestore={eligible ? () => { setForceLegacy(false); void load(); } : undefined}/>
    <Documents documents={legacyDocuments} teachers={legacyTeachers} academicYear={academicYear} onRefresh={onLegacyRefresh}/>
  </>;
  if (loading) return <State title="جاري تحميل سجل الوثائق من Supabase" detail="قراءة metadata فقط؛ الرفع الفعلي لم يُنقل بعد." busy/>;
  if (!context) return <Login error={error} onSignedIn={load} onLegacy={() => setForceLegacy(true)}/>;
  if (error || !snapshot) return <State title="تعذر تشغيل سجل الوثائق من Supabase" detail={error || 'لم تكتمل القراءة.'} onRetry={() => void load()} onLegacy={() => setForceLegacy(true)}/>;

  return <>
    <SourceBanner source="supabase" detail={`المصدر: Supabase / RLS • ${context.schoolName} • ${context.academicYear} • الوثائق: ${snapshot.documents.length}`} onRefresh={() => void load()} onLegacy={() => setForceLegacy(true)}/>
    <Documents
      documents={snapshot.documents}
      teachers={snapshot.teachers}
      academicYear={academicYear}
      onRefresh={load}
      canUpload={false}
      sourceNotice="S3-C3A ينقل فهرس الوثائق وبياناتها الوصفية فقط. رفع الملف نفسه ينتظر مرحلة Supabase Storage والرفع العام."
    />
  </>;
}

function SourceBanner({ source, detail, onLegacy, onRestore, onRefresh }: { source: 'supabase'|'legacy'; detail: string; onLegacy?: () => void; onRestore?: () => void; onRefresh?: () => void }) {
  return <div className={`teacher-source-banner ${source}`}><div><span className="teacher-source-dot"/><div><strong>{source==='supabase'?'S3-C3A • وثائق Supabase':'مصدر Legacy مؤقت'}</strong><span>{detail}</span></div></div><div className="teacher-source-actions">{onRefresh&&<button onClick={onRefresh}><Icon name="arrow" size={15}/> تحديث</button>}{onLegacy&&<button onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}{onRestore&&<button onClick={onRestore}>إعادة Supabase</button>}</div></div>;
}
function State({ title, detail, busy, onRetry, onLegacy }: { title:string; detail:string; busy?:boolean; onRetry?:()=>void; onLegacy?:()=>void }) { return <div className="teacher-cutover-state"><div className="teacher-cutover-card">{busy?<div className="spinner"/>:<Icon name="alert" size={28}/>}<h2>{title}</h2><p>{detail}</p><div className="teacher-source-actions">{onRetry&&<button className="primary-button" onClick={onRetry}>إعادة المحاولة</button>}{onLegacy&&<button className="ghost-button" onClick={onLegacy}>Legacy مؤقتًا</button>}</div></div></div>; }
function Login({ error, onSignedIn, onLegacy }: { error:string; onSignedIn:()=>Promise<void>; onLegacy:()=>void }) {
  const [busy,setBusy]=useState(false); const [message,setMessage]=useState(error);
  async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);setBusy(true);setMessage('');try{await signInWithEmail(String(form.get('email')||''),String(form.get('password')||''));await onSignedIn();}catch(caught){setMessage(caught instanceof Error?caught.message:'تعذر تسجيل الدخول.');}finally{setBusy(false);}}
  return <div className="teacher-cutover-state"><div className="teacher-cutover-card"><span className="eyebrow">S3-C3A • Supabase</span><h2>تسجيل الدخول لسجل الوثائق</h2><form onSubmit={submit} className="teacher-login-form"><label>البريد الإلكتروني<input type="email" name="email" required/></label><label>كلمة المرور<input type="password" name="password" required/></label>{message&&<div className="inline-error"><Icon name="alert" size={16}/>{message}</div>}<button className="primary-button" disabled={busy}>{busy?'جاري التحقق...':'تسجيل الدخول'}</button></form><button className="ghost-button" onClick={onLegacy}>Legacy مؤقتًا</button></div></div>;
}
