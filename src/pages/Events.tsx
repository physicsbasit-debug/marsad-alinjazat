import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { deleteEventMedia, getEventDetails, reorderEventMedia, updateEvent, updateEventMedia, uploadEventMedia } from '../lib/api';
import type { EventDetails, EventMediaRecord, EventRecord, Teacher } from '../types';
import { PageHeader } from './Teachers';

export function Events({ events, teachers, onAddEvent, onRefresh, initialOpenId = null, onInitialOpened }: { events: EventRecord[]; teachers: Teacher[]; onAddEvent: () => void; onRefresh: () => Promise<void>; initialOpenId?: number | null; onInitialOpened?: () => void }) {
  const [query, setQuery] = useState('');
  const [type, setType] = useState('الكل');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<EventDetails | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [message, setMessage] = useState('');

  const types = ['الكل', ...Array.from(new Set(events.map((event) => event.eventType)))];

  useEffect(() => {
    if (!initialOpenId) return;
    setSelectedId(initialOpenId);
    onInitialOpened?.();
  }, [initialOpenId]);
  const visible = useMemo(() => events.filter((event) => {
    const q = query.trim();
    const matchType = type === 'الكل' || event.eventType === type;
    const matchQuery = !q || event.title.includes(q) || (event.summary || '').includes(q) || (event.audience || '').includes(q);
    return matchType && matchQuery;
  }), [events, query, type]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    setMessage('');
    void getEventDetails(selectedId)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((error: unknown) => { if (!cancelled) setMessage(error instanceof Error ? error.message : 'تعذر تحميل الفعالية.'); })
      .finally(() => { if (!cancelled) setLoadingDetail(false); });
    return () => { cancelled = true; };
  }, [selectedId]);

  async function reloadDetail() {
    if (!selectedId) return;
    const result = await getEventDetails(selectedId);
    setDetail(result);
    await onRefresh();
  }

  return <div className="page">
    <PageHeader eyebrow="الذاكرة البصرية" title="الفعاليات والتوثيق" description="توثيق تربوي كامل للفعالية: الهدف والتنفيذ والمخرجات والفريق والصور والأدلة، في سجل واحد قابل للرجوع والتقرير." action="توثيق فعالية" onAction={onAddEvent} />

    <div className="feature-banner event-banner"><div className="banner-icon"><Icon name="image" size={28}/></div><div><strong>كل فعالية تصبح سجل إنجاز موثقًا</strong><p>لا صور متناثرة ولا ملفات يتيمة: الغلاف، الأدلة، المعلمون المشاركون، والنتائج كلها مرتبطة بنفس السجل.</p></div><span className="event-banner-stat">{events.length}<small>فعاليات موثقة</small></span></div>

    <div className="toolbar modern-toolbar event-toolbar">
      <div className="filter-row">{types.map((item) => <button key={item} className={`filter-chip ${type === item ? 'active' : ''}`} onClick={() => setType(item)}>{item}</button>)}</div>
      <label className="inline-search"><Icon name="search" size={18}/><input value={query} onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)} placeholder="ابحث في الفعاليات..." /></label>
    </div>

    <div className="event-grid">{visible.map((event) => <article className="event-card" key={event.id}>
      <button className={`event-cover ${event.coverTone} ${event.coverMediaUrl ? 'has-image' : ''}`} style={event.coverMediaUrl ? { backgroundImage: `linear-gradient(180deg, rgba(11,31,42,.05), rgba(11,31,42,.48)), url(${event.coverMediaUrl})` } : undefined} onClick={() => setSelectedId(event.id)}>
        <span className="event-date"><Icon name="calendar" size={15}/>{formatDate(event.eventDate)}</span><span className="event-type">{event.eventType}</span>
      </button>
      <div className="event-body"><h3>{event.title}</h3><p>{event.summary || event.goals || 'فعالية موثقة ضمن سجل المادة.'}</p>
        <div className="event-meta"><span><Icon name="teachers" size={16}/>{event.participantCount} مشاركًا</span><span><Icon name="image" size={16}/>{event.mediaCount || 0} دليلًا</span></div>
        <div className="card-footer"><span className="status-pill approved"><Icon name="check" size={14}/> موثق</span><button className="text-button" onClick={() => setSelectedId(event.id)}>عرض الفعالية <Icon name="arrow" size={16}/></button></div>
      </div>
    </article>)}</div>

    <Modal open={selectedId !== null} onClose={() => setSelectedId(null)} wide>
      {loadingDetail ? <div className="event-detail-loading"><div className="spinner"></div><p>جاري تجهيز سجل الفعالية...</p></div> : detail ? <EventDetail detail={detail} allTeachers={teachers} onReload={reloadDetail} onClose={() => setSelectedId(null)} onMessage={setMessage} /> : <div className="inline-error"><Icon name="alert" size={17}/>{message || 'تعذر تحميل الفعالية.'}</div>}
    </Modal>
    {message && selectedId !== null && detail && <div className="toast">{message}</div>}
  </div>;
}

