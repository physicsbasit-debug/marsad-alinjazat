import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import {
  createTeacherCvItem,
  deleteTeacherCvItem,
  getTeacherProfile,
  updateTeacherProfile,
} from '../lib/api';
import type {
  CreateTeacherCvItemInput,
  DocumentRecord,
  Teacher,
  TeacherCvItem,
  TeacherCvItemType,
  TeacherProfileDetails,
  UpdateTeacherProfileInput,
  UploadRequest,
  SupervisionVisitRecord,
} from '../types';

export function Teachers({
  teachers,
  requests,
  documents,
  visits,
  academicYear,
  currentAcademicYear,
  onAddTeacher,
  onChanged,
  initialOpenId = null,
  onInitialOpened,
}: {
  teachers: Teacher[];
  requests: UploadRequest[];
  documents: DocumentRecord[];
  visits: SupervisionVisitRecord[];
  academicYear: string;
  currentAcademicYear: string;
  onAddTeacher: () => void;
  onChanged: () => Promise<void>;
  initialOpenId?: number | null;
  onInitialOpened?: () => void;
}) {
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('الكل');
  const [selected, setSelected] = useState<Teacher | null>(null);
  const subjects = ['الكل', ...Array.from(new Set(teachers.map((teacher) => teacher.subject)))];
  useEffect(() => {
    if (!initialOpenId) return;
    const target = teachers.find((teacher) => teacher.id === initialOpenId);
    if (target) setSelected(target);
    onInitialOpened?.();
  }, [initialOpenId, teachers]);

  const visible = useMemo(
    () =>
      teachers.filter((teacher) => {
        const matchSubject = subject === 'الكل' || teacher.subject === subject;
        const q = query.trim();
        const matchQuery = !q || teacher.name.includes(q) || teacher.subject.includes(q) || teacher.specialization?.includes(q);
        return matchSubject && matchQuery;
      }),
    [teachers, query, subject],
  );

  return (
    <div className="page">
      <PageHeader
        eyebrow="الفريق"
        title="المعلمون والسير الذاتية"
        description={academicYear === currentAcademicYear ? "ملف مهني مترابط لكل معلم: بيانات أساسية، سيرة ذاتية، أعمال مقدمة، وإنجازات قابلة للبناء سنة بعد سنة." : `معلمو عام ${academicYear} هم المرتبطون صراحةً بهذا العام أو بسجلاته. الملف المهني الأساسي هو هوية مستمرة ولا يُعامل كلقطة تاريخية لخصائص ذلك العام.`}
        action="إضافة معلم"
        onAction={onAddTeacher}
      />
      <div className="toolbar modern-toolbar">
        <div className="filter-row">
          {subjects.map((item) => (
            <button key={item} className={`filter-chip ${subject === item ? 'active' : ''}`} onClick={() => setSubject(item)}>
              {item}
            </button>
          ))}
        </div>
        <label className="inline-search">
          <Icon name="search" size={18} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="ابحث باسم المعلم أو التخصص..." />
        </label>
      </div>
      <div className="teacher-grid">
        {visible.map((teacher) => {
          const requestCount = requests.filter((item) => item.teacherId === teacher.id).length;
          const documentCount = documents.filter((item) => item.teacherId === teacher.id).length;
          return (
            <article className="teacher-card" key={teacher.id}>
              <div className="teacher-top">
                <div className="avatar xl">{teacher.name[0]}</div>
                <div>
                  <h3>{teacher.name}</h3>
                  <p>معلم {teacher.subject} • {teacher.experienceYears} سنة خبرة</p>
                </div>
                <button className="icon-button" aria-label="خيارات المعلم"><Icon name="more" /></button>
              </div>
              <div className="teacher-facts">
                <div><strong>{teacher.workload}</strong><span>النصاب</span></div>
                <div><strong>{requestCount}</strong><span>الطلبات</span></div>
                <div><strong>{documentCount}</strong><span>الملفات</span></div>
              </div>
              <div className="completion-head"><span>اكتمال السيرة المهنية</span><strong>{teacher.cvCompletion}%</strong></div>
              <div className="mini-progress"><span style={{ width: `${teacher.cvCompletion}%` }} /></div>
              <div className="card-footer">
                <StatusPill complete={teacher.cvCompletion >= 90} />
                <button className="text-button" onClick={() => setSelected(teacher)}>عرض الملف <Icon name="arrow" size={16} /></button>
              </div>
            </article>
          );
        })}
      </div>
      <Modal open={!!selected} onClose={() => setSelected(null)}>
        {selected && (
          <TeacherProfile
            teacher={selected}
            requests={requests.filter((item) => item.teacherId === selected.id)}
            documents={documents.filter((item) => item.teacherId === selected.id)}
            visits={visits.filter((item) => item.teacherId === selected.id)}
            onChanged={onChanged}
            historicalContext={academicYear !== currentAcademicYear}
            academicYear={academicYear}
          />
        )}
      </Modal>
    </div>
  );
}

