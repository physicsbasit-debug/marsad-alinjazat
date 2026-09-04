import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '../components/Icon';
import { loadTenantSessionContext, signInWithEmail, subscribeToAuthChanges } from '../lib/supabaseSession';
import type { TenantSessionContext } from '../lib/supabaseSession';
import { loadSupabaseTeachersReadSnapshot } from '../lib/supabaseTeachers';
import type { SupabaseTeachersReadSnapshot } from '../lib/supabaseTeachers';
import {
  createSupabaseSupervisionAction,
  createSupabaseSupervisionVisit,
  deleteSupabaseSupervisionAction,
  getSupabaseSupervisionVisit,
  loadSupabaseSupervisionSnapshot,
  updateSupabaseSupervisionAction,
  updateSupabaseSupervisionVisit,
} from '../lib/supabaseSupervision';
import type { SupabaseSupervisionSnapshot } from '../lib/supabaseSupervision';
import { Supervision, SupervisionVisitModal } from './Supervision';
import type { SupervisionDataActions } from './Supervision';
import type { SupervisionVisitRecord, Teacher } from '../types';

export type SupervisionDataMode = 'legacy' | 'supabase';
const rawMode = (import.meta.env.VITE_SUPERVISION_DATA_MODE || 'legacy').trim().toLowerCase();
export const SUPERVISION_DATA_MODE: SupervisionDataMode = rawMode === 'supabase' ? 'supabase' : 'legacy';