function EventDetail({ detail, allTeachers, onReload, onClose, onMessage }: { detail: EventDetails; allTeachers: Teacher[]; onReload: () => Promise<void>; onClose: () => void; onMessage: (message: string) => void }) {
  const [tab, setTab] = useState<'overview' | 'media' | 'team'>('overview');
  const [selectedTeachers, setSelectedTeachers] = useState<number[]>(detail.teachers.map((teacher) => teacher.id));
  const [savingTeam, setSavingTeam] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);

  useEffect(() => setSelectedTeachers(detail.teachers.map((teacher) => teacher.id)), [detail.teachers]);

  const cover = detail.media.find((item) => item.isCover && isImage(item));
  const reportReady = Boolean(detail.goals && detail.summary && detail.outcomes && detail.media.length > 0);
  const sortedMedia = [...detail.media].sort((a, b) => a.position - b.position || a.id - b.id);

  async function saveTeam() {
    setSavingTeam(true);
    try {
      await updateEvent(detail.id, {
        title: detail.title,
        eventType: detail.eventType,
        eventDate: detail.eventDate,
        academicYear: detail.academicYear || '',
        location: detail.location || '',
        audience: detail.audience || '',
        participantCount: detail.participantCount,
        goals: detail.goals || '',
        summary: detail.summary || '',
        outcomes: detail.outcomes || '',
        recommendations: detail.recommendations || '',
        teacherIds: selectedTeachers,
      });
      await onReload();
      onMessage('تم تحديث فريق الفعالية');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث المشاركين.');
    } finally {
      setSavingTeam(false);
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      await uploadEventMedia(detail.id, Array.from(files));
      await onReload();
      onMessage('تمت إضافة أدلة الفعالية');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر رفع أدلة الفعالية.');
    } finally {
      setUploading(false);
    }
  }

  async function moveMedia(mediaId: number, direction: -1 | 1) {
    const ids = sortedMedia.map((item) => item.id);
    const index = ids.indexOf(mediaId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      await reorderEventMedia(detail.id, ids);
      await onReload();
      onMessage('تم تحديث ترتيب الأدلة');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر ترتيب الأدلة.');
    }
  }

  return <div className="event-detail-shell">
    <div className={`event-detail-hero ${detail.coverTone}`} style={cover?.contentUrl ? { backgroundImage: `linear-gradient(180deg, rgba(7,25,35,.18), rgba(7,25,35,.68)), url(${cover.contentUrl})` } : undefined}>
      <div className="event-detail-hero-copy"><span className="event-type floating">{detail.eventType}</span><h2>{detail.title}</h2><div className="event-detail-meta"><span><Icon name="calendar" size={16}/>{detail.academicYear ? `${detail.academicYear} • ` : ''}{formatDate(detail.eventDate)}</span><span><Icon name="teachers" size={16}/>{detail.participantCount} مشاركًا</span><span><Icon name="image" size={16}/>{detail.media.length} دليلًا</span></div></div>
      <div className="event-detail-hero-actions"><div className={`report-readiness ${reportReady ? 'ready' : ''}`}><Icon name={reportReady ? 'check' : 'clock'} size={17}/><div><strong>{reportReady ? 'جاهز لبناء تقرير فعالية' : 'التوثيق يحتاج استكمالًا'}</strong><small>{reportReady ? 'البيانات والأدلة الأساسية متوفرة' : 'أكمل المخرجات وأضف دليلًا واحدًا على الأقل'}</small></div></div><button className="event-edit-button" onClick={() => { setTab('overview'); setEditing((value) => !value); }}><Icon name={editing ? 'close' : 'planning'} size={16}/>{editing ? 'إلغاء التحرير' : 'تحرير البيانات'}</button></div>
    </div>

    <div className="event-detail-tabs"><button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>نظرة عامة</button><button className={tab === 'media' ? 'active' : ''} onClick={() => setTab('media')}>الأدلة والصور <b>{detail.media.length}</b></button><button className={tab === 'team' ? 'active' : ''} onClick={() => setTab('team')}>الفريق <b>{detail.teachers.length}</b></button></div>

    {tab === 'overview' && (editing ? <EventEditForm detail={detail} onCancel={() => setEditing(false)} onSaved={async () => { await onReload(); setEditing(false); }} onMessage={onMessage} /> : <div className="event-overview-layout">
      <div className="event-story"><EventSection title="الأهداف" text={detail.goals} /><EventSection title="التنفيذ" text={detail.summary} /><EventSection title="النتائج والمخرجات" text={detail.outcomes} /><EventSection title="التوصيات" text={detail.recommendations} /></div>
      <aside className="event-side-panel"><InfoRow icon="calendar" label="التاريخ" value={formatDate(detail.eventDate)} /><InfoRow icon="meeting" label="المكان" value={detail.location || 'غير مسجل'} /><InfoRow icon="teachers" label="الفئة المستهدفة" value={detail.audience || 'غير مسجلة'} /><div className="event-timeline"><strong>الخط الزمني</strong><TimelineItem title="إنشاء سجل الفعالية" date={formatDateTime(detail.createdAt)} /><TimelineItem title="موعد تنفيذ الفعالية" date={formatDate(detail.eventDate)} />{detail.media[0] && <TimelineItem title="آخر دليل مضاف" date={formatDateTime(detail.media[detail.media.length - 1].createdAt)} />}</div></aside>
    </div>)}

    {tab === 'media' && <div className="event-media-section">
      <label className={`event-upload-zone ${uploading ? 'busy' : ''}`}><Icon name="upload" size={28}/><strong>{uploading ? 'جاري رفع الأدلة...' : 'أضف صورًا أو ملفات توثيقية'}</strong><span>JPG, PNG, WEBP, PDF, Word, Excel, PowerPoint • حتى 25 MB للملف</span><input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx" onChange={(event: ChangeEvent<HTMLInputElement>) => void upload(event.target.files)} disabled={uploading}/></label>
      {sortedMedia.length ? <div className="event-media-grid">{sortedMedia.map((media, index) => <MediaCard key={media.id} eventId={detail.id} media={media} onReload={onReload} onMessage={onMessage} canMoveEarlier={index > 0} canMoveLater={index < sortedMedia.length - 1} onMove={(direction) => void moveMedia(media.id, direction)} />)}</div> : <div className="empty-state compact"><Icon name="image" size={30}/><strong>لا توجد أدلة بعد</strong><p>أضف أول صورة أو ملف ليبدأ سجل التوثيق البصري.</p></div>}
    </div>}

    {tab === 'team' && <div className="event-team-section"><div className="event-team-head"><div><h3>المعلمون المشاركون</h3><p>اربط الفعالية بأعضاء القسم ليظهر الإنجاز تلقائيًا في ملفاتهم المهنية مستقبلًا.</p></div><button className="primary-button" onClick={() => void saveTeam()} disabled={savingTeam}>{savingTeam ? 'جاري الحفظ...' : 'حفظ الفريق'}</button></div><div className="event-team-grid">{allTeachers.map((teacher) => { const checked = selectedTeachers.includes(teacher.id); return <label key={teacher.id} className={`event-team-card ${checked ? 'selected' : ''}`}><input type="checkbox" checked={checked} onChange={() => setSelectedTeachers((items) => checked ? items.filter((id) => id !== teacher.id) : [...items, teacher.id])}/><span className="avatar">{teacher.name[0]}</span><div><strong>{teacher.name}</strong><small>{teacher.subject} • {teacher.experienceYears} سنة خبرة</small></div><span className="team-check"><Icon name="check" size={15}/></span></label>; })}</div></div>}

    <div className="event-detail-footer"><button className="ghost-button" onClick={onClose}>إغلاق</button><span>آخر تحديث: {formatDateTime(detail.updatedAt)}</span></div>
  </div>;
}

