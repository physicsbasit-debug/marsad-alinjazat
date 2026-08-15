import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import {
  createSupervisionAction,
  createSupervisionVisit,
  deleteSupervisionAction,
  getSupervisionVisit,
  updateSupervisionAction,
  updateSupervisionVisit,
} from '../lib/api';
import type {
  SupervisionAction,
  SupervisionActionBaseStatus,
  SupervisionActionInput,
  SupervisionVisitDetails,
  SupervisionVisitInput,
  SupervisionVisitRecord,
  SupervisionVisitStatus,
  Teacher,
} from '../types';

export function Supervision({
  visits,
  supervisionAttention,
  teachers,
  onAddVisit,
  onRefresh,
  initialOpenId = null,
  onInitialOpened,
}: {
  visits: SupervisionVisitRecord[];
  supervisionAttention: SupervisionVisitRecord[];
  teachers: Teacher[];
  onAddVisit: () => void;
  onRefresh: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
}) {
  const [subject, setSubject] = useState('الكل');
  const [status, setStatus] = useState('الكل');
  const [selected, setSelected] = useState<SupervisionVisitDetails | null>(null);
  const [message, setMessage] = useState('');
  const subjects = ['الكل', ...Array.from(new Set(visits.map((visit) => visit.teacherSubject || '').filter(Boolean)))];
  const visible = useMemo(
    () => visits.filter((visit) =>
      (subject === 'الكل' || visit.teacherSubject === subject)
      && (status === 'الكل' || visit.status === status || (status === 'overdue' && visit.effectiveStatus === 'overdue'))),
    [visits, subject, status],
  );

  async function openVisit(id: number) {
    setMessage('');
    try {
      setSelected(await getSupervisionVisit(id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر فتح الزيارة.');
    }
  }

  useEffect(() => {
    if (!initialOpenId) return;
    void openVisit(initialOpenId);
    onInitialOpened?.();
  }, [initialOpenId]);

  const executed = visits.filter((visit) => visit.status !== 'planned').length;
  const overdue = visits.filter((visit) => visit.effectiveStatus === 'overdue').length;
  const followupVisits = visits.filter((visit) => ['needs_followup', 'closed'].includes(visit.status));
  const closureRate = followupVisits.length ? Math.round(100 * followupVisits.filter((visit) => visit.status === 'closed').length / followupVisits.length) : 0;

  return (
    <div className="page supervision-page">
      <header className="page-header supervision-header">
        <div>
          <span className="eyebrow">الإشراف الفني</span>
          <h1>الزيارات والمتابعة المهنية</h1>
          <p>زيارة صفية واضحة، توصية قابلة للمتابعة، وأثر محفوظ في ملف المعلم بدل ملاحظات تتبخر بعد نهاية الحصة.</p>
        </div>
        <button className="primary-button" onClick={onAddVisit}><Icon name="plus" /> تسجيل زيارة</button>
      </header>

      <section className="supervision-metrics">
        <SupervisionMetric label="إجمالي الزيارات" value={visits.length} detail="ضمن العام الدراسي" />
        <SupervisionMetric label="زيارات منفذة" value={executed} detail="منفذة أو في المتابعة" />
        <SupervisionMetric label="متأخرة" value={overdue} detail="زيارة أو متابعة فات موعدها" danger={overdue > 0} />
        <SupervisionMetric label="إغلاق المتابعات" value={`${closureRate}%`} detail="من الزيارات التي احتاجت متابعة" />
      </section>

      {supervisionAttention.length > 0 && (
        <section className="panel supervision-attention-panel">
          <div className="panel-heading"><div><span className="eyebrow danger">يحتاج إجراءً</span><h2>زيارات ومتابعات متأخرة</h2></div><span className="counter">{supervisionAttention.length}</span></div>
          <div className="supervision-attention-list">
            {supervisionAttention.slice(0, 5).map((visit) => (
              <button key={visit.id} onClick={() => void openVisit(visit.id)}>
                <span className="attention-dot late"></span>
                <div>
                  <strong>{visit.teacherName}</strong>
                  <small>{visit.visitType} • {visit.grade || 'دون صف'} • {visit.status === 'needs_followup' && visit.followupDate ? `متابعة ${formatDate(visit.followupDate)}` : `زيارة ${formatDate(visit.visitDate)}`}</small>
                </div>
                <Icon name="supervision" size={18} />
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="toolbar modern-toolbar supervision-toolbar">
        <div className="filter-row">{subjects.map((item) => <button key={item} className={`filter-chip ${subject === item ? 'active' : ''}`} onClick={() => setSubject(item)}>{item}</button>)}</div>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="الكل">كل الحالات</option>
          <option value="planned">مخططة</option>
          <option value="completed">منفذة</option>
          <option value="needs_followup">تحتاج متابعة</option>
          <option value="closed">مغلقة</option>
          <option value="overdue">متأخرة</option>
        </select>
      </div>

      {message && <div className="inline-error"><Icon name="alert" size={17} />{message}</div>}

      <section className="visit-grid">
        {visible.map((visit) => <VisitCard key={visit.id} visit={visit} onOpen={() => void openVisit(visit.id)} />)}
        {!visible.length && <div className="panel supervision-empty"><Icon name="supervision" size={30}/><strong>لا توجد زيارات مطابقة</strong><span>سجّل زيارة جديدة أو غيّر المرشحات الحالية.</span></div>}
      </section>

      <Modal open={!!selected} onClose={() => setSelected(null)}>
        {selected && <VisitDetails visit={selected} teachers={teachers} onReload={async () => { const next = await getSupervisionVisit(selected.id); setSelected(next); await onRefresh(); }} />}
      </Modal>
    </div>
  );
}

function SupervisionMetric({ label, value, detail, danger = false }: { label: string; value: string | number; detail: string; danger?: boolean }) {
  return <article className={`supervision-metric ${danger ? 'danger' : ''}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function VisitCard({ visit, onOpen }: { visit: SupervisionVisitRecord; onOpen: () => void }) {
  return (
    <button className={`visit-card ${visit.effectiveStatus === 'overdue' ? 'overdue' : ''}`} onClick={onOpen}>
      <div className="visit-card-top">
        <div className="avatar visit-avatar">{visit.teacherName[0]}</div>
        <div><span className="eyebrow">{visit.teacherSubject || 'المادة'} • {visit.grade || 'دون صف'}</span><h3>{visit.teacherName}</h3><p>{visit.visitType} • {formatDate(visit.visitDate)}</p></div>
        <VisitStatus visit={visit} />
      </div>
      <div className="visit-card-body">
        <div><span>الدرس</span><strong>{visit.lessonTitle || 'لم يحدد بعد'}</strong></div>
        <div><span>الحصة</span><strong>{visit.periodLabel || '—'}</strong></div>
      </div>
      <div className="visit-card-footer">
        <span>{visit.actionCount ? `${visit.completedActionCount}/${visit.actionCount} إجراءات مكتملة` : 'لا توجد إجراءات متابعة'}</span>
        {visit.openActionCount > 0 ? <strong className="visit-open-followup">{visit.openActionCount} مفتوحة</strong> : <strong className="visit-clear">المتابعة مستقرة</strong>}
      </div>
    </button>
  );
}

function VisitDetails({ visit, teachers, onReload }: { visit: SupervisionVisitDetails; teachers: Teacher[]; onReload: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [actionEditing, setActionEditing] = useState<SupervisionAction | 'new' | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function saveVisit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = visitPayloadFromForm(form);
    setBusy(true); setMessage('');
    try { await updateSupervisionVisit(visit.id, payload); setEditing(false); await onReload(); setMessage('تم تحديث الزيارة.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر تحديث الزيارة.'); }
    finally { setBusy(false); }
  }

  async function saveAction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const responsibleRaw = String(form.get('responsibleTeacherId') || '').trim();
    const dueRaw = String(form.get('dueDate') || '').trim();
    const payload: SupervisionActionInput = {
      title: String(form.get('title') || ''),
      responsibleTeacherId: responsibleRaw ? Number(responsibleRaw) : null,
      dueDate: dueRaw || null,
      status: String(form.get('status') || 'new') as SupervisionActionBaseStatus,
      notes: String(form.get('notes') || ''),
    };
    setBusy(true); setMessage('');
    try {
      if (actionEditing === 'new') await createSupervisionAction(visit.id, payload);
      else if (actionEditing) await updateSupervisionAction(visit.id, actionEditing.id, payload);
      setActionEditing(null); await onReload(); setMessage('تم حفظ إجراء المتابعة.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حفظ الإجراء.'); }
    finally { setBusy(false); }
  }

  async function removeAction(action: SupervisionAction) {
    if (!window.confirm(`حذف إجراء «${action.title}»؟`)) return;
    setBusy(true); setMessage('');
    try { await deleteSupervisionAction(visit.id, action.id); await onReload(); setMessage('تم حذف إجراء المتابعة.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حذف الإجراء.'); }
    finally { setBusy(false); }
  }

  return (
    <div className="supervision-detail">
      <div className="supervision-detail-hero">
        <div className="avatar hero-avatar">{visit.teacherName[0]}</div>
        <div><span className="eyebrow">{visit.visitType}</span><h2>{visit.teacherName}</h2><p>{visit.teacherSubject} • {visit.grade || 'دون صف'} • {formatDate(visit.visitDate)}</p></div>
        <div className="supervision-detail-side"><VisitStatus visit={visit}/><span className={`report-readiness ${visit.reportReady ? 'ready' : ''}`}><Icon name={visit.reportReady ? 'check' : 'clock'} size={14}/>{visit.reportReady ? 'جاهزة للتقرير' : 'التوثيق غير مكتمل'}</span></div>
      </div>

      <div className="supervision-detail-actions"><button className="soft-button" onClick={() => setEditing(!editing)}><Icon name="edit" size={16}/>{editing ? 'إغلاق التعديل' : 'تحديث الزيارة'}</button><button className="primary-button" onClick={() => setActionEditing('new')}><Icon name="plus" size={16}/> إجراء متابعة</button></div>
      {message && <div className={`profile-message ${message.includes('تعذر') || message.includes('معاينة') ? 'warning' : ''}`}>{message}</div>}

      {editing ? <VisitForm teachers={teachers} visit={visit} busy={busy} onSubmit={saveVisit} submitLabel="حفظ تحديث الزيارة" /> : (
        <>
          <section className="supervision-info-grid">
            <InfoBox label="الدرس" value={visit.lessonTitle || 'غير مسجل'} />
            <InfoBox label="الحصة" value={visit.periodLabel || 'غير مسجلة'} />
            <InfoBox label="الصف" value={visit.grade || 'غير مسجل'} />
            <InfoBox label="موعد المتابعة" value={visit.followupDate ? formatDate(visit.followupDate) : 'لا توجد متابعة مجدولة'} />
          </section>
          <section className="supervision-narrative-grid">
            <Narrative title="أهداف الزيارة" text={visit.objectives} />
            <Narrative title="جوانب القوة" text={visit.strengths} tone="positive" />
            <Narrative title="جوانب التطوير" text={visit.developmentAreas} tone="development" />
            <Narrative title="التوصيات والإجراءات" text={visit.recommendations} tone="recommendation" />
          </section>
          {visit.followupNotes && <div className="supervision-followup-note"><Icon name="clock" size={18}/><div><strong>ملاحظات المتابعة</strong><p>{visit.followupNotes}</p></div></div>}
        </>
      )}

      {actionEditing && <ActionForm key={actionEditing === 'new' ? 'new' : actionEditing.id} action={actionEditing === 'new' ? null : actionEditing} teachers={teachers} busy={busy} onSubmit={saveAction} onCancel={() => setActionEditing(null)} />}

      <section className="supervision-actions-section">
        <div className="panel-heading"><div><span className="eyebrow">متابعة التوصيات</span><h3>إجراءات قابلة للإغلاق</h3></div><span className="counter">{visit.actions.length}</span></div>
        <div className="supervision-action-list">
          {visit.actions.map((action) => (
            <article key={action.id} className={`supervision-action-row ${action.status === 'overdue' ? 'overdue' : ''}`}>
              <span className={`action-state-dot ${action.status}`}></span>
              <div><strong>{action.title}</strong><small>{action.responsibleName || 'دون مسؤول'}{action.dueDate ? ` • حتى ${formatDate(action.dueDate)}` : ''}</small>{action.notes && <p>{action.notes}</p>}</div>
              <ActionStatus action={action}/>
              <div className="row-actions"><button className="icon-button" onClick={() => setActionEditing(action)} title="تعديل"><Icon name="edit" size={16}/></button><button className="icon-button danger" onClick={() => void removeAction(action)} title="حذف"><Icon name="trash" size={16}/></button></div>
            </article>
          ))}
          {!visit.actions.length && <div className="empty-state-compact">لا توجد إجراءات متابعة مسجلة لهذه الزيارة.</div>}
        </div>
      </section>

      <section className="supervision-timeline">
        <div className="panel-heading"><div><span className="eyebrow">السجل الزمني</span><h3>تطور الزيارة والمتابعة</h3></div></div>
        {visit.timeline.length ? visit.timeline.slice(0, 10).map((item) => <div className="timeline-row" key={item.id}><span></span><div><strong>{item.title}</strong><small>{item.detail || 'تحديث إشرافي'} • {formatDateTime(item.created_at)}</small></div></div>) : <div className="empty-state-compact">لا توجد تحديثات إضافية بعد.</div>}
      </section>
    </div>
  );
}

export function SupervisionVisitModal({ open, teachers, onClose, onCreated }: { open: boolean; teachers: Teacher[]; onClose: () => void; onCreated: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true); setMessage('');
    try { await createSupervisionVisit(visitPayloadFromForm(new FormData(formElement))); formElement.reset(); await onCreated(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر إنشاء الزيارة.'); }
    finally { setBusy(false); }
  }
  return <Modal open={open} onClose={onClose}>{<div className="supervision-create"><div className="modal-heading"><span className="eyebrow">الإشراف الفني</span><h2>تسجيل زيارة</h2><p>يمكن إنشاؤها كزيارة مخططة ثم استكمال التوثيق بعد التنفيذ.</p></div>{message && <div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<VisitForm teachers={teachers} busy={busy} onSubmit={submit} submitLabel="حفظ الزيارة" /></div>}</Modal>;
}

function VisitForm({ teachers, visit, busy, onSubmit, submitLabel }: { teachers: Teacher[]; visit?: SupervisionVisitRecord; busy: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; submitLabel: string }) {
  return (
    <form className="supervision-form" onSubmit={onSubmit}>
      <div className="form-grid">
        <label className="full">المعلم<select name="teacherId" required defaultValue={visit?.teacherId || ''}><option value="" disabled>اختر المعلم</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name} • {teacher.subject}</option>)}</select></label>
        <label>نوع الزيارة<select name="visitType" defaultValue={visit?.visitType || 'زيارة صفية'}><option>زيارة صفية</option><option>زيارة تطويرية</option><option>زيارة متابعة</option><option>تبادل مهني</option></select></label>
        <label>الحالة<select name="status" defaultValue={visit?.status || 'planned'}><option value="planned">مخططة</option><option value="completed">منفذة</option><option value="needs_followup">تحتاج متابعة</option><option value="closed">مغلقة</option></select></label>
        <label>تاريخ الزيارة<input name="visitDate" type="date" required defaultValue={visit?.visitDate || ''}/></label>
        <label>موعد المتابعة<input name="followupDate" type="date" defaultValue={visit?.followupDate || ''}/></label>
        <label>الصف<input name="grade" defaultValue={visit?.grade || ''} placeholder="العاشر"/></label>
        <label>الحصة<input name="periodLabel" defaultValue={visit?.periodLabel || ''} placeholder="الحصة الثالثة"/></label>
        <label className="full">عنوان الدرس<input name="lessonTitle" defaultValue={visit?.lessonTitle || ''} placeholder="عنوان الدرس أو المحور المشاهد"/></label>
        <label className="full">أهداف الزيارة<textarea name="objectives" rows={3} defaultValue={visit?.objectives || ''} placeholder="ما الذي تريد ملاحظته أو دعمه في هذه الزيارة؟"/></label>
        <label className="full">جوانب القوة<textarea name="strengths" rows={3} defaultValue={visit?.strengths || ''}/></label>
        <label className="full">جوانب التطوير<textarea name="developmentAreas" rows={3} defaultValue={visit?.developmentAreas || ''}/></label>
        <label className="full">التوصيات والإجراءات<textarea name="recommendations" rows={3} defaultValue={visit?.recommendations || ''}/></label>
        <label className="full">ملاحظات المتابعة<textarea name="followupNotes" rows={2} defaultValue={visit?.followupNotes || ''}/></label>
      </div>
      <div className="profile-form-actions"><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : submitLabel}</button></div>
    </form>
  );
}

function ActionForm({ action, teachers, busy, onSubmit, onCancel }: { action: SupervisionAction | null; teachers: Teacher[]; busy: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  return (
    <form className="supervision-action-form" onSubmit={onSubmit}>
      <div className="profile-section-head compact"><div><span className="eyebrow">إجراء متابعة</span><h3>{action ? 'تحديث الإجراء' : 'إضافة إجراء جديد'}</h3></div><button type="button" className="text-button" onClick={onCancel}>إلغاء</button></div>
      <div className="form-grid">
        <label className="full">الإجراء<input name="title" required defaultValue={action?.title || ''} placeholder="إجراء محدد وقابل للتحقق"/></label>
        <label>المسؤول<select name="responsibleTeacherId" defaultValue={action?.responsibleTeacherId || ''}><option value="">دون مسؤول محدد</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label>
        <label>الموعد<input type="date" name="dueDate" defaultValue={action?.dueDate || ''}/></label>
        <label>الحالة<select name="status" defaultValue={action?.baseStatus || 'new'}><option value="new">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="completed">مكتمل</option><option value="cancelled">ملغي</option></select></label>
        <label className="full">ملاحظات<textarea name="notes" rows={2} defaultValue={action?.notes || ''}/></label>
      </div>
      <div className="profile-form-actions"><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : 'حفظ الإجراء'}</button></div>
    </form>
  );
}

function visitPayloadFromForm(form: FormData): SupervisionVisitInput {
  const followupRaw = String(form.get('followupDate') || '').trim();
  return {
    teacherId: Number(form.get('teacherId')),
    visitType: String(form.get('visitType') || 'زيارة صفية'),
    visitDate: String(form.get('visitDate') || ''),
    periodLabel: String(form.get('periodLabel') || ''),
    grade: String(form.get('grade') || ''),
    lessonTitle: String(form.get('lessonTitle') || ''),
    objectives: String(form.get('objectives') || ''),
    strengths: String(form.get('strengths') || ''),
    developmentAreas: String(form.get('developmentAreas') || ''),
    recommendations: String(form.get('recommendations') || ''),
    followupDate: followupRaw || null,
    followupNotes: String(form.get('followupNotes') || ''),
    status: String(form.get('status') || 'planned') as SupervisionVisitStatus,
  };
}

function VisitStatus({ visit }: { visit: SupervisionVisitRecord }) {
  const labels: Record<string, string> = { planned: 'مخططة', completed: 'منفذة', needs_followup: 'تحتاج متابعة', closed: 'مغلقة', overdue: 'متأخرة' };
  return <span className={`visit-status ${visit.effectiveStatus}`}>{visit.effectiveStatus === 'overdue' && <Icon name="alert" size={13}/>} {labels[visit.effectiveStatus]}</span>;
}

function ActionStatus({ action }: { action: SupervisionAction }) {
  const labels: Record<string, string> = { new: 'جديد', in_progress: 'قيد التنفيذ', completed: 'مكتمل', cancelled: 'ملغي', overdue: 'متأخر' };
  return <span className={`status-pill ${action.status === 'completed' ? 'approved' : action.status === 'overdue' ? 'late' : 'review'}`}>{labels[action.status]}</span>;
}

function Narrative({ title, text, tone = '' }: { title: string; text?: string | null; tone?: string }) {
  return <article className={`supervision-narrative ${tone}`}><strong>{title}</strong><p>{text || 'لم تسجل بيانات في هذا القسم بعد.'}</p></article>;
}
function InfoBox({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function formatDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }).format(new Date(value)); }