function toTeacher(record: SupabaseTeachersReadSnapshot['teachers'][number]): Teacher {
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

function canReadSupervision(context: TenantSessionContext): boolean {
  return context.role === 'owner' || context.role === 'admin' || context.role === 'lead_teacher';
}

function canManageSupervision(context: TenantSessionContext): boolean {
  return context.role === 'owner' || context.role === 'admin';
}

export function SupervisionWorkspace({
  legacyVisits,
  legacyAttention,
  legacyTeachers,
  academicYear,
  currentAcademicYear,
  onLegacyAddVisit,
  onLegacyRefresh,
  initialOpenId = null,
  onInitialOpened,
  createSignal = 0,
}: {
  legacyVisits: SupervisionVisitRecord[];
  legacyAttention: SupervisionVisitRecord[];
  legacyTeachers: Teacher[];
  academicYear: string;
  currentAcademicYear: string;
  onLegacyAddVisit: () => void;
  onLegacyRefresh: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
  createSignal?: number;
}) {
  const eligibleForSupabase = SUPERVISION_DATA_MODE === 'supabase' && academicYear === currentAcademicYear;
  const [forceLegacy, setForceLegacy] = useState(false);
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [teachersSnapshot, setTeachersSnapshot] = useState<SupabaseTeachersReadSnapshot | null>(null);
  const [snapshot, setSnapshot] = useState<SupabaseSupervisionSnapshot | null>(null);
  const [loading, setLoading] = useState(eligibleForSupabase);
  const [error, setError] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const handledCreateSignal = useRef(0);

  const loadSupabase = useCallback(async () => {
    if (!eligibleForSupabase) return;
    setLoading(true);
    setError('');
    try {
      const nextContext = await loadTenantSessionContext();
      if (!nextContext) {
        setContext(null);
        setTeachersSnapshot(null);
        setSnapshot(null);
        return;
      }
      if (nextContext.academicYear !== academicYear) {
        throw new Error('جلسة Supabase لا تطابق عام العمل الحالي.');
      }
      setContext(nextContext);
      if (!canReadSupervision(nextContext)) {
        throw new Error('واجهة الإشراف السحابية في هذه المرحلة متاحة للإدارة والمعلم الأول للقراءة، وللإدارة فقط للتعديل.');
      }
      const nextTeachers = await loadSupabaseTeachersReadSnapshot(nextContext);
      const nextSnapshot = await loadSupabaseSupervisionSnapshot(nextContext, nextTeachers);
      setTeachersSnapshot(nextTeachers);
      setSnapshot(nextSnapshot);
    } catch (caught) {
      setTeachersSnapshot(null);
      setSnapshot(null);
      setError(caught instanceof Error ? caught.message : 'تعذر تشغيل الإشراف من Supabase.');
    } finally {
      setLoading(false);
    }
  }, [academicYear, eligibleForSupabase]);

  useEffect(() => {
    setForceLegacy(false);
    setContext(null);
    setTeachersSnapshot(null);
    setSnapshot(null);
    setAddOpen(false);
    handledCreateSignal.current = 0;
    if (!eligibleForSupabase) return;
    void loadSupabase();
    return subscribeToAuthChanges(() => { void loadSupabase(); });
  }, [academicYear, eligibleForSupabase, loadSupabase]);

  useEffect(() => {
    if (eligibleForSupabase && initialOpenId) setForceLegacy(true);
  }, [eligibleForSupabase, initialOpenId]);

  useEffect(() => {
    if (!createSignal || createSignal === handledCreateSignal.current) return;
    if (!eligibleForSupabase || forceLegacy) {
      handledCreateSignal.current = createSignal;
      onLegacyAddVisit();
      return;
    }
    if (loading || !context) return;
    handledCreateSignal.current = createSignal;
    if (canManageSupervision(context)) setAddOpen(true);
    else setError('صلاحية تسجيل الزيارات متاحة لمالك النظام أو الإدارة فقط.');
  }, [context, createSignal, eligibleForSupabase, forceLegacy, loading, onLegacyAddVisit]);

  const supabaseTeachers = useMemo(() => teachersSnapshot?.teachers.map(toTeacher) || [], [teachersSnapshot]);

  const dataActions = useMemo<SupervisionDataActions | undefined>(() => {
    if (!context || !teachersSnapshot) return undefined;
    return {
      getVisit: (visitId) => getSupabaseSupervisionVisit(context, teachersSnapshot, visitId),
      updateVisit: (visitId, input) => updateSupabaseSupervisionVisit(context, visitId, input),
      createAction: (visitId, input) => createSupabaseSupervisionAction(context, visitId, input),
      updateAction: (visitId, actionId, input) => updateSupabaseSupervisionAction(context, visitId, actionId, input),
      deleteAction: (visitId, actionId) => deleteSupabaseSupervisionAction(context, visitId, actionId),
    };
  }, [context, teachersSnapshot]);

  if (!eligibleForSupabase || forceLegacy) {
    return (
      <>
        <SupervisionSourceBanner
          source="legacy"
          detail={academicYear !== currentAcademicYear
            ? 'S3-C2 يحول العام الجاري فقط؛ السجل التاريخي يبقى على Legacy في هذه المرحلة.'
            : 'تم تفعيل الرجوع اليدوي إلى Legacy لهذه الجلسة فقط.'}
          onRestoreSupabase={eligibleForSupabase ? () => { setForceLegacy(false); void loadSupabase(); } : undefined}
        />
        <Supervision
          visits={legacyVisits}
          supervisionAttention={legacyAttention}
          teachers={legacyTeachers}
          onAddVisit={onLegacyAddVisit}
          onRefresh={onLegacyRefresh}
          initialOpenId={initialOpenId}
          onInitialOpened={onInitialOpened}
        />
      </>
    );
  }

  if (loading) {
    return <SupervisionCutoverState title="جاري تشغيل الإشراف من Supabase" detail="يتم التحقق من الجلسة وRLS ومعلمي عام العمل." busy />;
  }

  if (!context) {
    return <SupervisionLoginGate error={error} onSignedIn={loadSupabase} onLegacy={() => setForceLegacy(true)} />;
  }

  if (error || !teachersSnapshot || !snapshot || !dataActions) {
    return (
      <SupervisionCutoverState
        title="تعذر تشغيل مصدر Supabase للإشراف"
        detail={error || 'لم تكتمل قراءة الزيارات الإشرافية.'}
        onRetry={() => void loadSupabase()}
        onLegacy={() => setForceLegacy(true)}
      />
    );
  }

  const canManage = canManageSupervision(context);
  return (
    <>
      <SupervisionSourceBanner
        source="supabase"
        detail={`الإشراف: Supabase / RLS • ${context.schoolName} • ${context.academicYear} • الزيارات ${snapshot.visits.length} • إجراءات المتابعة ${snapshot.actionRowsInScope}`}
        onLegacy={() => setForceLegacy(true)}
        onRefresh={() => void loadSupabase()}
      />
      <Supervision
        visits={snapshot.visits}
        supervisionAttention={snapshot.attention}
        teachers={supabaseTeachers}
        onAddVisit={() => setAddOpen(true)}
        onRefresh={loadSupabase}
        initialOpenId={null}
        onInitialOpened={onInitialOpened}
        dataActions={dataActions}
        canManage={canManage}
        sourceNotice={canManage
          ? 'الزيارات وإجراءات المتابعة في هذه الصفحة تُقرأ وتُحفظ في Supabase. بقية مجالات المرصد ما زالت تنتقل على مراحل.'
          : 'عرض Supabase للزيارات متاح لهذا الدور، بينما التعديل والإجراءات الجديدة محصورة بالإدارة.'}
      />
      {canManage && (
        <SupervisionVisitModal
          open={addOpen}
          teachers={supabaseTeachers}
          academicYear={context.academicYear}
          onClose={() => setAddOpen(false)}
          createVisit={(input) => createSupabaseSupervisionVisit(context, input)}
          onCreated={async () => {
            setAddOpen(false);
            await loadSupabase();
          }}
        />
      )}
    </>
  );
}

function SupervisionSourceBanner({
  source,
  detail,
  onLegacy,
  onRestoreSupabase,
  onRefresh,
}: {
  source: 'supabase' | 'legacy';
  detail: string;
  onLegacy?: () => void;
  onRestoreSupabase?: () => void;
  onRefresh?: () => void;
}) {
  return (
    <div className={`teacher-source-banner ${source}`}>
      <div>
        <span className="teacher-source-dot" />
        <div><strong>{source === 'supabase' ? 'S3-C2 • تشغيل الإشراف عبر Supabase' : 'مصدر الإشراف Legacy مؤقت'}</strong><span>{detail}</span></div>
      </div>
      <div className="teacher-source-actions">
        {onRefresh && <button type="button" onClick={onRefresh}><Icon name="arrow" size={15} /> تحديث</button>}
        {onLegacy && <button type="button" onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}
        {onRestoreSupabase && <button type="button" onClick={onRestoreSupabase}>إعادة محاولة Supabase</button>}
      </div>
    </div>
  );
}

function SupervisionLoginGate({ error, onSignedIn, onLegacy }: { error: string; onSignedIn: () => Promise<void>; onLegacy: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(error);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setMessage('');
    try {
      await signInWithEmail(String(form.get('email') || ''), String(form.get('password') || ''));
      await onSignedIn();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'تعذر تسجيل الدخول.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="teacher-cutover-state">
      <div className="teacher-cutover-card">
        <span className="eyebrow">S3-C2 • Supabase</span>
        <h2>تسجيل الدخول لتشغيل الإشراف</h2>
        <p>العام الجاري للزيارات الإشرافية يعمل من Supabase، مع بقاء الرجوع المؤقت إلى Legacy متاحًا أثناء الانتقال.</p>
        <form onSubmit={submit} className="teacher-login-form">
          <label>البريد الإلكتروني<input type="email" name="email" autoComplete="email" required /></label>
          <label>كلمة المرور<input type="password" name="password" autoComplete="current-password" required /></label>
          {message && <div className="inline-error"><Icon name="alert" size={16} />{message}</div>}
          <button className="primary-button" disabled={busy}>{busy ? 'جاري التحقق...' : 'تسجيل الدخول'}</button>
        </form>
        <button type="button" className="ghost-button" onClick={onLegacy}>استخدام مصدر Legacy مؤقتًا</button>
      </div>
    </div>
  );
}

function SupervisionCutoverState({ title, detail, busy, onRetry, onLegacy }: { title: string; detail: string; busy?: boolean; onRetry?: () => void; onLegacy?: () => void }) {
  return (
    <div className="teacher-cutover-state">
      <div className="teacher-cutover-card">
        {busy ? <div className="spinner" /> : <Icon name="alert" size={28} />}
        <h2>{title}</h2><p>{detail}</p>
        <div className="teacher-source-actions">
          {onRetry && <button type="button" className="primary-button" onClick={onRetry}>إعادة المحاولة</button>}
          {onLegacy && <button type="button" className="ghost-button" onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}
        </div>
      </div>
    </div>
  );
}