function EventEditForm({ detail, onCancel, onSaved, onMessage }: { detail: EventDetails; onCancel: () => void; onSaved: () => Promise<void>; onMessage: (message: string) => void }) {
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    try {
      await updateEvent(detail.id, {
        title: String(form.get('title') || ''),
        eventType: String(form.get('eventType') || ''),
        eventDate: String(form.get('eventDate') || ''),
        academicYear: String(form.get('academicYear') || detail.academicYear || ''),
        location: String(form.get('location') || ''),
        audience: String(form.get('audience') || ''),
        participantCount: Number(form.get('participantCount') || 0),
        goals: String(form.get('goals') || ''),
        summary: String(form.get('summary') || ''),
        outcomes: String(form.get('outcomes') || ''),
        recommendations: String(form.get('recommendations') || ''),
        teacherIds: detail.teachers.map((teacher) => teacher.id),
      });
      await onSaved();
      onMessage('تم تحديث بيانات الفعالية');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث بيانات الفعالية.');
    } finally {
      setSaving(false);
    }
  }

  return <form className="event-edit-form" onSubmit={submit}>
    <div className="event-edit-heading"><div><span className="eyebrow">تحرير السجل</span><h3>بيانات الفعالية ومخرجاتها</h3><p>حدّث التنفيذ والنتائج بعد انتهاء الفعالية دون إنشاء سجل جديد.</p></div><span className="status-pill approved"><Icon name="check" size={14}/> سجل واحد مستمر</span></div>
    <div className="form-grid event-edit-grid">
      <label className="full">عنوان الفعالية<input name="title" required defaultValue={detail.title}/></label>
      <label>نوع الفعالية<select name="eventType" defaultValue={detail.eventType}><option>فعالية</option><option>مسابقة</option><option>مبادرة</option><option>زيارة علمية</option><option>برنامج طلابي</option><option>مشاركة مجتمعية</option></select></label>
      <label>التاريخ<input type="date" name="eventDate" required defaultValue={detail.eventDate}/></label>
      <label>العام الدراسي للسجل<input name="academicYear" required readOnly value={detail.academicYear || ''} dir="ltr"/><small className="field-hint">عام السجل ثابت أثناء تحرير الفعالية.</small></label>
      <label>المكان<input name="location" defaultValue={detail.location || ''}/></label>
      <label>عدد المشاركين<input type="number" name="participantCount" min="0" max="100000" defaultValue={detail.participantCount}/></label>
      <label className="full">الفئة المستهدفة<input name="audience" defaultValue={detail.audience || ''}/></label>
      <label className="full">الأهداف<textarea name="goals" rows={3} defaultValue={detail.goals || ''}/></label>
      <label className="full">وصف التنفيذ<textarea name="summary" rows={4} defaultValue={detail.summary || ''}/></label>
      <label className="full">النتائج والمخرجات<textarea name="outcomes" rows={3} defaultValue={detail.outcomes || ''}/></label>
      <label className="full">التوصيات<textarea name="recommendations" rows={3} defaultValue={detail.recommendations || ''}/></label>
    </div>
    <div className="event-edit-actions"><button type="button" className="ghost-button" onClick={onCancel} disabled={saving}>إلغاء</button><button className="primary-button" disabled={saving}>{saving ? 'جاري الحفظ...' : 'حفظ تحديث الفعالية'}</button></div>
  </form>;
}