type ProfileTab = 'overview' | 'cv' | 'works' | 'visits' | 'achievements';

function TeacherProfile({
  teacher,
  requests,
  documents,
  visits,
  onChanged,
  historicalContext,
  academicYear,
}: {
  teacher: Teacher;
  requests: UploadRequest[];
  documents: DocumentRecord[];
  visits: SupervisionVisitRecord[];
  onChanged: () => Promise<void>;
  historicalContext: boolean;
  academicYear: string;
}) {
  const [details, setDetails] = useState<TeacherProfileDetails | null>(null);
  const [activeTab, setActiveTab] = useState<ProfileTab>('overview');
  const [editing, setEditing] = useState(false);
  const [addingItem, setAddingItem] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setMessage('');
    try {
      setDetails(await getTeacherProfile(teacher.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر تحميل الملف المهني.');
    }
  }

  useEffect(() => {
    setActiveTab('overview');
    setEditing(false);
    setAddingItem(false);
    void load();
  }, [teacher.id]);

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!details) return;
    const form = new FormData(event.currentTarget);
    const schoolJoinYearRaw = String(form.get('schoolJoinYear') || '').trim();
    const payload: UpdateTeacherProfileInput = {
      name: String(form.get('name') || ''),
      subject: String(form.get('subject') || ''),
      specialization: String(form.get('specialization') || ''),
      qualification: String(form.get('qualification') || ''),
      experienceYears: Number(form.get('experienceYears') || 0),
      workload: Number(form.get('workload') || 0),
      email: String(form.get('email') || ''),
      phone: String(form.get('phone') || ''),
      employeeNumber: String(form.get('employeeNumber') || ''),
      schoolJoinYear: schoolJoinYearRaw ? Number(schoolJoinYearRaw) : null,
      grades: String(form.get('grades') || ''),
      responsibilities: String(form.get('responsibilities') || ''),
      professionalSummary: String(form.get('professionalSummary') || ''),
    };
    setBusy(true);
    setMessage('');
    try {
      await updateTeacherProfile(teacher.id, payload);
      await load();
      await onChanged();
      setEditing(false);
      setMessage('تم تحديث الملف المهني بنجاح.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر حفظ الملف المهني.');
    } finally {
      setBusy(false);
    }
  }

  async function addCvItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const startYearRaw = String(form.get('startYear') || '').trim();
    const endYearRaw = String(form.get('endYear') || '').trim();
    const payload: CreateTeacherCvItemInput = {
      itemType: String(form.get('itemType')) as TeacherCvItemType,
      title: String(form.get('title') || ''),
      organization: String(form.get('organization') || ''),
      startYear: startYearRaw ? Number(startYearRaw) : null,
      endYear: endYearRaw ? Number(endYearRaw) : null,
      description: String(form.get('description') || ''),
    };
    setBusy(true);
    setMessage('');
    try {
      await createTeacherCvItem(teacher.id, payload);
      formElement.reset();
      await load();
      await onChanged();
      setAddingItem(false);
      setMessage('تمت إضافة بند السيرة المهنية.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر إضافة بند السيرة.');
    } finally {
      setBusy(false);
    }
  }

  async function removeCvItem(item: TeacherCvItem) {
    if (!window.confirm(`حذف «${item.title}» من السيرة المهنية؟`)) return;
    setBusy(true);
    setMessage('');
    try {
      await deleteTeacherCvItem(teacher.id, item.id);
      await load();
      await onChanged();
      setMessage('تم حذف البند.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'تعذر حذف البند.');
    } finally {
      setBusy(false);
    }
  }

  if (!details) {
    return <div className="profile-loading"><div className="spinner" /><p>{message || 'جاري تحميل الملف المهني...'}</p></div>;
  }

  const current = details.teacher;
  const achievementItems = details.cvItems.filter((item) => item.itemType === 'achievement');

  return (
    <div className="profile-view profile-shell">
      <div className="profile-hero profile-hero-modern">
        <div className="avatar hero-avatar">{current.name[0]}</div>
        <div className="profile-identity">
          <span className="eyebrow">الملف المهني</span>
          <h2>{current.name}</h2>
          <p>معلم {current.subject} • {current.specialization || current.subject}</p>
        </div>
        <div className="profile-header-actions">
          <span className="profile-completion"><strong>{current.cvCompletion}%</strong><small>اكتمال السيرة</small></span>
          {!historicalContext && <button className="soft-button" onClick={() => setEditing((value) => !value)}><Icon name="user" size={17} /> {editing ? 'إلغاء التعديل' : 'تحديث البيانات'}</button>}
        </div>
      </div>

      {historicalContext && <div className="quiet-note">عرض عام {academicYear}: الأعمال والزيارات أدناه تخص هذا العام، أما بيانات الهوية المهنية الأساسية فتمثل الملف المستمر الحالي ولا تُعد لقطة تاريخية مفترضة.</div>}

      <div className="profile-tabs" role="tablist" aria-label="أقسام الملف المهني">
        <Tab id="overview" current={activeTab} onSelect={setActiveTab}>نظرة عامة</Tab>
        <Tab id="cv" current={activeTab} onSelect={setActiveTab}>السيرة الذاتية</Tab>
        <Tab id="works" current={activeTab} onSelect={setActiveTab}>الأعمال</Tab>
        <Tab id="visits" current={activeTab} onSelect={setActiveTab}>الزيارات</Tab>
        <Tab id="achievements" current={activeTab} onSelect={setActiveTab}>الإنجازات</Tab>
      </div>

      {message && <div className={`profile-message ${message.includes('تعذر') || message.includes('معاينة') ? 'warning' : ''}`}>{message}</div>}

      {editing ? (
        <ProfileEditForm details={details} busy={busy} onSubmit={saveProfile} />
      ) : activeTab === 'overview' ? (
        <Overview details={details} />
      ) : activeTab === 'cv' ? (
        <CvSection details={details} busy={busy} addingItem={addingItem} setAddingItem={setAddingItem} onAdd={addCvItem} onDelete={removeCvItem} />
      ) : activeTab === 'works' ? (
        <WorksSection requests={requests} documents={documents} stats={details.stats} />
      ) : activeTab === 'visits' ? (
        <VisitsSection visits={visits} stats={details.stats} />
      ) : (
        <AchievementsSection items={achievementItems} onAdd={() => { setActiveTab('cv'); setAddingItem(true); }} />
      )}
    </div>
  );
}

