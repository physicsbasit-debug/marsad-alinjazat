import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import {
  createCurriculumPlan,
  createCurriculumUnit,
  deleteCurriculumUnit,
  getCurriculumPlan,
  updateCurriculumPlan,
  updateCurriculumUnit,
} from '../lib/api';
import type {
  CurriculumPlanDetails,
  CurriculumPlanInput,
  CurriculumPlanRecord,
  CurriculumUnit,
  CurriculumUnitInput,
  Teacher,
} from '../types';

export function Planning({
  plans,
  planningAttention,
  teachers,
  academicYear,
  onRefresh,
  initialOpenId = null,
  onInitialOpened,
}: {
  plans: CurriculumPlanRecord[];
  planningAttention: CurriculumUnit[];
  teachers: Teacher[];
  academicYear: string;
  onRefresh: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
}) {
  const [subject, setSubject] = useState('الكل');
  const [grade, setGrade] = useState('الكل');
  const [selected, setSelected] = useState<CurriculumPlanDetails | null>(null);
  const [planModal, setPlanModal] = useState(false);
  const [message, setMessage] = useState('');
  const subjects = ['الكل', ...Array.from(new Set(plans.map((plan) => plan.subject)))];
  const grades = ['الكل', ...Array.from(new Set(plans.map((plan) => plan.grade)))];
  const visible = useMemo(
    () => plans.filter((plan) => (subject === 'الكل' || plan.subject === subject) && (grade === 'الكل' || plan.grade === grade)),
    [plans, subject, grade],
  );

  async function openPlan(id: number) {
    setMessage('');
    try {
      setSelected(await getCurriculumPlan(id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر فتح الخطة.');
    }
  }

  useEffect(() => {
    if (!initialOpenId) return;
    void openPlan(initialOpenId);
    onInitialOpened?.();
  }, [initialOpenId]);

  const activePlans = plans.filter((plan) => plan.status === 'active');
  const average = activePlans.length ? Math.round(activePlans.reduce((sum, plan) => sum + plan.progressPercent, 0) / activePlans.length) : 0;
  const overdue = plans.reduce((sum, plan) => sum + plan.overdueUnitCount, 0);
  const completedUnits = plans.reduce((sum, plan) => sum + plan.completedUnitCount, 0);
  const totalUnits = plans.reduce((sum, plan) => sum + plan.unitCount, 0);

  return (
    <div className="page planning-page">
      <header className="page-header planning-header">
        <div>
          <span className="eyebrow">التخطيط والتنفيذ</span>
          <h1>التخطيط ومتابعة المنهج</h1>
          <p>الخطة، الوحدات، المسؤوليات، ونسبة الإنجاز في شاشة واحدة. التأخير يظهر هنا بدل أن يختبئ داخل ملف Excel بحسن سلوك.</p>
        </div>
        <button className="primary-button" onClick={() => setPlanModal(true)}><Icon name="plus" /> إضافة خطة</button>
      </header>

      <section className="planning-metrics">
        <PlanningMetric label="الخطط النشطة" value={activePlans.length} detail="خطة قيد التنفيذ" />
        <PlanningMetric label="متوسط التنفيذ" value={`${average}%`} detail="حسب الوحدات المسجلة" />
        <PlanningMetric label="الوحدات المكتملة" value={`${completedUnits}/${totalUnits || 0}`} detail="من إجمالي وحدات المنهج" />
        <PlanningMetric label="وحدات متأخرة" value={overdue} detail="تحتاج معالجة" danger={overdue > 0} />
      </section>

      {planningAttention.length > 0 && (
        <section className="panel planning-alert-panel">
          <div className="panel-heading"><div><span className="eyebrow danger">تأخير يحتاج قرارًا</span><h2>الوحدات المتأخرة</h2></div><span className="counter">{planningAttention.length}</span></div>
          <div className="planning-alert-list">
            {planningAttention.slice(0, 5).map((unit) => (
              <button key={unit.id} onClick={() => void openPlan(unit.planId)}>
                <span className="attention-dot late"></span>
                <div><strong>{unit.title}</strong><small>{unit.planSubject} • {unit.planGrade} • {unit.responsibleName || 'دون مسؤول'}{unit.plannedEnd ? ` • انتهت ${formatDate(unit.plannedEnd)}` : ''}</small></div>
                <strong>{unit.progressPercent}%</strong>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="toolbar modern-toolbar planning-toolbar">
        <div className="filter-row">{subjects.map((item) => <button key={item} className={`filter-chip ${subject === item ? 'active' : ''}`} onClick={() => setSubject(item)}>{item}</button>)}</div>
        <select value={grade} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setGrade(event.target.value)}>{grades.map((item) => <option key={item}>{item}</option>)}</select>
      </div>

      {message && <div className="inline-error"><Icon name="alert" size={17} />{message}</div>}

      <section className="plan-grid">
        {visible.map((plan) => <PlanCard key={plan.id} plan={plan} onOpen={() => void openPlan(plan.id)} />)}
        {!visible.length && <div className="panel planning-empty"><Icon name="planning" size={28}/><strong>لا توجد خطط مطابقة</strong><span>أضف خطة أو غيّر المرشحات الحالية.</span></div>}
      </section>

      <PlanFormModal open={planModal} teachers={teachers} academicYear={academicYear} onClose={() => setPlanModal(false)} onSaved={async () => { setPlanModal(false); await onRefresh(); }} />
      <Modal open={!!selected} onClose={() => setSelected(null)}>
        {selected && <PlanDetails plan={selected} teachers={teachers} onReload={async () => { const next = await getCurriculumPlan(selected.id); setSelected(next); await onRefresh(); }} />}
      </Modal>
    </div>
  );
}

function PlanningMetric({ label, value, detail, danger = false }: { label: string; value: string | number; detail: string; danger?: boolean }) {
  return <article className={`planning-metric ${danger ? 'danger' : ''}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function PlanCard({ plan, onOpen }: { plan: CurriculumPlanRecord; onOpen: () => void }) {
  return (
    <button className="plan-card" onClick={onOpen}>
      <div className="plan-card-top"><div><span className="eyebrow">{plan.subject} • {plan.grade}</span><h3>{plan.title}</h3><p>{plan.term} • {plan.ownerName || 'دون مسؤول محدد'}</p></div><PlanStatus status={plan.status} /></div>
      <div className="plan-card-progress"><div><span>التنفيذ</span><strong>{plan.progressPercent}%</strong></div><div className="progress-track"><span style={{ width: `${plan.progressPercent}%` }} /></div></div>
      <div className="plan-card-footer"><span><strong>{plan.completedUnitCount}</strong> مكتملة من {plan.unitCount}</span>{plan.overdueUnitCount > 0 ? <span className="plan-overdue"><Icon name="alert" size={15}/>{plan.overdueUnitCount} متأخرة</span> : <span className="plan-on-track"><Icon name="check" size={15}/>على المسار</span>}</div>
    </button>
  );
}

function PlanDetails({ plan, teachers, onReload }: { plan: CurriculumPlanDetails; teachers: Teacher[]; onReload: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [unitModal, setUnitModal] = useState<CurriculumUnit | 'new' | null>(null);
  const [message, setMessage] = useState('');
  async function removeUnit(unit: CurriculumUnit) {
    if (!window.confirm(`حذف الوحدة «${unit.title}» من الخطة؟`)) return;
    try { await deleteCurriculumUnit(plan.id, unit.id); await onReload(); } catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حذف الوحدة.'); }
  }
  return (
    <div className="plan-details">
      <div className="plan-detail-hero">
        <div><span className="eyebrow">{plan.subject} • {plan.grade} • {plan.term} • {plan.academicYear}</span><h2>{plan.title}</h2><p>{plan.ownerName || 'دون مسؤول محدد'}{plan.startDate || plan.endDate ? ` • ${plan.startDate ? formatDate(plan.startDate) : '—'} إلى ${plan.endDate ? formatDate(plan.endDate) : '—'}` : ''}</p></div>
        <div className="plan-detail-score"><strong>{plan.progressPercent}%</strong><span>تنفيذ المنهج</span></div>
      </div>
      <div className="plan-detail-actions"><button className="soft-button" onClick={() => setEditing(true)}><Icon name="edit" size={16}/> تعديل الخطة</button><button className="primary-button" onClick={() => setUnitModal('new')}><Icon name="plus" size={16}/> إضافة وحدة</button></div>
      {plan.notes && <div className="profile-callout"><div><strong>ملاحظات الخطة</strong><p>{plan.notes}</p></div></div>}
      {message && <div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}
      <section className="plan-unit-section">
        <div className="panel-heading"><div><span className="eyebrow">توزيع المنهج</span><h3>الوحدات والدروس الرئيسة</h3></div><span className="counter">{plan.units.length}</span></div>
        <div className="plan-unit-list">
          {plan.units.map((unit) => (
            <article className={`plan-unit-row ${unit.effectiveStatus === 'overdue' ? 'overdue' : ''}`} key={unit.id}>
              <span className="unit-sequence">{unit.sequence || '•'}</span>
              <div className="unit-main"><div><strong>{unit.title}</strong><small>{unit.responsibleName || 'دون مسؤول'} • {unit.plannedEnd ? `حتى ${formatDate(unit.plannedEnd)}` : 'دون موعد نهائي'}</small></div><div className="unit-progress"><span>{unit.progressPercent}%</span><div className="progress-track"><span style={{ width: `${unit.progressPercent}%` }} /></div></div>{unit.effectiveStatus === 'overdue' && unit.delayReason && <p className="delay-reason">سبب التأخير: {unit.delayReason}</p>}</div>
              <div className="unit-side"><UnitStatus unit={unit}/><div><button className="icon-button" title="تعديل" onClick={() => setUnitModal(unit)}><Icon name="edit" size={16}/></button><button className="icon-button danger" title="حذف" onClick={() => void removeUnit(unit)}><Icon name="trash" size={16}/></button></div></div>
            </article>
          ))}
          {!plan.units.length && <div className="planning-empty inline"><strong>الخطة بلا وحدات بعد</strong><span>أضف الوحدات لتبدأ نسبة الإنجاز بالحساب الفعلي.</span></div>}
        </div>
      </section>
      <section className="plan-timeline"><div className="panel-heading"><div><span className="eyebrow">السجل الزمني</span><h3>تحديثات الخطة</h3></div></div>{plan.timeline.length ? plan.timeline.slice(0, 8).map((item) => <div className="activity-row" key={item.id}><span className="activity-icon"><Icon name="planning" size={17}/></span><div><strong>{item.title}</strong><small>{item.detail} • {formatDateTime(item.created_at)}</small></div></div>) : <div className="quiet-note">لا توجد تحديثات إضافية بعد.</div>}</section>
      <PlanFormModal open={editing} teachers={teachers} academicYear={plan.academicYear} initial={plan} onClose={() => setEditing(false)} onSaved={async () => { setEditing(false); await onReload(); }} />
      <UnitFormModal open={!!unitModal} planId={plan.id} teachers={teachers} initial={unitModal === 'new' ? undefined : unitModal || undefined} nextSequence={plan.units.length ? Math.max(...plan.units.map((unit) => unit.sequence)) + 1 : 1} onClose={() => setUnitModal(null)} onSaved={async () => { setUnitModal(null); await onReload(); }} />
    </div>
  );
}

function PlanFormModal({ open, teachers, academicYear, initial, onClose, onSaved }: { open: boolean; teachers: Teacher[]; academicYear: string; initial?: CurriculumPlanRecord; onClose: () => void; onSaved: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setMessage('');
    const form = new FormData(event.currentTarget);
    const ownerRaw = String(form.get('ownerTeacherId') || '');
    const input: CurriculumPlanInput = {
      title: String(form.get('title') || ''), subject: String(form.get('subject') || ''), grade: String(form.get('grade') || ''), term: String(form.get('term') || ''), academicYear: String(form.get('academicYear') || academicYear),
      ownerTeacherId: ownerRaw ? Number(ownerRaw) : null, startDate: String(form.get('startDate') || '') || null, endDate: String(form.get('endDate') || '') || null,
      notes: String(form.get('notes') || ''), status: String(form.get('status') || 'active') as CurriculumPlanInput['status'],
    };
    try { if (initial) await updateCurriculumPlan(initial.id, input); else await createCurriculumPlan(input); await onSaved(); } catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حفظ الخطة.'); } finally { setSaving(false); }
  }
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">{initial ? 'تحديث الخطة' : 'خطة جديدة'}</span><h2>{initial ? initial.title : 'إضافة خطة منهج'}</h2><p>اربط الخطة بمادة وصف ومعلم، ثم أضف الوحدات من داخلها.</p></div><div className="form-grid"><label className="full">عنوان الخطة<input name="title" required defaultValue={initial?.title || ''} placeholder="مثال: خطة الفيزياء للفصل الأول"/></label><label>المادة<select name="subject" defaultValue={initial?.subject || 'الفيزياء'}><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label><label>الصف<select name="grade" defaultValue={initial?.grade || 'العاشر'}><option>العاشر</option><option>التاسع</option><option>الثامن</option></select></label><label>الفصل<select name="term" defaultValue={initial?.term || 'الفصل الأول'}><option>الفصل الأول</option><option>الفصل الثاني</option></select></label><label>العام الدراسي للسجل<input name="academicYear" required defaultValue={initial?.academicYear || academicYear} placeholder="2025/2026"/></label><label>المعلم المسؤول<select name="ownerTeacherId" defaultValue={initial?.ownerTeacherId || ''}><option value="">دون تحديد</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label><label>بداية الخطة<input type="date" name="startDate" defaultValue={initial?.startDate || ''}/></label><label>نهاية الخطة<input type="date" name="endDate" defaultValue={initial?.endDate || ''}/></label><label>الحالة<select name="status" defaultValue={initial?.status || 'active'}><option value="active">نشطة</option><option value="completed">مكتملة</option><option value="archived">مؤرشفة</option></select></label><label className="full">ملاحظات<textarea name="notes" rows={3} defaultValue={initial?.notes || ''}/></label></div>{message && <div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : 'حفظ الخطة'}</button></div></form></Modal>;
}

function UnitFormModal({ open, planId, teachers, initial, nextSequence, onClose, onSaved }: { open: boolean; planId: number; teachers: Teacher[]; initial?: CurriculumUnit; nextSequence: number; onClose: () => void; onSaved: () => Promise<void> }) {
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setMessage(''); const form = new FormData(event.currentTarget); const teacherRaw = String(form.get('responsibleTeacherId') || '');
    const input: CurriculumUnitInput = { title: String(form.get('title') || ''), sequence: Number(form.get('sequence') || 0), plannedStart: String(form.get('plannedStart') || '') || null, plannedEnd: String(form.get('plannedEnd') || '') || null, progressPercent: Number(form.get('progressPercent') || 0), status: String(form.get('status') || 'not_started') as CurriculumUnitInput['status'], delayReason: String(form.get('delayReason') || ''), notes: String(form.get('notes') || ''), responsibleTeacherId: teacherRaw ? Number(teacherRaw) : null };
    try { if (initial) await updateCurriculumUnit(planId, initial.id, input); else await createCurriculumUnit(planId, input); await onSaved(); } catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حفظ الوحدة.'); } finally { setSaving(false); }
  }
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">توزيع المنهج</span><h2>{initial ? 'تعديل الوحدة' : 'إضافة وحدة'}</h2><p>التقدم يحسب مباشرة في الخطة ولوحة القيادة.</p></div><div className="form-grid"><label className="full">اسم الوحدة<input name="title" required defaultValue={initial?.title || ''}/></label><label>الترتيب<input type="number" min="0" max="1000" name="sequence" defaultValue={initial?.sequence ?? nextSequence}/></label><label>المعلم المسؤول<select name="responsibleTeacherId" defaultValue={initial?.responsibleTeacherId || ''}><option value="">دون تحديد</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label><label>البداية المخططة<input type="date" name="plannedStart" defaultValue={initial?.plannedStart || ''}/></label><label>النهاية المخططة<input type="date" name="plannedEnd" defaultValue={initial?.plannedEnd || ''}/></label><label>نسبة الإنجاز<input type="number" min="0" max="100" name="progressPercent" defaultValue={initial?.progressPercent ?? 0}/></label><label>الحالة<select name="status" defaultValue={initial?.status || 'not_started'}><option value="not_started">لم تبدأ</option><option value="in_progress">جارية</option><option value="completed">مكتملة</option></select></label><label className="full">سبب التأخير إن وجد<textarea name="delayReason" rows={2} defaultValue={initial?.delayReason || ''}/></label><label className="full">ملاحظات<textarea name="notes" rows={2} defaultValue={initial?.notes || ''}/></label></div>{message && <div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : 'حفظ الوحدة'}</button></div></form></Modal>;
}

function PlanStatus({ status }: { status: CurriculumPlanRecord['status'] }) { const labels = { active: 'نشطة', completed: 'مكتملة', archived: 'مؤرشفة' }; return <span className={`plan-status ${status}`}>{labels[status]}</span>; }
function UnitStatus({ unit }: { unit: CurriculumUnit }) { const labels = { not_started: 'لم تبدأ', in_progress: 'جارية', completed: 'مكتملة', overdue: 'متأخرة' }; return <span className={`unit-status ${unit.effectiveStatus}`}>{labels[unit.effectiveStatus]}</span>; }
function formatDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }).format(new Date(value)); }
