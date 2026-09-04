import { useCallback, useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { loadTenantSessionContext, signInWithEmail, subscribeToAuthChanges } from '../lib/supabaseSession';
import type { TenantSessionContext } from '../lib/supabaseSession';
import { loadSupabaseTeachersReadSnapshot } from '../lib/supabaseTeachers';
import type { SupabaseTeachersReadSnapshot } from '../lib/supabaseTeachers';
import { createSupabaseTeacher } from '../lib/supabaseTeachersWrite';
import {
  createSupabaseTeacherCvItem,
  deleteSupabaseTeacherCvItem,
  getSupabaseTeacherProfile,
  updateSupabaseTeacherProfile,
} from '../lib/supabaseTeacherProfile';
import { Teachers } from './Teachers';
import type { TeacherProfileActions } from './Teachers';
import type {
  CreateTeacherInput,
  DocumentRecord,
  SupervisionVisitRecord,
  Teacher,
  UploadRequest,
} from '../types';

export type TeachersDataMode = 'legacy' | 'supabase';
const rawMode = (import.meta.env.VITE_TEACHERS_DATA_MODE || 'legacy').trim().toLowerCase();
export const TEACHERS_DATA_MODE: TeachersDataMode = rawMode === 'supabase' ? 'supabase' : 'legacy';

const RELATED_DATA_NOTICE = 'طلبات الملفات والوثائق والزيارات ما زالت على مصدر Legacy، لذلك لا تُخلط معرفاتها مع معلمي Supabase في هذه المرحلة.';

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

export function TeachersWorkspace({
  legacyTeachers,
  requests,
  documents,
  visits,
  academicYear,
  currentAcademicYear,
  onLegacyAddTeacher,
  onLegacyChanged,
  initialOpenId = null,
  onInitialOpened,
  onSupabaseTeacherCount,
}: {
  legacyTeachers: Teacher[];
  requests: UploadRequest[];
  documents: DocumentRecord[];
  visits: SupervisionVisitRecord[];
  academicYear: string;
  currentAcademicYear: string;
  onLegacyAddTeacher: () => void;
  onLegacyChanged: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
  onSupabaseTeacherCount?: (count: number | null) => void;
}) {
  const eligibleForSupabase = TEACHERS_DATA_MODE === 'supabase' && academicYear === currentAcademicYear;
  const [forceLegacy, setForceLegacy] = useState(false);
  const [context, setContext] = useState<TenantSessionContext | null>(null);
  const [snapshot, setSnapshot] = useState<SupabaseTeachersReadSnapshot | null>(null);
  const [loading, setLoading] = useState(eligibleForSupabase);
  const [error, setError] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  const loadSupabase = useCallback(async () => {
    if (!eligibleForSupabase) return;
    setLoading(true);
    setError('');
    try {
      const nextContext = await loadTenantSessionContext();
      if (!nextContext) {
        setContext(null);
        setSnapshot(null);
        onSupabaseTeacherCount?.(null);
        return;
      }
      if (nextContext.academicYear !== academicYear) {
        throw new Error('جلسة Supabase لا تطابق عام العمل الحالي.');
      }
      const nextSnapshot = await loadSupabaseTeachersReadSnapshot(nextContext);
      setContext(nextContext);
      setSnapshot(nextSnapshot);
      onSupabaseTeacherCount?.(nextSnapshot.teachers.length);
    } catch (caught) {
      setSnapshot(null);
      onSupabaseTeacherCount?.(null);
      setError(caught instanceof Error ? caught.message : 'تعذر تحميل معلمي Supabase.');
    } finally {
      setLoading(false);
    }
  }, [academicYear, eligibleForSupabase, onSupabaseTeacherCount]);

  useEffect(() => {
    setForceLegacy(false);
    setSnapshot(null);
    setContext(null);
    if (!eligibleForSupabase) {
      onSupabaseTeacherCount?.(null);
      return;
    }
    void loadSupabase();
    return subscribeToAuthChanges(() => { void loadSupabase(); });
  }, [academicYear, eligibleForSupabase]);

  const supabaseTeachers = useMemo(() => snapshot?.teachers.map(toTeacher) || [], [snapshot]);

  const profileActions = useMemo<TeacherProfileActions | undefined>(() => {
    if (!context) return undefined;
    return {
      loadProfile: (teacherId) => getSupabaseTeacherProfile(context, teacherId),
      updateProfile: async (teacherId, input) => {
        await updateSupabaseTeacherProfile(context, teacherId, input);
      },
      createCvItem: (teacherId, input) => createSupabaseTeacherCvItem(context, teacherId, input),
      deleteCvItem: (teacherId, itemId) => deleteSupabaseTeacherCvItem(context, teacherId, itemId),
    };
  }, [context]);

  function activateLegacy(): void {
    setForceLegacy(true);
    onSupabaseTeacherCount?.(null);
  }

  useEffect(() => {
    if (eligibleForSupabase && initialOpenId) {
      setForceLegacy(true);
      onSupabaseTeacherCount?.(null);
    }
  }, [eligibleForSupabase, initialOpenId, onSupabaseTeacherCount]);

  if (!eligibleForSupabase || forceLegacy) {
    return (
      <>
        <TeacherSourceBanner
          source="legacy"
          detail={academicYear !== currentAcademicYear
            ? 'S3-B3 يقطع العام الجاري فقط؛ العرض التاريخي يبقى على Legacy حتى مرحلة الأرشيف السحابي.'
            : 'تم تفعيل الرجوع اليدوي إلى مصدر Legacy لهذه الجلسة فقط.'}
          onRestoreSupabase={eligibleForSupabase ? () => { setForceLegacy(false); void loadSupabase(); } : undefined}
        />
        <Teachers
          teachers={legacyTeachers}
          requests={requests}
          documents={documents}
          visits={visits}
          academicYear={academicYear}
          currentAcademicYear={currentAcademicYear}
          onAddTeacher={onLegacyAddTeacher}
          onChanged={onLegacyChanged}
          initialOpenId={initialOpenId}
          onInitialOpened={onInitialOpened}
        />
      </>
    );
  }

  if (loading) {
    return <TeacherCutoverState title="جاري ربط صفحة المعلمين بـ Supabase" detail="يتم التحقق من الجلسة وRLS والعام الدراسي الحالي." busy />;
  }

  if (!context) {
    return <TeacherLoginGate error={error} onSignedIn={loadSupabase} onLegacy={activateLegacy} />;
  }

  if (error || !snapshot || !profileActions) {
    return (
      <TeacherCutoverState
        title="تعذر تشغيل مصدر Supabase للمعلمين"
        detail={error || 'لم تكتمل قراءة مجال المعلمين.'}
        onRetry={() => void loadSupabase()}
        onLegacy={activateLegacy}
      />
    );
  }

  return (
    <>
      <TeacherSourceBanner
        source="supabase"
        detail={`مصدر المعلمين: Supabase / RLS • ${snapshot.schoolName} • ${snapshot.academicYear}`}
        onLegacy={activateLegacy}
        onRefresh={() => void loadSupabase()}
      />
      <Teachers
        teachers={supabaseTeachers}
        requests={[]}
        documents={[]}
        visits={[]}
        academicYear={academicYear}
        currentAcademicYear={currentAcademicYear}
        onAddTeacher={() => setAddOpen(true)}
        onChanged={loadSupabase}
        initialOpenId={null}
        onInitialOpened={onInitialOpened}
        profileActions={profileActions}
        relatedDataNotice={RELATED_DATA_NOTICE}
      />
      <SupabaseTeacherModal
        open={addOpen}
        context={context}
        onClose={() => setAddOpen(false)}
        onCreated={async () => {
          setAddOpen(false);
          await loadSupabase();
        }}
      />
    </>
  );
}

function TeacherSourceBanner({
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
        <div><strong>{source === 'supabase' ? 'S3-B3 • تشغيل Supabase' : 'مصدر Legacy مؤقت'}</strong><span>{detail}</span></div>
      </div>
      <div className="teacher-source-actions">
        {onRefresh && <button type="button" onClick={onRefresh}><Icon name="arrow" size={15} /> تحديث</button>}
        {onLegacy && <button type="button" onClick={onLegacy}>الرجوع المؤقت إلى Legacy</button>}
        {onRestoreSupabase && <button type="button" onClick={onRestoreSupabase}>إعادة محاولة Supabase</button>}
      </div>
    </div>
  );
}

function TeacherLoginGate({ error, onSignedIn, onLegacy }: { error: string; onSignedIn: () => Promise<void>; onLegacy: () => void }) {
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
        <span className="eyebrow">S3-B3 • Supabase</span>
        <h2>تسجيل الدخول لتشغيل صفحة المعلمين</h2>
        <p>هذه الصفحة انتقلت إلى Supabase للعام الجاري. بقية وحدات المرصد ما زالت تعمل بمصدرها السابق.</p>
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

function TeacherCutoverState({ title, detail, busy, onRetry, onLegacy }: { title: string; detail: string; busy?: boolean; onRetry?: () => void; onLegacy?: () => void }) {
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

function SupabaseTeacherModal({ open, context, onClose, onCreated }: { open: boolean; context: TenantSessionContext; onClose: () => void; onCreated: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: CreateTeacherInput = {
      academicYear: context.academicYear,
      name: String(form.get('name') || ''),
      subject: String(form.get('subject') || ''),
      specialization: String(form.get('specialization') || ''),
      qualification: String(form.get('qualification') || ''),
      experienceYears: Number(form.get('experienceYears') || 0),
      workload: Number(form.get('workload') || 0),
      email: String(form.get('email') || ''),
      phone: String(form.get('phone') || ''),
    };
    setSaving(true);
    setMessage('');
    try {
      await createSupabaseTeacher(context, payload);
      formElement.reset();
      await onCreated();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'تعذر إضافة المعلم في Supabase.');
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal open={open} onClose={onClose}>
      <form className="request-form" onSubmit={submit}>
        <div className="modal-heading"><span className="eyebrow">Supabase / RLS</span><h2>إضافة معلم إلى عام العمل</h2><p>يحفظ المعلم داخل مدرسة الجلسة الحالية ويرتبط بالعام {context.academicYear} عبر المسار الذري المعتمد.</p></div>
        <div className="form-grid">
          <label>العام الدراسي<input required readOnly value={context.academicYear} dir="ltr" /></label>
          <label className="full">اسم المعلم<input name="name" required placeholder="الاسم الرباعي" /></label>
          <label>المادة<select name="subject"><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label>
          <label>التخصص<input name="specialization" placeholder="مثال: فيزياء" /></label>
          <label className="full">المؤهل<input name="qualification" placeholder="مثال: بكالوريوس تربية" /></label>
          <label>سنوات الخبرة<input type="number" min="0" max="60" name="experienceYears" defaultValue="0" /></label>
          <label>النصاب<input type="number" min="0" max="40" name="workload" defaultValue="0" /></label>
          <label>البريد<input type="email" name="email" placeholder="name@example.edu" /></label>
          <label>الهاتف<input name="phone" placeholder="اختياري" /></label>
        </div>
        {message && <div className="inline-error"><Icon name="alert" size={17} />{message}</div>}
        <div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : 'إضافة المعلم'}</button></div>
      </form>
    </Modal>
  );
}