function Tab({ id, current, onSelect, children }: { id: ProfileTab; current: ProfileTab; onSelect: (id: ProfileTab) => void; children: string }) {
  return <button className={current === id ? 'active' : ''} onClick={() => onSelect(id)}>{children}</button>;
}

function Overview({ details }: { details: TeacherProfileDetails }) {
  const { teacher, profile, stats } = details;
  return (
    <div className="profile-panel">
      <div className="profile-stats">
        <div><strong>{stats.requestCount}</strong><span>طلبات ملفات</span></div>
        <div><strong>{stats.documentCount}</strong><span>ملفات مرتبطة</span></div>
        <div><strong>{stats.approvedDocumentCount}</strong><span>ملفات معتمدة</span></div>
        <div><strong>{stats.visitCount}</strong><span>زيارات إشرافية</span></div>
      </div>
      <div className="profile-summary-card">
        <span className="eyebrow">نبذة مهنية</span>
        <p>{profile.professionalSummary || 'لم تُضف نبذة مهنية بعد. يمكن تحديثها من زر «تحديث البيانات».'}</p>
      </div>
      <div className="profile-info-grid profile-info-grid-three">
        <Info label="المؤهل" value={teacher.qualification || 'غير مسجل'} />
        <Info label="سنوات الخبرة" value={`${teacher.experienceYears} سنة`} />
        <Info label="التخصص" value={teacher.specialization || teacher.subject} />
        <Info label="الرقم الوظيفي" value={profile.employeeNumber || 'غير مسجل'} />
        <Info label="الصفوف الحالية" value={profile.grades || 'غير مسجلة'} />
        <Info label="الالتحاق بالمدرسة" value={profile.schoolJoinYear ? String(profile.schoolJoinYear) : 'غير مسجل'} />
      </div>
      <div className="profile-section-card">
        <div className="profile-section-title"><span><Icon name="planning" size={18} /></span><div><strong>المسؤوليات الحالية</strong><small>المهام والأدوار التي يتولاها المعلم داخل المادة</small></div></div>
        <p>{profile.responsibilities || 'لا توجد مسؤوليات إضافية مسجلة.'}</p>
      </div>
    </div>
  );
}