function MediaCard({ eventId, media, onReload, onMessage, canMoveEarlier, canMoveLater, onMove }: { eventId: number; media: EventMediaRecord; onReload: () => Promise<void>; onMessage: (message: string) => void; canMoveEarlier: boolean; canMoveLater: boolean; onMove: (direction: -1 | 1) => void }) {
  const [caption, setCaption] = useState(media.caption || '');
  const [busy, setBusy] = useState(false);
  const image = isImage(media);

  async function update(isCover = media.isCover) {
    setBusy(true);
    try {
      await updateEventMedia(eventId, media.id, { caption, position: media.position, isCover });
      await onReload();
      onMessage(isCover && !media.isCover ? 'تم اعتماد صورة الغلاف' : 'تم حفظ وصف الدليل');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر تحديث الدليل.');
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm('حذف هذا الدليل نهائيًا من سجل الفعالية؟')) return;
    setBusy(true);
    try {
      await deleteEventMedia(eventId, media.id);
      await onReload();
      onMessage('تم حذف الدليل');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'تعذر حذف الدليل.');
    } finally { setBusy(false); }
  }

  return <article className={`event-media-card ${media.isCover ? 'cover' : ''}`}>
    <div className="event-media-preview">{image && media.contentUrl ? <img src={media.contentUrl} alt={caption || media.originalName}/> : <div className="file-preview"><Icon name="document" size={30}/><strong>{fileExtension(media.originalName)}</strong></div>}{media.isCover && <span className="cover-badge"><Icon name="check" size={13}/> الغلاف</span>}</div>
    <div className="event-media-body"><strong title={media.originalName}>{media.originalName}</strong><small>{formatBytes(media.sizeBytes)} • {formatDateTime(media.createdAt)}</small><textarea value={caption} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setCaption(event.target.value)} rows={2} placeholder="وصف مختصر للدليل..."/><div className="event-media-actions"><button className="soft-button tiny" onClick={() => void update()} disabled={busy}>حفظ الوصف</button>{image && !media.isCover && <button className="soft-button tiny" onClick={() => void update(true)} disabled={busy}>اجعله الغلاف</button>}{canMoveEarlier && <button className="soft-button tiny" onClick={() => onMove(-1)} disabled={busy}>تقديم</button>}{canMoveLater && <button className="soft-button tiny" onClick={() => onMove(1)} disabled={busy}>تأخير</button>}{(media.webViewLink || media.contentUrl) && <a className="text-button" href={media.webViewLink || media.contentUrl || '#'} target="_blank" rel="noreferrer">فتح</a>}<button className="text-button danger" onClick={() => void remove()} disabled={busy}>حذف</button></div></div>
  </article>;
}

function EventSection({ title, text }: { title: string; text?: string | null }) { return <section className="event-story-card"><span className="eyebrow">{title}</span><p>{text || 'لم يُسجل محتوى لهذا القسم بعد.'}</p></section>; }
function InfoRow({ icon, label, value }: { icon: 'calendar' | 'meeting' | 'teachers'; label: string; value: string }) { return <div className="event-info-row"><span><Icon name={icon} size={18}/></span><div><small>{label}</small><strong>{value}</strong></div></div>; }
function TimelineItem({ title, date }: { title: string; date: string }) { return <div className="timeline-item"><i></i><div><strong>{title}</strong><span>{date}</span></div></div>; }
function isImage(media: EventMediaRecord) { return (media.mimeType || '').startsWith('image/'); }
function fileExtension(name: string) { return name.includes('.') ? name.split('.').pop()?.toUpperCase() || 'FILE' : 'FILE'; }
function formatBytes(bytes: number) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`; return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
function formatDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${value}T12:00:00`)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value)); }
