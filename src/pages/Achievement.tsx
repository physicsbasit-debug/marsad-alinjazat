import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import {
  createAchievementAction,
  createAchievementAssessment,
  deleteAchievementAction,
  deleteAchievementActionMetric,
  getAchievementAssessment,
  updateAchievementAction,
  upsertAchievementActionMetric,
  updateAchievementAssessment,
} from '../lib/api';
import type {
  AchievementAction,
  AchievementActionBaseStatus,
  AchievementActionInput,
  AchievementActionType,
  AchievementImpactMetricInput,
  AchievementImpactStatus,
  AchievementAssessmentDetails,
  AchievementAssessmentInput,
  AchievementAssessmentRecord,
  AchievementAssessmentStatus,
  Teacher,
} from '../types';

export function Achievement({
  assessments,
  achievementAttention,
  teachers,
  academicYear,
  term,
  onAddAssessment,
  onRefresh,
  initialOpenId = null,
  onInitialOpened,
}: {
  assessments: AchievementAssessmentRecord[];
  achievementAttention: AchievementAssessmentRecord[];
  teachers: Teacher[];
  academicYear: string;
  term: string;
  onAddAssessment: () => void;
  onRefresh: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
}) {
  const [subject, setSubject] = useState('الكل');
  const [status, setStatus] = useState('الكل');
  const [selected, setSelected] = useState<AchievementAssessmentDetails | null>(null);
  const [message, setMessage] = useState('');
  const subjects = ['الكل', ...Array.from(new Set(assessments.map((item) => item.subject).filter(Boolean)))];
  const visible = useMemo(
    () => assessments.filter((item) => (subject === 'الكل' || item.subject === subject) && (status === 'الكل' || item.status === status)),
    [assessments, subject, status],
  );
  const completed = assessments.filter((item) => item.status !== 'draft' && item.studentCount > 0);
  const mastery = completed.length ? Math.round(completed.reduce((sum, item) => sum + item.masteryPercent, 0) / completed.length) : 0;
  const lowMastery = completed.filter((item) => item.masteryPercent < item.masteryThresholdPct).length;
  const openActions = assessments.reduce((sum, item) => sum + item.openActionCount, 0);
  const remedialActions = assessments.reduce((sum, item) => sum + item.remedialActionCount, 0);
  const enrichmentActions = assessments.reduce((sum, item) => sum + item.enrichmentActionCount, 0);
  const measuredActions = assessments.reduce((sum, item) => sum + item.measuredActionCount, 0);
  const targetMetActions = assessments.reduce((sum, item) => sum + item.targetMetActionCount, 0);
  const unmeasuredCompleted = assessments.reduce((sum, item) => sum + item.unmeasuredCompletedActionCount, 0);
  const impactReview = assessments.reduce((sum, item) => sum + item.impactReviewActionCount, 0);

  async function openAssessment(id: number) {
    setMessage('');
    try { setSelected(await getAchievementAssessment(id)); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر فتح سجل التحصيل.'); }
  }

  useEffect(() => {
    if (!initialOpenId) return;
    void openAssessment(initialOpenId);
    onInitialOpened?.();
  }, [initialOpenId]);

  return (
    <div className="page achievement-page">
      <header className="page-header achievement-header">
        <div>
          <span className="eyebrow">التحصيل والنتائج</span>
          <h1>من النتيجة إلى الإجراء</h1>
          <p>سجل موحد للاختبارات والمؤشرات وفئات الأداء والتدخلات، مع إبقاء التحليل المتقدم لمحركات «تقارير» و«بوصلة الإتقان» بدل تكراره داخل المرصد.</p>
        </div>
        <button className="primary-button" onClick={onAddAssessment}><Icon name="plus" /> تسجيل نتيجة</button>
      </header>

      <section className="achievement-metrics">
        <AchievementMetric label="سجلات التحصيل" value={assessments.length} detail={`${academicYear} • ${term}`} />
        <AchievementMetric label="متوسط نسبة الفئة المحققة للحد" value={`${mastery}%`} detail="وفق الحد المسجل في كل تقويم" />
        <AchievementMetric label="دون الحد المسجل" value={lowMastery} detail="لا يعني معيارًا وزاريًا ما لم يكن المرجع موثقًا" danger={lowMastery > 0} />
        <AchievementMetric label="إجراءات مفتوحة" value={openActions} detail="علاجية أو إثرائية أو متابعة" danger={assessments.some((item) => item.overdueActionCount > 0)} />
      </section>

      <section className="achievement-metrics intervention-metrics">
        <AchievementMetric label="برامج علاجية" value={remedialActions} detail="مرتبطة بنتائج التحصيل" />
        <AchievementMetric label="برامج إثرائية" value={enrichmentActions} detail="مرتبطة بنتائج التحصيل" />
        <AchievementMetric label="تدخلات مقاسة" value={measuredActions} detail={measuredActions ? `${targetMetActions} حققت الهدف المسجل` : 'لا توجد نتائج قياس نهائية'} />
        <AchievementMetric label="تحتاج قرار أثر" value={unmeasuredCompleted + impactReview} detail={`${unmeasuredCompleted} مكتملة بلا قياس • ${impactReview} بلا تحسن حسابي`} danger={unmeasuredCompleted + impactReview > 0} />
      </section>

      {achievementAttention.length > 0 && (
        <section className="panel achievement-attention-panel">
          <div className="panel-heading"><div><span className="eyebrow danger">يحتاج قرارًا</span><h2>نتائج أو تدخلات تستحق المتابعة</h2></div><span className="counter">{achievementAttention.length}</span></div>
          <div className="achievement-attention-list">
            {achievementAttention.slice(0, 5).map((item) => (
              <button key={item.id} onClick={() => void openAssessment(item.id)}>
                <span className="attention-dot late"></span>
                <div><strong>{item.title}</strong><small>{item.subject} • {item.grade} • الفئة المحققة للحد {item.masteryPercent}% وفق حد مسجل {item.masteryThresholdPct}%{item.overdueActionCount ? ` • ${item.overdueActionCount} إجراء متأخر` : ''}{item.unmeasuredCompletedActionCount ? ` • ${item.unmeasuredCompletedActionCount} مكتمل بلا قياس` : ''}{item.impactReviewActionCount ? ` • ${item.impactReviewActionCount} يحتاج قرار أثر` : ''}</small></div>
                <Icon name="chart" size={18} />
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="toolbar modern-toolbar achievement-toolbar">
        <div className="filter-row">{subjects.map((item) => <button key={item} className={`filter-chip ${subject === item ? 'active' : ''}`} onClick={() => setSubject(item)}>{item}</button>)}</div>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="الكل">كل الحالات</option><option value="draft">مسودة</option><option value="recorded">مسجلة</option><option value="reviewed">مراجعة مكتملة</option>
        </select>
      </div>

      {message && <div className="inline-error"><Icon name="alert" size={17} />{message}</div>}

      <section className="achievement-grid">
        {visible.map((item) => <AssessmentCard key={item.id} assessment={item} onOpen={() => void openAssessment(item.id)} />)}
        {!visible.length && <div className="panel achievement-empty"><Icon name="chart" size={30}/><strong>لا توجد نتائج مطابقة</strong><span>سجل نتيجة جديدة أو غيّر المرشحات الحالية.</span></div>}
      </section>

      <Modal open={!!selected} onClose={() => setSelected(null)}>
        {selected && <AssessmentDetails assessment={selected} teachers={teachers} onReload={async () => { const next = await getAchievementAssessment(selected.id); setSelected(next); await onRefresh(); }} />}
      </Modal>
    </div>
  );
}

function AchievementMetric({ label, value, detail, danger = false }: { label: string; value: string | number; detail: string; danger?: boolean }) {
  return <article className={`achievement-metric ${danger ? 'danger' : ''}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function AssessmentCard({ assessment, onOpen }: { assessment: AchievementAssessmentRecord; onOpen: () => void }) {
  const classified = assessment.masteredCount + assessment.nearMasteryCount + assessment.interventionCount;
  return (
    <button className={`assessment-card ${assessment.masteryPercent < assessment.masteryThresholdPct && assessment.status !== 'draft' ? 'needs-attention' : ''}`} onClick={onOpen}>
      <div className="assessment-card-top">
        <div><span className="eyebrow">{assessment.assessmentType} • {assessment.grade}</span><h3>{assessment.title}</h3><p>{assessment.subject} • {formatDate(assessment.assessmentDate)}</p></div>
        <AssessmentStatus status={assessment.status} />
      </div>
      <div className="assessment-score-row">
        <div><span>الفئة المحققة للحد</span><strong>{assessment.masteryPercent}%</strong><small>وفق الحد المسجل {assessment.masteryThresholdPct}%</small></div>
        <div><span>المتوسط</span><strong>{assessment.averagePercent}%</strong><small>{assessment.averageScore ?? '—'} / {assessment.maxScore}</small></div>
        <div><span>الطلبة</span><strong>{assessment.studentCount}</strong><small>مصنف {classified}</small></div>
      </div>
      <PerformanceBand assessment={assessment} />
      <div className="assessment-card-footer"><span>{assessment.teacherName || 'دون معلم مسؤول'}</span>{assessment.openActionCount ? <strong className="achievement-open">{assessment.openActionCount} إجراءات مفتوحة</strong> : <strong className="achievement-clear">لا توجد متابعة مفتوحة</strong>}</div>
    </button>
  );
}

function PerformanceBand({ assessment }: { assessment: AchievementAssessmentRecord }) {
  const total = assessment.studentCount || 1;
  const mastery = 100 * assessment.masteredCount / total;
  const near = 100 * assessment.nearMasteryCount / total;
  const intervention = 100 * assessment.interventionCount / total;
  return <div className="performance-band" aria-label="توزيع فئات الأداء"><span className="mastered" style={{width:`${mastery}%`}}/><span className="near" style={{width:`${near}%`}}/><span className="intervention" style={{width:`${intervention}%`}}/></div>;
}

function AssessmentDetails({ assessment, teachers, onReload }: { assessment: AchievementAssessmentDetails; teachers: Teacher[]; onReload: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [actionEditing, setActionEditing] = useState<AchievementAction | 'new' | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function saveAssessment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setMessage('');
    try { await updateAchievementAssessment(assessment.id, assessmentPayload(form)); setEditing(false); await onReload(); setMessage('تم تحديث سجل التحصيل.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر تحديث سجل التحصيل.'); }
    finally { setBusy(false); }
  }

  async function saveAction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setMessage('');
    try {
      const payload = actionPayload(form);
      const metric = metricPayload(form);
      const saved = actionEditing === 'new'
        ? await createAchievementAction(assessment.id, payload)
        : actionEditing ? await updateAchievementAction(assessment.id, actionEditing.id, payload) : null;
      if (!saved) throw new Error('تعذر تحديد الإجراء المراد حفظه.');
      if (metric) await upsertAchievementActionMetric(assessment.id, saved.id, metric);
      else if (actionEditing !== 'new' && actionEditing?.metric) await deleteAchievementActionMetric(assessment.id, saved.id);
      setActionEditing(null); await onReload(); setMessage('تم حفظ الإجراء وبيانات قياس الأثر.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حفظ الإجراء.'); }
    finally { setBusy(false); }
  }

  async function removeAction(action: AchievementAction) {
    if (!window.confirm(`حذف الإجراء «${action.title}»؟`)) return;
    setBusy(true); setMessage('');
    try { await deleteAchievementAction(assessment.id, action.id); setActionEditing(null); await onReload(); setMessage('تم حذف الإجراء.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'تعذر حذف الإجراء.'); }
    finally { setBusy(false); }
  }

  return <div className="achievement-detail">
    <div className="achievement-detail-hero">
      <div><span className="eyebrow">{assessment.subject} • {assessment.grade}</span><h2>{assessment.title}</h2><p>{assessment.assessmentType} • {formatDate(assessment.assessmentDate)} • {assessment.teacherName || 'دون معلم مسؤول'}</p></div>
      <div className="achievement-detail-actions"><AssessmentStatus status={assessment.status}/><button className="ghost-button" onClick={() => setEditing(!editing)}><Icon name="edit" size={17}/>{editing ? 'إغلاق التعديل' : 'تعديل النتيجة'}</button></div>
    </div>

    {message && <div className={message.includes('تم ') ? 'inline-success' : 'inline-error'}>{message}</div>}

    {editing ? <AssessmentForm assessment={assessment} teachers={teachers} onSubmit={saveAssessment} busy={busy}/> : <>
      <section className="achievement-detail-metrics">
        <AchievementMetric label="الفئة المحققة للحد" value={`${assessment.masteryPercent}%`} detail={`وفق الحد المسجل ${assessment.masteryThresholdPct}%`} danger={assessment.masteryPercent < assessment.masteryThresholdPct}/>
        <AchievementMetric label="متوسط الدرجات" value={`${assessment.averagePercent}%`} detail={`${assessment.averageScore ?? '—'} من ${assessment.maxScore}`}/>
        <AchievementMetric label="أعلى / أدنى" value={`${assessment.highestScore ?? '—'} / ${assessment.lowestScore ?? '—'}`} detail="درجة فعلية"/>
        <AchievementMetric label="التحليل" value={assessment.analysisReady ? 'جاهز' : 'ناقص'} detail={assessment.analysisReady ? 'فئات الأداء مكتملة' : 'أكمل تصنيف الطلبة'} danger={!assessment.analysisReady}/>
      </section>
      <div className="mastery-reference-note"><strong>مرجع حد التصنيف:</strong> {assessment.masteryReferenceSource}{assessment.masteryReferenceYear ? ` • ${assessment.masteryReferenceYear}` : ''}{assessment.masteryReferenceNote ? <small>{assessment.masteryReferenceNote}</small> : null}</div>
      <section className="panel performance-panel"><div className="panel-heading"><div><span className="eyebrow">فئات الأداء وفق المرجع المسجل</span><h3>توزيع الطلبة</h3></div></div><PerformanceBand assessment={assessment}/><div className="performance-legend"><span><i className="mastered"/>محققو الحد <strong>{assessment.masteredCount}</strong></span><span><i className="near"/>الفئة القريبة من الحد <strong>{assessment.nearMasteryCount}</strong></span><span><i className="intervention"/>الفئة المستهدفة بالتدخل <strong>{assessment.interventionCount}</strong></span></div>{assessment.notes && <p className="achievement-notes">{assessment.notes}</p>}</section>
    </>}

    <section className="achievement-actions-section">
      <div className="section-title-row"><div><span className="eyebrow">التدخل والمتابعة</span><h3>إجراءات مرتبطة بالنتيجة</h3></div><button className="soft-button" onClick={() => setActionEditing('new')}><Icon name="plus" size={17}/>إضافة إجراء</button></div>
      <div className="achievement-actions-list">{assessment.actions.map((action) => <button key={action.id} className={`achievement-action-row ${action.status === 'overdue' ? 'overdue' : ''} ${actionNeedsImpactDecision(action) ? 'impact-review' : ''}`} onClick={() => setActionEditing(action)}><span className="action-type">{actionTypeLabel(action.actionType)}</span><div><strong>{action.title}</strong><small>{action.targetGroup || 'دون فئة مستهدفة'} • {action.responsibleName || 'دون مسؤول'}{action.dueDate ? ` • حتى ${formatDate(action.dueDate)}` : ''}</small>{action.metric ? <small className="impact-line">{action.metric.metricName}: {formatMetricValue(action.metric.baselineValue, action.metric.unit)} ← {formatMetricValue(action.metric.outcomeValue, action.metric.unit)} • {impactStatusLabel(action.metric.impactStatus)}</small> : action.baseStatus === 'completed' ? <small className="impact-line warning">مكتمل بلا مقياس أثر منظم</small> : null}</div><div className="action-row-status"><ActionStatus status={action.status}/>{action.metric && <ImpactStatus status={action.metric.impactStatus}/>}</div></button>)}{!assessment.actions.length && <div className="quiet-note">لا توجد إجراءات مرتبطة بهذه النتيجة.</div>}</div>
    </section>

    <section className="achievement-timeline"><div className="section-title-row"><div><span className="eyebrow">السجل الزمني</span><h3>تاريخ المتابعة</h3></div></div><div className="timeline-list">{assessment.timeline.map((item) => <div key={item.id}><span></span><div><strong>{item.title}</strong><small>{item.detail || ''} • {formatDateTime(item.created_at)}</small></div></div>)}</div></section>

    <Modal open={!!actionEditing} onClose={() => setActionEditing(null)} compact>
      {actionEditing && <form className="request-form" onSubmit={saveAction}><div className="modal-heading"><span className="eyebrow">إجراء تحصيلي وقياس أثر</span><h2>{actionEditing === 'new' ? 'إضافة تدخل أو متابعة' : 'تعديل الإجراء'}</h2></div><ActionFields action={actionEditing === 'new' ? null : actionEditing} teachers={teachers}/>{actionEditing !== 'new' && <button type="button" className="danger-text-button" onClick={() => void removeAction(actionEditing)} disabled={busy}><Icon name="trash" size={16}/>حذف الإجراء</button>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={() => setActionEditing(null)}>إلغاء</button><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : 'حفظ الإجراء'}</button></div></form>}
    </Modal>
  </div>;
}

export function AssessmentModal({ open, teachers, academicYear, term, onClose, onCreated }: { open: boolean; teachers: Teacher[]; academicYear: string; term: string; onClose: () => void; onCreated: () => Promise<void> }) {
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) { event.preventDefault(); const formElement=event.currentTarget; const form=new FormData(formElement); setSaving(true); setMessage(''); try { await createAchievementAssessment(assessmentPayload(form)); formElement.reset(); await onCreated(); } catch(error){setMessage(error instanceof Error?error.message:'تعذر تسجيل النتيجة.');} finally {setSaving(false);} }
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">سجل تحصيل جديد</span><h2>تسجيل نتيجة وتقسيم الأداء</h2><p>سجل المؤشرات الأساسية فقط. التحليل المتقدم سيظل في محركاته المتخصصة ثم يرتبط بهذا السجل.</p></div><input type="hidden" name="academicYear" value={academicYear}/><input type="hidden" name="term" value={term}/><AssessmentFields teachers={teachers}/>{message&&<div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving?'جاري الحفظ...':'تسجيل النتيجة'}</button></div></form></Modal>;
}

function AssessmentForm({ assessment, teachers, onSubmit, busy }: { assessment: AchievementAssessmentDetails; teachers: Teacher[]; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; busy: boolean }) {
  return <form className="request-form achievement-edit-form" onSubmit={onSubmit}><input type="hidden" name="academicYear" value={assessment.academicYear}/><input type="hidden" name="term" value={assessment.term}/><AssessmentFields assessment={assessment} teachers={teachers}/><div className="modal-actions"><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : 'حفظ التعديلات'}</button></div></form>;
}

function AssessmentFields({ assessment, teachers }: { assessment?: AchievementAssessmentRecord; teachers: Teacher[] }) {
  return <div className="form-grid achievement-form-grid"><label className="full">عنوان التقويم<input name="title" required defaultValue={assessment?.title || ''} placeholder="مثال: الاختبار القصير الأول"/></label><label>النوع<select name="assessmentType" defaultValue={assessment?.assessmentType || 'اختبار قصير'}><option>اختبار قصير</option><option>اختبار نهائي</option><option>اختبار تشخيصي</option><option>مهمة أدائية</option><option>تقويم آخر</option></select></label><label>التاريخ<input type="date" name="assessmentDate" required defaultValue={assessment?.assessmentDate || '2026-09-15'}/></label><label>المادة<select name="subject" defaultValue={assessment?.subject || 'الفيزياء'}><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label><label>الصف<select name="grade" defaultValue={assessment?.grade || 'العاشر'}><option>العاشر</option><option>التاسع</option><option>الثامن</option></select></label><label>المعلم المسؤول<select name="teacherId" defaultValue={assessment?.teacherId || ''}><option value="">دون تعيين</option>{teachers.map((teacher)=><option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label><label>الحالة<select name="status" defaultValue={assessment?.status || 'recorded'}><option value="draft">مسودة</option><option value="recorded">مسجلة</option><option value="reviewed">مراجعة مكتملة</option></select></label><label>الدرجة الكلية<input type="number" step="0.01" min="0.01" name="maxScore" required defaultValue={assessment?.maxScore ?? 40}/></label><label>عدد الطلبة<input type="number" min="0" name="studentCount" required defaultValue={assessment?.studentCount ?? 0}/></label><label>المتوسط<input type="number" step="0.01" min="0" name="averageScore" defaultValue={assessment?.averageScore ?? ''}/></label><label>أعلى درجة<input type="number" step="0.01" min="0" name="highestScore" defaultValue={assessment?.highestScore ?? ''}/></label><label>أدنى درجة<input type="number" step="0.01" min="0" name="lowestScore" defaultValue={assessment?.lowestScore ?? ''}/></label><label>حد التصنيف/الإتقان المعتمد %<input type="number" step="0.1" min="0" max="100" name="masteryThresholdPct" required defaultValue={assessment?.masteryThresholdPct ?? ''} placeholder="أدخل الحد وفق المرجع المستخدم"/><small>لا يضع المرصد قيمة افتراضية. استخدم فقط الحد الموثق في مرجع عُماني معتمد.</small></label><label className="full">مرجع الحد المستخدم<input name="masteryReferenceSource" required defaultValue={assessment?.masteryReferenceSource || ''} placeholder="اسم وثيقة وزارة التربية والتعليم/التعميم/المرجع العُماني المعتمد"/><small>حقل إلزامي حتى لا تتحول قيمة النسبة إلى قاعدة تربوية مجهولة المصدر.</small></label><label>سنة/إصدار المرجع<input name="masteryReferenceYear" defaultValue={assessment?.masteryReferenceYear || ''} placeholder="السنة أو الإصدار إن وجد"/></label><label className="full">موضع أو ملاحظة المرجع<textarea name="masteryReferenceNote" rows={2} defaultValue={assessment?.masteryReferenceNote || ''} placeholder="البند أو الصفحة أو أي توضيح يسهل التحقق من المصدر"/></label><label>الفئة المحققة للحد<input type="number" min="0" name="masteredCount" defaultValue={assessment?.masteredCount ?? 0}/></label><label>الفئة القريبة من الحد وفق المرجع<input type="number" min="0" name="nearMasteryCount" defaultValue={assessment?.nearMasteryCount ?? 0}/></label><label>الفئة المستهدفة بالتدخل وفق المرجع<input type="number" min="0" name="interventionCount" defaultValue={assessment?.interventionCount ?? 0}/></label><label className="full">ملاحظات تحليلية مختصرة<textarea name="notes" rows={3} defaultValue={assessment?.notes || ''} placeholder="ملاحظة تربوية مختصرة دون ادعاء تشخيص مهارة من درجات كلية فقط."/></label></div>;
}

function ActionFields({ action, teachers }: { action: AchievementAction | null; teachers: Teacher[] }) {
  const metric = action?.metric || null;
  return <div className="form-grid">
    <label>نوع الإجراء<select name="actionType" defaultValue={action?.actionType || 'remedial'}><option value="remedial">علاجي</option><option value="enrichment">إثرائي</option><option value="followup">متابعة</option></select></label>
    <label>الحالة<select name="status" defaultValue={action?.baseStatus || 'new'}><option value="new">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="completed">مكتمل</option><option value="cancelled">ملغي</option></select></label>
    <label className="full">عنوان الإجراء<input name="title" required defaultValue={action?.title || ''} placeholder="اكتب وصفًا محددًا للتدخل"/></label>
    <label className="full">الفئة المستهدفة<input name="targetGroup" defaultValue={action?.targetGroup || ''} placeholder="الفئة كما حُددت في التحليل أو السجل المعتمد"/></label>
    <label>المسؤول<select name="responsibleTeacherId" defaultValue={action?.responsibleTeacherId || ''}><option value="">دون تعيين</option>{teachers.map((teacher)=><option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label>
    <label>البداية<input type="date" name="startDate" defaultValue={action?.startDate || ''}/></label>
    <label>موعد المتابعة<input type="date" name="dueDate" defaultValue={action?.dueDate || ''}/></label>
    <label className="full">وصف خط الأساس<input name="baselineIndicator" defaultValue={action?.baselineIndicator || ''} placeholder="وصف تربوي أو تشخيصي كما ورد في المصدر المستخدم"/></label>
    <label className="full">وصف الهدف<input name="targetIndicator" defaultValue={action?.targetIndicator || ''} placeholder="الهدف كما حُدد في الخطة أو المرجع"/></label>
    <label className="full">وصف الأثر بعد التنفيذ<input name="outcomeIndicator" defaultValue={action?.outcomeIndicator || ''} placeholder="وصف نوعي يعبأ بعد المتابعة إن وجد"/></label>
    <label className="full">ملاحظات<textarea name="notes" rows={3} defaultValue={action?.notes || ''}/></label>

    <div className="full impact-contract-note"><strong>قياس الأثر المنظم</strong><span>هذا الجزء يحسب التغير بالنسبة لهدف مسجل فقط. لا ينشئ معيار إتقان أو حكمًا تربويًا من تلقاء نفسه. إذا كان الهدف مستندًا إلى معيار تربوي، دوّن مصدره العُماني المعتمد.</span></div>
    <label className="full impact-toggle"><input type="checkbox" name="metricEnabled" defaultChecked={!!metric}/> تفعيل قياس أثر رقمي لهذا الإجراء</label>
    <label>اسم المؤشر<input name="metricName" defaultValue={metric?.metricName || ''} placeholder="اسم المؤشر المستخدم في الخطة"/></label>
    <label>الوحدة<input name="metricUnit" defaultValue={metric?.unit || ''} placeholder="%، درجة، عدد..."/></label>
    <label>اتجاه التحسن<select name="metricDirection" defaultValue={metric?.direction || 'higher_better'}><option value="higher_better">القيمة الأعلى أفضل</option><option value="lower_better">القيمة الأقل أفضل</option></select></label>
    <label>خط الأساس<input type="number" step="any" name="metricBaseline" defaultValue={metric?.baselineValue ?? ''}/></label>
    <label>الهدف المسجل<input type="number" step="any" name="metricTarget" defaultValue={metric?.targetValue ?? ''}/></label>
    <label>النتيجة الفعلية<input type="number" step="any" name="metricOutcome" defaultValue={metric?.outcomeValue ?? ''} placeholder="يترك فارغًا حتى القياس"/></label>
    <label>تاريخ القياس النهائي<input type="date" name="metricMeasuredAt" defaultValue={metric?.measuredAt || ''}/></label>
    <label className="full">مصدر المعيار أو الهدف<input name="metricReferenceSource" required defaultValue={metric?.referenceSource || ''} placeholder="مثال: اسم وثيقة وزارة التربية والتعليم أو خطة مدرسية معتمدة"/></label>
    <label>سنة/إصدار المرجع<input name="metricReferenceYear" defaultValue={metric?.referenceYear || ''} placeholder="السنة أو رقم الإصدار إن وجد"/></label>
    <label className="full">ملاحظة المرجع<textarea name="metricReferenceNote" rows={2} defaultValue={metric?.referenceNote || ''} placeholder="الصفحة أو البند أو أي توضيح يساعد على الرجوع للمصدر"/></label>
    <label className="full">ملاحظات القياس<textarea name="metricNotes" rows={2} defaultValue={metric?.notes || ''}/></label>
    {metric && <div className="full impact-current"><strong>الأثر الحسابي الحالي: {impactStatusLabel(metric.impactStatus)}</strong><span>{formatMetricValue(metric.baselineValue, metric.unit)} ← {formatMetricValue(metric.outcomeValue, metric.unit)} • الهدف المسجل {formatMetricValue(metric.targetValue, metric.unit)}</span>{metric.referenceSource ? <small>المصدر: {metric.referenceSource}{metric.referenceYear ? ` • ${metric.referenceYear}` : ''}</small> : <small className="warning">لم يسجل مصدر للمعيار/الهدف.</small>}</div>}
  </div>;
}

function assessmentPayload(form: FormData): AchievementAssessmentInput {
  const optionalNumber=(name:string)=>{const raw=String(form.get(name)||'').trim(); return raw === '' ? null : Number(raw);};
  const teacherRaw=String(form.get('teacherId')||'').trim();
  const masteryRaw=String(form.get('masteryThresholdPct')||'').trim();
  if (!masteryRaw) throw new Error('أدخل الحد المعتمد وفق المرجع المستخدم؛ المرصد لا يضع حدًا تربويًا من تلقاء نفسه.');
  const masteryReferenceSource=String(form.get('masteryReferenceSource')||'').trim();
  if (!masteryReferenceSource) throw new Error('وثّق مرجع الحد المستخدم من المنظومة التعليمية العُمانية.');
  return {title:String(form.get('title')||''),assessmentType:String(form.get('assessmentType')||'اختبار'),subject:String(form.get('subject')||''),grade:String(form.get('grade')||''),assessmentDate:String(form.get('assessmentDate')||''),term:String(form.get('term')||'الفصل الأول'),academicYear:String(form.get('academicYear')||''),teacherId:teacherRaw?Number(teacherRaw):null,maxScore:Number(form.get('maxScore')||0),studentCount:Number(form.get('studentCount')||0),averageScore:optionalNumber('averageScore'),highestScore:optionalNumber('highestScore'),lowestScore:optionalNumber('lowestScore'),masteryThresholdPct:Number(masteryRaw),masteryReferenceSource,masteryReferenceYear:String(form.get('masteryReferenceYear')||'').trim(),masteryReferenceNote:String(form.get('masteryReferenceNote')||'').trim(),masteredCount:Number(form.get('masteredCount')||0),nearMasteryCount:Number(form.get('nearMasteryCount')||0),interventionCount:Number(form.get('interventionCount')||0),notes:String(form.get('notes')||''),status:String(form.get('status')||'recorded') as AchievementAssessmentStatus};
}

function metricPayload(form: FormData): AchievementImpactMetricInput | null {
  if (!form.get('metricEnabled')) return null;
  const raw = (name: string) => String(form.get(name) || '').trim();
  const baseline = raw('metricBaseline');
  const target = raw('metricTarget');
  if (!raw('metricName')) throw new Error('اكتب اسم مؤشر قياس الأثر.');
  if (baseline === '' || target === '') throw new Error('أدخل خط الأساس والهدف المسجل لقياس الأثر.');
  const outcome = raw('metricOutcome');
  const measuredAt = raw('metricMeasuredAt');
  if (outcome !== '' && !measuredAt) throw new Error('أدخل تاريخ القياس النهائي عند تسجيل النتيجة الفعلية.');
  if (outcome === '' && measuredAt) throw new Error('لا تسجل تاريخ قياس نهائي دون نتيجة فعلية.');
  if (!raw('metricReferenceSource')) throw new Error('وثّق مصدر الهدف أو المعيار المستخدم في قياس الأثر.');
  return {
    metricName: raw('metricName'), unit: raw('metricUnit'),
    direction: raw('metricDirection') === 'lower_better' ? 'lower_better' : 'higher_better',
    baselineValue: Number(baseline), targetValue: Number(target), outcomeValue: outcome === '' ? null : Number(outcome),
    measuredAt: measuredAt || null, referenceSource: raw('metricReferenceSource'), referenceYear: raw('metricReferenceYear'),
    referenceNote: raw('metricReferenceNote'), notes: raw('metricNotes'),
  };
}

function actionPayload(form: FormData): AchievementActionInput { const responsible=String(form.get('responsibleTeacherId')||'').trim(); const start=String(form.get('startDate')||'').trim(); const due=String(form.get('dueDate')||'').trim(); return {actionType:String(form.get('actionType')||'remedial') as AchievementActionType,title:String(form.get('title')||''),targetGroup:String(form.get('targetGroup')||''),responsibleTeacherId:responsible?Number(responsible):null,startDate:start||null,dueDate:due||null,status:String(form.get('status')||'new') as AchievementActionBaseStatus,baselineIndicator:String(form.get('baselineIndicator')||''),targetIndicator:String(form.get('targetIndicator')||''),outcomeIndicator:String(form.get('outcomeIndicator')||''),notes:String(form.get('notes')||'')}; }
function impactStatusLabel(status: AchievementImpactStatus) { return {pending:'لم يُقَس بعد',target_met:'حقق الهدف المسجل',improved_not_met:'تحسن ولم يبلغ الهدف المسجل',no_change:'لم يحدث تغير',regressed:'تراجع المؤشر'}[status]; }
function formatMetricValue(value: number | null | undefined, unit: string) { return value === null || value === undefined ? 'لم يُقَس بعد' : `${value}${unit ? ` ${unit}` : ''}`; }
function actionNeedsImpactDecision(action: AchievementAction) { return action.baseStatus === 'completed' && (!action.metric || action.metric.impactStatus === 'pending' || action.metric.impactStatus === 'no_change' || action.metric.impactStatus === 'regressed'); }
function ImpactStatus({ status }: { status: AchievementImpactStatus }) { return <span className={`impact-status ${status}`}>{impactStatusLabel(status)}</span>; }

function AssessmentStatus({ status }: { status: AchievementAssessmentStatus }) { const labels={draft:'مسودة',recorded:'مسجلة',reviewed:'مراجعة مكتملة'}; return <span className={`assessment-status ${status}`}>{labels[status]}</span>; }
function ActionStatus({ status }: { status: AchievementAction['status'] }) { const labels={new:'جديد',in_progress:'قيد التنفيذ',completed:'مكتمل',cancelled:'ملغي',overdue:'متأخر'}; return <span className={`achievement-action-status ${status}`}>{labels[status]}</span>; }
function actionTypeLabel(type: AchievementActionType) { return {remedial:'علاجي',enrichment:'إثرائي',followup:'متابعة'}[type]; }
function formatDate(value: string) { return new Intl.DateTimeFormat('ar-OM',{day:'numeric',month:'short',year:'numeric'}).format(new Date(`${value}T12:00:00`)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('ar-OM',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'}).format(new Date(value)); }