function ProfileEditForm({ details, busy, onSubmit }: { details: TeacherProfileDetails; busy: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  const { teacher, profile } = details;
  return (
    <form className="profile-edit-form" onSubmit={onSubmit}>
      <div className="profile-edit-heading"><div><strong>تحديث الملف المهني</strong><p>هذه البيانات هي المصدر المنظم للسيرة المهنية، ولا تؤثر على ملفات Drive أو طلبات التسليم.</p></div><span className="status-pill approved"><Icon name="check" size={14} /> محفوظ مركزيًا</span></div>
      <div className="form-grid profile-edit-grid">
        <label className="full">اسم المعلم<input name="name" required defaultValue={teacher.name} /></label>
        <label>المادة<select name="subject" defaultValue={teacher.subject}><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label>
        <label>التخصص<input name="specialization" defaultValue={teacher.specialization || ''} /></label>
        <label className="full">المؤهل<input name="qualification" defaultValue={teacher.qualification || ''} /></label>
        <label>سنوات الخبرة<input type="number" min="0" max="60" name="experienceYears" defaultValue={teacher.experienceYears} /></label>
        <label>النصاب<input type="number" min="0" max="40" name="workload" defaultValue={teacher.workload} /></label>
        <label>الرقم الوظيفي<input name="employeeNumber" defaultValue={profile.employeeNumber || ''} /></label>
        <label>سنة الالتحاق بالمدرسة<input type="number" min="1950" max="2100" name="schoolJoinYear" defaultValue={profile.schoolJoinYear || ''} /></label>
        <label>البريد<input type="email" name="email" defaultValue={teacher.email || ''} /></label>
        <label>الهاتف<input name="phone" defaultValue={teacher.phone || ''} /></label>
        <label className="full">الصفوف الحالية<input name="grades" defaultValue={profile.grades || ''} placeholder="مثال: الثامن، التاسع، العاشر" /></label>
        <label className="full">المسؤوليات<textarea name="responsibilities" rows={3} defaultValue={profile.responsibilities || ''} /></label>
        <label className="full">نبذة مهنية<textarea name="professionalSummary" rows={4} defaultValue={profile.professionalSummary || ''} placeholder="نبذة مختصرة عن خبرة المعلم ومجالات تميزه المهني..." /></label>
      </div>
      <div className="profile-form-actions"><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : 'حفظ التحديثات'}</button></div>
    </form>
  );
}

function CvSection({
  details,
  busy,
  addingItem,
  setAddingItem,
  onAdd,
  onDelete,
}: {
  details: TeacherProfileDetails;
  busy: boolean;
  addingItem: boolean;
  setAddingItem: (value: boolean) => void;
  onAdd: (event: React.FormEvent<HTMLFormElement>) => void;
  onDelete: (item: TeacherCvItem) => void;
}) {
  const grouped = useMemo(() => ({
    qualification: details.cvItems.filter((item) => item.itemType === 'qualification'),
    experience: details.cvItems.filter((item) => item.itemType === 'experience'),
    course: details.cvItems.filter((item) => item.itemType === 'course'),
    achievement: details.cvItems.filter((item) => item.itemType === 'achievement'),
  }), [details.cvItems]);

  return (
    <div className="profile-panel">
      <div className="profile-section-head">
        <div><span className="eyebrow">السيرة المنظمة</span><h3>المؤهلات والخبرات والتطوير المهني</h3></div>
        <button className="soft-button" onClick={() => setAddingItem(!addingItem)}><Icon name="plus" size={16} /> {addingItem ? 'إغلاق' : 'إضافة بند'}</button>
      </div>
      {addingItem && <CvItemForm busy={busy} onSubmit={onAdd} />}
      <CvGroup title="المؤهلات العلمية" items={grouped.qualification} onDelete={onDelete} />
      <CvGroup title="الخبرات والمسؤوليات السابقة" items={grouped.experience} onDelete={onDelete} />
      <CvGroup title="البرامج والدورات التدريبية" items={grouped.course} onDelete={onDelete} />
      <CvGroup title="الإنجازات المهنية" items={grouped.achievement} onDelete={onDelete} />
    </div>
  );
}

