import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import {
  createMeeting,
  createMeetingDecision,
  deleteMeetingDecision,
  getMeetingDetails,
  updateMeeting,
  updateMeetingDecision,
} from '../lib/api';
import type {
  CreateMeetingInput,
  MeetingDecision,
  MeetingDecisionBaseStatus,
  MeetingDecisionInput,
  MeetingDetails,
  MeetingRecord,
  MeetingStatus,
  Teacher,
} from '../types';
import { PageHeader } from './Teachers';

export function Meetings({ meetings, teachers, onAddMeeting, onRefresh, initialOpenId = null, onInitialOpened }: { meetings: MeetingRecord[]; teachers: Teacher[]; onAddMeeting: () => void; onRefresh: () => Promise<void>; initialOpenId?: number | null; onInitialOpened?: () => void }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'open' | 'overdue' | 'completed'>('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MeetingDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const totals = useMemo(() => ({
    meetings: meetings.length,
    open: meetings.reduce((sum, item) => sum + item.openDecisionCount, 0),
    overdue: meetings.reduce((sum, item) => sum + item.overdueDecisionCount, 0),
    completed: meetings.reduce((sum, item) => sum + item.completedDecisionCount, 0),
  }), [meetings]);

  useEffect(() => {
    if (!initialOpenId) return;
    setSelectedId(initialOpenId);
    onInitialOpened?.();
  }, [initialOpenId]);

  const visible = useMemo(() => meetings.filter((meeting) => {
    const q = query.trim();
    const matchesQuery = !q || meeting.title.includes(q) || meeting.meetingType.includes(q) || (meeting.location || '').includes(q);
    const matchesFilter = filter === 'all'
      || (filter === 'open' && meeting.openDecisionCount > 0)
      || (filter === 'overdue' && meeting.overdueDecisionCount > 0)
      || (filter === 'completed' && meeting.decisionCount > 0 && meeting.openDecisionCount === 0);
    return matchesQuery && matchesFilter;
  }), [meetings, query, filter]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setMessage('');
    void getMeetingDetails(selectedId)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((error: unknown) => { if (!cancelled) setMessage(error instanceof Error ? error.message : 'تعذر تحميل الاجتماع.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selectedId]);

  async function reloadDetail() {
    if (!selectedId) return;
    setDetail(await getMeetingDetails(selectedId));
    await onRefresh();
  }

  return <div className="page meetings-page">
    <PageHeader eyebrow="المتابعة المؤسسية" title="الاجتماعات والقرارات" description="محضر حي لا ينتهي عند كتابة الاجتماع: كل قرار له مسؤول وموعد وحالة، وكل تغيير يبقى في سجل زمني واضح." action="اجتماع جديد" onAction={onAddMeeting} />

    <section className="meeting-kpi-grid">
      <MeetingKpi value={totals.meetings} label="اجتماعات موثقة" icon="meeting" tone="navy" />
      <MeetingKpi value={totals.open} label="قرارات مفتوحة" icon="clock" tone="teal" />
      <MeetingKpi value={totals.overdue} label="قرارات متأخرة" icon="alert" tone="danger" />
      <MeetingKpi value={totals.completed} label="قرارات مكتملة" icon="check" tone="success" />
    </section>

    <div className="toolbar modern-toolbar meeting-toolbar">
      <div className="filter-row">
        <button className={`filter-chip ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>الكل</button>
        <button className={`filter-chip ${filter === 'open' ? 'active' : ''}`} onClick={() => setFilter('open')}>بقرارات مفتوحة</button>
        <button className={`filter-chip ${filter === 'overdue' ? 'active' : ''}`} onClick={() => setFilter('overdue')}>متأخرة</button>
        <button className={`filter-chip ${filter === 'completed' ? 'active' : ''}`} onClick={() => setFilter('completed')}>مغلقة القرارات</button>
      </div>
      <label className="inline-search"><Icon name="search" size={18}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ابحث في الاجتماعات..."/></label>
    </div>

    {visible.length ? <div className="meeting-list">{visible.map((meeting) => <MeetingCard key={meeting.id} meeting={meeting} onOpen={() => setSelectedId(meeting.id)} />)}</div> : <div className="empty-state"><Icon name="meeting" size={32}/><strong>لا توجد اجتماعات مطابقة</strong><p>غيّر التصفية أو أنشئ اجتماعًا جديدًا.</p></div>}

    <Modal open={selectedId !== null} onClose={() => setSelectedId(null)} wide>
      {loading ? <div className="event-detail-loading"><div className="spinner"></div><p>جاري تجهيز محضر الاجتماع...</p></div> : detail ? <MeetingDetail detail={detail} teachers={teachers} onReload={reloadDetail} onClose={() => setSelectedId(null)} onMessage={setMessage}/> : <div className="inline-error"><Icon name="alert" size={17}/>{message || 'تعذر تحميل الاجتماع.'}</div>}
    </Modal>
    {message && selectedId !== null && detail && <div className="toast">{message}</div>}
  </div>;
}

function MeetingCard({ meeting, onOpen }: { meeting: MeetingRecord; onOpen: () => void }) {
  const completion = meeting.decisionCount ? Math.round((meeting.completedDecisionCount / meeting.decisionCount) * 100) : 0;
  return <article className={`meeting-card ${meeting.overdueDecisionCount ? 'has-overdue' : ''}`}>
    <button className="meeting-date-tile" onClick={onOpen}><strong>{new Date(`${meeting.meetingDate}T12:00:00`).getDate()}</strong><span>{monthName(meeting.meetingDate)}</span><small>{meeting.meetingTime || 'دون وقت'}</small></button>
    <div className="meeting-card-body">
      <div className="meeting-card-head"><div><span className={`meeting-status ${meeting.status}`}>{meetingStatusLabel(meeting.status)}</span><h3>{meeting.title}</h3><p>{meeting.meetingType} • {meeting.location || 'المكان غير محدد'}</p></div><button className="icon-button" onClick={onOpen}><Icon name="chevron"/></button></div>
      <div className="meeting-card-stats"><span><Icon name="teachers" size={16}/>{meeting.attendeeCount} حاضرًا</span><span><Icon name="meeting" size={16}/>{meeting.decisionCount} قرارًا</span><span className={meeting.overdueDecisionCount ? 'danger-text' : ''}><Icon name={meeting.overdueDecisionCount ? 'alert' : 'clock'} size={16}/>{meeting.openDecisionCount} مفتوحًا</span></div>
      <div className="meeting-progress"><div><span>إنجاز القرارات</span><strong>{completion}%</strong></div><div className="meeting-progress-track"><i style={{ width: `${completion}%` }}/></div></div>
    </div>
  </article>;
}

function MeetingKpi({ value, label, icon, tone }: { value: number; label: string; icon: 'meeting' | 'clock' | 'alert' | 'check'; tone: string }) {
  return <article className={`meeting-kpi ${tone}`}><span><Icon name={icon}/></span><div><strong>{value}</strong><small>{label}</small></div></article>;
}

function MeetingDetail({ detail, teachers, onReload, onClose, onMessage }: { detail: MeetingDetails; teachers: Teacher[]; onReload: () => Promise<void>; onClose: () => void; onMessage: (message: string) => void }) {
  const [tab, setTab] = useState<'overview' | 'decisions' | 'team' | 'timeline'>('overview');
  const [editing, setEditing] = useState(false);
  const [addingDecision, setAddingDecision] = useState(false);
  const [selectedAttendees, setSelectedAttendees] = useState<number[]>(detail.attendees.map((item) => item.id));
  const [savingTeam, setSavingTeam] = useState(false);

  useEffect(() => setSelectedAttendees(detail.attendees.map((item) => item.id)), [detail.attendees]);

  async function saveTeam() {
    setSavingTeam(true);
    try {
      await updateMeeting(detail.id, meetingPayloadFromDetail(detail, selectedAttendees));
      await onReload();
      onMessage('تم تحديث حضور الاجتماع');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث الحضور.');
    } finally { setSavingTeam(false); }
  }

  const completion = detail.decisionCount ? Math.round((detail.completedDecisionCount / detail.decisionCount) * 100) : 0;

  return <div className="meeting-detail-shell">
    <header className="meeting-detail-hero">
      <div className="meeting-hero-date"><strong>{new Date(`${detail.meetingDate}T12:00:00`).getDate()}</strong><span>{monthName(detail.meetingDate)}</span><small>{detail.meetingTime || 'دون وقت'}</small></div>
      <div className="meeting-hero-copy"><span className="eyebrow">{detail.meetingType}</span><h2>{detail.title}</h2><div className="meeting-hero-meta"><span><Icon name="calendar" size={16}/>{formatDate(detail.meetingDate)}</span><span><Icon name="teachers" size={16}/>{detail.attendeeCount} حاضرًا</span><span><Icon name="meeting" size={16}/>{detail.decisionCount} قرارًا</span></div></div>
      <div className="meeting-hero-status"><span className={`minutes-readiness ${detail.minutesReady ? 'ready' : ''}`}><Icon name={detail.minutesReady ? 'check' : 'clock'} size={17}/><div><strong>{detail.minutesReady ? 'المحضر مكتمل البنية' : 'المحضر يحتاج استكمالًا'}</strong><small>{detail.minutesReady ? 'جاهز لتوليد تقرير رسمي لاحقًا' : 'أكمل النقاش والحضور والقرارات'}</small></div></span><div className="meeting-completion-ring"><strong>{completion}%</strong><small>إنجاز القرارات</small></div></div>
    </header>

    <nav className="meeting-tabs"><button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>المحضر</button><button className={tab === 'decisions' ? 'active' : ''} onClick={() => setTab('decisions')}>القرارات <b>{detail.decisions.length}</b></button><button className={tab === 'team' ? 'active' : ''} onClick={() => setTab('team')}>الحضور <b>{detail.attendees.length}</b></button><button className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>السجل الزمني</button></nav>

    {tab === 'overview' && (editing ? <MeetingEditForm detail={detail} onCancel={() => setEditing(false)} onSaved={async () => { await onReload(); setEditing(false); }} onMessage={onMessage}/> : <div className="meeting-overview-layout">
      <div className="meeting-minutes"><MinuteSection title="جدول الأعمال" text={detail.agenda}/><MinuteSection title="ملخص المناقشات" text={detail.discussionSummary}/><MinuteSection title="ملاحظات إضافية" text={detail.notes}/></div>
      <aside className="meeting-side-card"><div className="meeting-side-head"><span className={`meeting-status ${detail.status}`}>{meetingStatusLabel(detail.status)}</span><button className="soft-button tiny" onClick={() => setEditing(true)}><Icon name="planning" size={15}/> تحرير المحضر</button></div><InfoRow label="نوع الاجتماع" value={detail.meetingType}/><InfoRow label="التاريخ" value={formatDate(detail.meetingDate)}/><InfoRow label="الوقت" value={detail.meetingTime || 'غير محدد'}/><InfoRow label="المكان" value={detail.location || 'غير محدد'}/><InfoRow label="العام الدراسي" value={detail.academicYear}/></aside>
    </div>)}

    {tab === 'decisions' && <section className="decision-section">
      <div className="decision-section-head"><div><span className="eyebrow">المتابعة التنفيذية</span><h3>قرارات الاجتماع</h3><p>كل قرار يبقى مفتوحًا حتى يُغلق فعليًا، لا حتى يختفي المحضر في مجلد ما.</p></div><button className="primary-button" onClick={() => setAddingDecision((value) => !value)}><Icon name={addingDecision ? 'close' : 'plus'}/>{addingDecision ? 'إلغاء' : 'إضافة قرار'}</button></div>
      {addingDecision && <DecisionForm meetingId={detail.id} teachers={teachers} onSaved={async () => { await onReload(); setAddingDecision(false); }} onMessage={onMessage}/>} 
      {detail.decisions.length ? <div className="decision-list">{detail.decisions.map((decision) => <DecisionCard key={decision.id} decision={decision} meetingId={detail.id} teachers={teachers} onReload={onReload} onMessage={onMessage}/>)}</div> : <div className="empty-state compact"><Icon name="meeting" size={30}/><strong>لا توجد قرارات بعد</strong><p>أضف أول قرار ليبدأ مسار المتابعة.</p></div>}
    </section>}

    {tab === 'team' && <section className="meeting-team-section"><div className="event-team-head"><div><h3>الحضور</h3><p>حدد أعضاء القسم الذين حضروا الاجتماع. هذه القائمة تحفظ داخل المحضر نفسه.</p></div><button className="primary-button" onClick={() => void saveTeam()} disabled={savingTeam}>{savingTeam ? 'جاري الحفظ...' : 'حفظ الحضور'}</button></div><div className="event-team-grid">{teachers.map((teacher) => { const checked = selectedAttendees.includes(teacher.id); return <label key={teacher.id} className={`event-team-card ${checked ? 'selected' : ''}`}><input type="checkbox" checked={checked} onChange={() => setSelectedAttendees((items) => checked ? items.filter((id) => id !== teacher.id) : [...items, teacher.id])}/><span className="avatar">{teacher.name[0]}</span><div><strong>{teacher.name}</strong><small>{teacher.subject}</small></div><span className="team-check"><Icon name="check" size={15}/></span></label>; })}</div></section>}

    {tab === 'timeline' && <section className="meeting-timeline-section"><div className="meeting-timeline-head"><span className="eyebrow">الأثر الزمني</span><h3>ما الذي حدث لهذا الاجتماع؟</h3><p>الإنشاء والتعديل والقرارات وتغييراتها مرتبة من الأحدث إلى الأقدم.</p></div>{detail.timeline.length ? <div className="meeting-timeline">{detail.timeline.map((item) => <div className="meeting-timeline-item" key={item.id}><span className="timeline-symbol"><Icon name={item.title.includes('قرار') ? 'check' : 'meeting'} size={17}/></span><div><strong>{item.title}</strong><small>{item.detail || 'تحديث موثق'} • {formatDateTime(item.created_at)}</small></div></div>)}</div> : <div className="empty-state compact"><Icon name="clock" size={30}/><strong>لا توجد حركة مسجلة بعد</strong></div>}</section>}

    <footer className="event-detail-footer"><button className="ghost-button" onClick={onClose}>إغلاق</button><span>آخر تحديث: {formatDateTime(detail.updatedAt)}</span></footer>
  </div>;
}

function MeetingEditForm({ detail, onCancel, onSaved, onMessage }: { detail: MeetingDetails; onCancel: () => void; onSaved: () => Promise<void>; onMessage: (message: string) => void }) {
  const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    try {
      await updateMeeting(detail.id, meetingInputFromForm(form, detail.attendees.map((item) => item.id)));
      await onSaved();
      onMessage('تم تحديث محضر الاجتماع');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث الاجتماع.');
    } finally { setSaving(false); }
  }
  return <form className="meeting-edit-form" onSubmit={submit}><div className="event-edit-heading"><div><span className="eyebrow">تحرير المحضر</span><h3>بيانات الاجتماع والمناقشة</h3></div><span className="status-pill approved"><Icon name="check" size={14}/> سجل واحد مستمر</span></div><MeetingFields initial={detail}/><div className="event-edit-actions"><button type="button" className="ghost-button" onClick={onCancel}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : 'حفظ التحديث'}</button></div></form>;
}

function DecisionCard({ decision, meetingId, teachers, onReload, onMessage }: { decision: MeetingDecision; meetingId: number; teachers: Teacher[]; onReload: () => Promise<void>; onMessage: (message: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  async function setStatus(status: MeetingDecisionBaseStatus) {
    setBusy(true);
    try {
      await updateMeetingDecision(meetingId, decision.id, {
        title: decision.title,
        responsibleTeacherId: decision.responsibleTeacherId,
        responsibleName: decision.responsibleName || '',
        dueDate: decision.dueDate || null,
        status,
        notes: decision.notes || '',
      });
      await onReload();
      onMessage('تم تحديث حالة القرار');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث القرار.');
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm('حذف هذا القرار من محضر الاجتماع؟')) return;
    setBusy(true);
    try {
      await deleteMeetingDecision(meetingId, decision.id);
      await onReload();
      onMessage('تم حذف القرار');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر حذف القرار.');
    } finally { setBusy(false); }
  }

  if (editing) return <DecisionForm meetingId={meetingId} teachers={teachers} decision={decision} onSaved={async () => { await onReload(); setEditing(false); }} onCancel={() => setEditing(false)} onMessage={onMessage}/>;

  return <article className={`decision-card ${decision.status}`}><div className="decision-status-column"><span className={`decision-status-badge ${decision.status}`}>{decisionStatusLabel(decision.status)}</span>{decision.dueDate && <small className={decision.status === 'overdue' ? 'danger-text' : ''}><Icon name="calendar" size={14}/>{formatDate(decision.dueDate)}</small>}</div><div className="decision-main"><h4>{decision.title}</h4><div className="decision-meta"><span><Icon name="user" size={15}/>{decision.responsibleName || 'دون مسؤول محدد'}</span>{decision.notes && <span><Icon name="document" size={15}/>{decision.notes}</span>}</div><div className="decision-actions"><select value={decision.baseStatus} onChange={(event) => void setStatus(event.target.value as MeetingDecisionBaseStatus)} disabled={busy}><option value="new">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="completed">مكتمل</option><option value="cancelled">ملغي</option></select><button className="soft-button tiny" onClick={() => setEditing(true)} disabled={busy}>تحرير</button><button className="text-button danger" onClick={() => void remove()} disabled={busy}>حذف</button></div></div></article>;
}

function DecisionForm({ meetingId, teachers, decision, onSaved, onCancel, onMessage }: { meetingId: number; teachers: Teacher[]; decision?: MeetingDecision; onSaved: () => Promise<void>; onCancel?: () => void; onMessage: (message: string) => void }) {
  const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const teacherIdRaw = String(form.get('responsibleTeacherId') || '');
    const input: MeetingDecisionInput = {
      title: String(form.get('title') || ''),
      responsibleTeacherId: teacherIdRaw ? Number(teacherIdRaw) : null,
      responsibleName: String(form.get('responsibleName') || ''),
      dueDate: String(form.get('dueDate') || '') || null,
      status: String(form.get('status') || 'new') as MeetingDecisionBaseStatus,
      notes: String(form.get('notes') || ''),
    };
    setSaving(true);
    try {
      if (decision) await updateMeetingDecision(meetingId, decision.id, input);
      else await createMeetingDecision(meetingId, input);
      await onSaved();
      onMessage(decision ? 'تم تحديث القرار' : 'تمت إضافة القرار');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر حفظ القرار.');
    } finally { setSaving(false); }
  }
  return <form className="decision-form" onSubmit={submit}><div className="decision-form-head"><div><span className="eyebrow">{decision ? 'تحرير قرار' : 'قرار جديد'}</span><h4>{decision ? 'حدّث بيانات القرار ومسؤوليته' : 'حوّل النقاش إلى إجراء قابل للمتابعة'}</h4></div>{onCancel && <button type="button" className="icon-button" onClick={onCancel}><Icon name="close"/></button>}</div><div className="form-grid"><label className="full">نص القرار<input name="title" required defaultValue={decision?.title || ''} placeholder="مثال: اعتماد خطة الزيارات الصفية"/></label><label>المسؤول من الفريق<select name="responsibleTeacherId" defaultValue={decision?.responsibleTeacherId || ''}><option value="">غير محدد / مسؤول آخر</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label><label>اسم المسؤول<input name="responsibleName" defaultValue={decision?.responsibleName || ''} placeholder="يُملأ تلقائيًا عند اختيار معلم"/></label><label>الموعد النهائي<input type="date" name="dueDate" defaultValue={decision?.dueDate || ''}/></label><label>الحالة<select name="status" defaultValue={decision?.baseStatus || 'new'}><option value="new">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="completed">مكتمل</option><option value="cancelled">ملغي</option></select></label><label className="full">ملاحظات المتابعة<textarea name="notes" rows={2} defaultValue={decision?.notes || ''} placeholder="تفاصيل التنفيذ أو معيار الإغلاق..."/></label></div><div className="modal-actions">{onCancel && <button type="button" className="ghost-button" onClick={onCancel}>إلغاء</button>}<button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : decision ? 'حفظ القرار' : 'إضافة القرار'}</button></div></form>;
}

export function MeetingModal({ open, teachers, academicYear, onClose, onCreated }: { open: boolean; teachers: Teacher[]; academicYear: string; onClose: () => void; onCreated: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [attendeeQuery, setAttendeeQuery] = useState('');
  const [selectedAttendees, setSelectedAttendees] = useState<number[]>([]);

  useEffect(() => {
    if (!open) return;
    setAttendeeQuery('');
    setSelectedAttendees([]);
    setMessage('');
  }, [open, academicYear]);

  const visibleTeachers = useMemo(() => {
    const query = attendeeQuery.trim().toLocaleLowerCase('ar');
    if (!query) return teachers;
    return teachers.filter((teacher) => `${teacher.name} ${teacher.subject} ${teacher.specialization || ''}`.toLocaleLowerCase('ar').includes(query));
  }, [teachers, attendeeQuery]);

  function toggleAttendee(teacherId: number) {
    setSelectedAttendees((current) => current.includes(teacherId) ? current.filter((id) => id !== teacherId) : [...current, teacherId]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSaving(true);
    setMessage('');
    try {
      await createMeeting(meetingInputFromForm(form, selectedAttendees));
      formElement.reset();
      setSelectedAttendees([]);
      await onCreated();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر إنشاء الاجتماع.');
    } finally { setSaving(false); }
  }

  return <Modal open={open} onClose={onClose}><form className="request-form meeting-create-form" onSubmit={submit}>
    <div className="modal-heading"><span className="eyebrow">محضر جديد</span><h2>إنشاء اجتماع</h2><p>أنشئ المحضر وحدد الحضور من دليل المعلمين. اختيار معلم في عام تاريخي يربطه بذلك العام تلقائيًا دون إنشاء نسخة جديدة منه.</p></div>
    <MeetingFields academicYear={academicYear}/>
    <div className="meeting-attendee-picker">
      <div className="meeting-attendee-picker-head">
        <div><strong>الحضور</strong><small>{selectedAttendees.length} محدد من {teachers.length}</small></div>
        <div className="meeting-attendee-actions">
          <button type="button" onClick={()=>setSelectedAttendees(teachers.map((teacher)=>teacher.id))} disabled={!teachers.length}>تحديد الكل</button>
          <button type="button" onClick={()=>setSelectedAttendees([])} disabled={!selectedAttendees.length}>إلغاء الكل</button>
        </div>
      </div>
      {teachers.length ? <>
        <label className="meeting-attendee-search"><Icon name="search" size={17}/><input value={attendeeQuery} onChange={(event)=>setAttendeeQuery(event.target.value)} placeholder="ابحث عن معلم بالاسم أو المادة..."/></label>
        <div className="meeting-attendee-options">{visibleTeachers.map((teacher) => {
          const checked=selectedAttendees.includes(teacher.id);
          return <label key={teacher.id} className={checked?'selected':''}>
            <input type="checkbox" checked={checked} onChange={()=>toggleAttendee(teacher.id)}/>
            <span className="avatar">{teacher.name[0]}</span>
            <div><b>{teacher.name}</b><small>{teacher.subject}{teacher.specialization?` • ${teacher.specialization}`:''}</small></div>
          </label>;
        })}</div>
        {!visibleTeachers.length&&<div className="quiet-note">لا توجد أسماء مطابقة للبحث.</div>}
      </> : <div className="inline-warning"><Icon name="alert" size={17}/><span>دليل المعلمين فارغ. أضف المعلمين أولًا من قسم «المعلمون»، ثم سيظهرون هنا للاختيار في أي عام دراسي.</span></div>}
    </div>
    {message && <div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}
    <div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الإنشاء...' : 'إنشاء الاجتماع'}</button></div>
  </form></Modal>;
}

function MeetingFields({ initial, academicYear }: { initial?: MeetingDetails; academicYear?: string }) {
  return <div className="form-grid meeting-form-grid"><label className="full">عنوان الاجتماع<input name="title" required defaultValue={initial?.title || 'اجتماع قسم العلوم'} /></label><label>نوع الاجتماع<select name="meetingType" defaultValue={initial?.meetingType || 'اجتماع قسم'}><option>اجتماع قسم</option><option>اجتماع متابعة</option><option>اجتماع تنسيقي</option><option>اجتماع نتائج</option><option>اجتماع طارئ</option></select></label><label>الحالة<select name="status" defaultValue={initial?.status || 'planned'}><option value="planned">مخطط</option><option value="held">منعقد</option><option value="cancelled">ملغي</option></select></label><label>التاريخ<input type="date" name="meetingDate" required defaultValue={initial?.meetingDate || ''}/></label><label>العام الدراسي للسجل<input name="academicYear" required readOnly value={initial?.academicYear || academicYear || ''} dir="ltr"/><small className="field-hint">يُحدد من تقويم عام العمل أعلى التطبيق.</small></label><label>الوقت<input type="time" name="meetingTime" defaultValue={initial?.meetingTime || ''}/></label><label className="full">المكان<input name="location" defaultValue={initial?.location || 'قاعة العلوم'}/></label><label className="full">جدول الأعمال<textarea name="agenda" rows={4} defaultValue={initial?.agenda || ''} placeholder="اكتب المحاور الرئيسة للاجتماع..."/></label><label className="full">ملخص المناقشات<textarea name="discussionSummary" rows={4} defaultValue={initial?.discussionSummary || ''} placeholder="أهم ما نوقش وما تم الاتفاق عليه..."/></label><label className="full">ملاحظات<textarea name="notes" rows={2} defaultValue={initial?.notes || ''}/></label></div>;
}

function meetingInputFromForm(form: FormData, attendeeIds: number[]): CreateMeetingInput {
  return {
    title: String(form.get('title') || ''), meetingType: String(form.get('meetingType') || 'اجتماع قسم'), meetingDate: String(form.get('meetingDate') || ''), academicYear: String(form.get('academicYear') || ''), meetingTime: String(form.get('meetingTime') || ''), location: String(form.get('location') || ''), agenda: String(form.get('agenda') || ''), discussionSummary: String(form.get('discussionSummary') || ''), notes: String(form.get('notes') || ''), status: String(form.get('status') || 'planned') as MeetingStatus, attendeeIds,
  };
}
function meetingPayloadFromDetail(detail: MeetingDetails, attendeeIds: number[]): CreateMeetingInput { return { title: detail.title, meetingType: detail.meetingType, meetingDate: detail.meetingDate, academicYear: detail.academicYear, meetingTime: detail.meetingTime || '', location: detail.location || '', agenda: detail.agenda || '', discussionSummary: detail.discussionSummary || '', notes: detail.notes || '', status: detail.status, attendeeIds }; }
function MinuteSection({ title, text }: { title: string; text?: string | null }) { return <section className="meeting-minute-card"><span className="eyebrow">{title}</span><p>{text || 'لم يُسجل محتوى لهذا القسم بعد.'}</p></section>; }
function InfoRow({ label, value }: { label: string; value: string }) { return <div className="meeting-info-row"><small>{label}</small><strong>{value}</strong></div>; }
function meetingStatusLabel(status: MeetingStatus) { return status === 'planned' ? 'مخطط' : status === 'held' ? 'منعقد' : 'ملغي'; }
function decisionStatusLabel(status: MeetingDecision['status']) { return status === 'new' ? 'جديد' : status === 'in_progress' ? 'قيد التنفيذ' : status === 'completed' ? 'مكتمل' : status === 'overdue' ? 'متأخر' : 'ملغي'; }
function monthName(value: string) { return new Intl.DateTimeFormat('ar-OM', { month: 'short' }).format(new Date(`${value}T12:00:00`)); }
function formatDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${value}T12:00:00`)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)); }
function todayInputValue() { const now = new Date(); const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000); return local.toISOString().slice(0, 10); }