function CvItemForm({ busy, onSubmit }: { busy: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return (
    <form className="cv-item-form" onSubmit={onSubmit}>
      <div className="form-grid">
        <label>نوع البند<select name="itemType"><option value="qualification">مؤهل علمي</option><option value="experience">خبرة أو مسؤولية</option><option value="course">برنامج تدريبي</option><option value="achievement">إنجاز مهني</option></select></label>
        <label>الجهة<input name="organization" placeholder="الجامعة / الجهة / المدرسة" /></label>
        <label className="full">العنوان<input name="title" required placeholder="عنوان المؤهل أو الدورة أو الإنجاز" /></label>
        <label>سنة البداية<input type="number" min="1950" max="2100" name="startYear" /></label>
        <label>سنة النهاية<input type="number" min="1950" max="2100" name="endYear" /></label>
        <label className="full">وصف مختصر<textarea name="description" rows={2} /></label>
      </div>
      <div className="profile-form-actions"><button className="primary-button" disabled={busy}>{busy ? 'جاري الحفظ...' : 'إضافة إلى السيرة'}</button></div>
    </form>
  );
}

function CvGroup({ title, items, onDelete }: { title: string; items: TeacherCvItem[]; onDelete: (item: TeacherCvItem) => void }) {
  return (
    <section className="cv-group">
      <div className="cv-group-heading"><h4>{title}</h4><span>{items.length}</span></div>
      {items.length ? <div className="cv-list">{items.map((item) => <CvItem key={item.id} item={item} onDelete={onDelete} />)}</div> : <div className="empty-state-compact">لا توجد بيانات مسجلة في هذا القسم بعد.</div>}
    </section>
  );
}

function CvItem({ item, onDelete }: { item: TeacherCvItem; onDelete: (item: TeacherCvItem) => void }) {
  const years = item.startYear || item.endYear ? `${item.startYear || '—'}${item.endYear && item.endYear !== item.startYear ? ` – ${item.endYear}` : ''}` : '';
  return (
    <article className="cv-item">
      <span className={`cv-item-mark ${item.itemType}`}><Icon name={item.itemType === 'achievement' ? 'spark' : item.itemType === 'course' ? 'planning' : 'document'} size={17} /></span>
      <div><strong>{item.title}</strong><p>{[item.organization, years].filter(Boolean).join(' • ') || 'بدون جهة أو تاريخ'}</p>{item.description && <small>{item.description}</small>}</div>
      <button className="danger-text-button" onClick={() => onDelete(item)} type="button">حذف</button>
    </article>
  );
}

function WorksSection({ requests, documents, stats }: { requests: UploadRequest[]; documents: DocumentRecord[]; stats: TeacherProfileDetails['stats'] }) {
  return (
    <div className="profile-panel">
      <div className="profile-stats">
        <div><strong>{stats.requestCount}</strong><span>طلبات مرتبطة</span></div>
        <div><strong>{stats.documentCount}</strong><span>ملفات مستلمة</span></div>
        <div><strong>{stats.approvedDocumentCount}</strong><span>ملفات معتمدة</span></div>
      </div>
      <div className="profile-section-head compact"><div><span className="eyebrow">الأعمال</span><h3>آخر الطلبات والملفات المرتبطة بالمعلم</h3></div></div>
      <div className="teacher-work-list">
        {requests.slice(0, 6).map((item) => <div key={`r-${item.id}`}><span className="work-icon"><Icon name="upload" size={16} /></span><div><strong>{item.title}</strong><small>{item.requestType} • {item.subject} • {item.grade}</small></div><StatusPillByStatus status={item.status} /></div>)}
        {documents.slice(0, 6).map((item) => <div key={`d-${item.id}`}><span className="work-icon"><Icon name="document" size={16} /></span><div><strong>{item.title}</strong><small>{item.originalName}</small></div><span className={`status-pill ${item.status === 'approved' ? 'approved' : 'received'}`}>{item.status === 'approved' ? 'معتمد' : 'مستلم'}</span></div>)}
        {!requests.length && !documents.length && <div className="empty-state-compact">لا توجد أعمال مرتبطة بهذا المعلم بعد.</div>}
      </div>
    </div>
  );
}

function VisitsSection({ visits, stats }: { visits: SupervisionVisitRecord[]; stats: TeacherProfileDetails['stats'] }) {
  const labels: Record<string, string> = { planned: 'مخططة', completed: 'منفذة', needs_followup: 'تحتاج متابعة', closed: 'مغلقة', overdue: 'متأخرة' };
  return (
    <div className="profile-panel">
      <div className="profile-stats">
        <div><strong>{stats.visitCount}</strong><span>إجمالي الزيارات</span></div>
        <div><strong>{visits.filter((item) => item.status !== 'planned').length}</strong><span>زيارات منفذة</span></div>
        <div><strong>{stats.openFollowupCount}</strong><span>متابعات مفتوحة</span></div>
      </div>
      <div className="profile-section-head compact"><div><span className="eyebrow">الإشراف الفني</span><h3>سجل الزيارات المرتبط بالمعلم</h3></div></div>
      <div className="teacher-visit-list">
        {visits.map((visit) => <article key={visit.id} className={visit.effectiveStatus === 'overdue' ? 'overdue' : ''}><span className="work-icon"><Icon name="supervision" size={16}/></span><div><strong>{visit.lessonTitle || visit.visitType}</strong><small>{visit.visitType} • {visit.grade || 'دون صف'} • {formatProfileDate(visit.visitDate)}</small></div><span className={`status-pill ${visit.effectiveStatus === 'closed' ? 'approved' : visit.effectiveStatus === 'overdue' ? 'late' : 'review'}`}>{labels[visit.effectiveStatus]}</span></article>)}
        {!visits.length && <div className="empty-state-compact">لا توجد زيارات إشرافية مرتبطة بهذا المعلم بعد.</div>}
      </div>
    </div>
  );
}

function formatProfileDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)); }

function AchievementsSection({ items, onAdd }: { items: TeacherCvItem[]; onAdd: () => void }) {
  return (
    <div className="profile-panel">
      <div className="profile-section-head"><div><span className="eyebrow">الإنجازات</span><h3>سجل الإنجازات المهنية</h3><p>يظهر هنا ما يوثق إسهامات المعلم ومبادراته وتميزه المهني.</p></div><button className="soft-button" onClick={onAdd}><Icon name="plus" size={16} /> إضافة إنجاز</button></div>
      {items.length ? <div className="achievement-list">{items.map((item) => <article key={item.id}><span><Icon name="spark" size={19} /></span><div><strong>{item.title}</strong><p>{item.organization || 'إنجاز مهني'}{item.startYear ? ` • ${item.startYear}` : ''}</p>{item.description && <small>{item.description}</small>}</div></article>)}</div> : <div className="achievement-empty"><Icon name="spark" size={25} /><strong>لا توجد إنجازات مسجلة بعد</strong><p>أضف الإنجازات المهنية لتصبح جزءًا من السيرة وملف الإنجاز.</p></div>}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) { return <div className="info-box"><span>{label}</span><strong>{value}</strong></div>; }
function StatusPill({ complete }: { complete: boolean }) { return <span className={`status-pill ${complete ? 'approved' : 'waiting_upload'}`}><Icon name={complete ? 'check' : 'clock'} size={14} />{complete ? 'السيرة مكتملة' : 'تحتاج تحديث'}</span>; }
function StatusPillByStatus({ status }: { status: UploadRequest['status'] }) {
  const labels: Record<UploadRequest['status'], string> = { waiting_upload: 'بانتظار الرفع', received: 'مستلم', review: 'للمراجعة', approved: 'معتمد', needs_revision: 'يحتاج تعديل', late: 'متأخر', cancelled: 'ملغي' };
  return <span className={`status-pill ${status}`}>{labels[status]}</span>;
}
export function PageHeader({ eyebrow, title, description, action, onAction }: { eyebrow: string; title: string; description: string; action?: string; onAction?: () => void }) { return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action && <button className="soft-button" onClick={onAction}><Icon name="plus" /> {action}</button>}</header>; }
