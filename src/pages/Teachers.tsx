import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import type { Teacher } from '../types';

export function Teachers({ teachers, onAddTeacher }: { teachers: Teacher[]; onAddTeacher: () => void }) {
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('الكل');
  const [selected, setSelected] = useState<Teacher | null>(null);
  const subjects = ['الكل', ...Array.from(new Set(teachers.map((teacher) => teacher.subject)))];
  const visible = useMemo(() => teachers.filter((teacher) => {
    const matchSubject = subject === 'الكل' || teacher.subject === subject;
    const q = query.trim();
    const matchQuery = !q || teacher.name.includes(q) || teacher.subject.includes(q);
    return matchSubject && matchQuery;
  }), [teachers, query, subject]);

  return (
    <div className="page">
      <PageHeader eyebrow="الفريق" title="المعلمون والسير الذاتية" description="ملف مهني واضح لكل معلم، من السيرة والمؤهلات إلى الأعمال والزيارات والإنجازات." action="إضافة معلم" onAction={onAddTeacher} />
      <div className="toolbar modern-toolbar">
        <div className="filter-row">{subjects.map((item) => <button key={item} className={`filter-chip ${subject === item ? 'active' : ''}`} onClick={() => setSubject(item)}>{item}</button>)}</div>
        <label className="inline-search"><Icon name="search" size={18}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="ابحث باسم المعلم..." /></label>
      </div>
      <div className="teacher-grid">
        {visible.map((teacher) => (
          <article className="teacher-card" key={teacher.id}>
            <div className="teacher-top"><div className="avatar xl">{teacher.name[0]}</div><div><h3>{teacher.name}</h3><p>معلم {teacher.subject} • {teacher.experienceYears} سنة خبرة</p></div><button className="icon-button"><Icon name="more" /></button></div>
            <div className="teacher-facts"><div><strong>{teacher.workload}</strong><span>النصاب</span></div><div><strong>{teacher.experienceYears}</strong><span>الخبرة</span></div><div><strong>{teacher.cvCompletion}%</strong><span>السيرة</span></div></div>
            <div className="completion-head"><span>اكتمال السيرة المهنية</span><strong>{teacher.cvCompletion}%</strong></div>
            <div className="mini-progress"><span style={{ width: `${teacher.cvCompletion}%` }} /></div>
            <div className="card-footer"><StatusPill complete={teacher.cvCompletion >= 90}/><button className="text-button" onClick={() => setSelected(teacher)}>عرض الملف <Icon name="arrow" size={16}/></button></div>
          </article>
        ))}
      </div>
      <Modal open={!!selected} onClose={() => setSelected(null)}>
        {selected && <TeacherProfile teacher={selected} />}
      </Modal>
    </div>
  );
}

function TeacherProfile({ teacher }: { teacher: Teacher }) {
  return <div className="profile-view"><div className="profile-hero"><div className="avatar hero-avatar">{teacher.name[0]}</div><div><span className="eyebrow">الملف المهني</span><h2>{teacher.name}</h2><p>معلم {teacher.subject} • {teacher.specialization}</p></div></div><div className="profile-tabs"><button className="active">نظرة عامة</button><button>السيرة الذاتية</button><button>الأعمال</button><button>الزيارات</button><button>الإنجازات</button></div><div className="profile-info-grid"><Info label="المؤهل" value={teacher.qualification || 'غير مسجل'} /><Info label="سنوات الخبرة" value={`${teacher.experienceYears} سنة`} /><Info label="التخصص" value={teacher.specialization || teacher.subject} /><Info label="البريد" value={teacher.email || 'غير مسجل'} /></div><div className="profile-callout"><div><strong>اكتمال السيرة الذاتية</strong><p>السيرة تُبنى من بيانات المعلم وتبقى قابلة للتصدير لاحقًا بتصميم موحد.</p></div><span>{teacher.cvCompletion}%</span></div></div>;
}
function Info({ label, value }: { label: string; value: string }) { return <div className="info-box"><span>{label}</span><strong>{value}</strong></div>; }
function StatusPill({ complete }: { complete: boolean }) { return <span className={`status-pill ${complete ? 'approved' : 'waiting_upload'}`}><Icon name={complete ? 'check' : 'clock'} size={14}/>{complete ? 'السيرة مكتملة' : 'تحتاج تحديث'}</span>; }
export function PageHeader({ eyebrow, title, description, action, onAction }: { eyebrow: string; title: string; description: string; action?: string; onAction?: () => void }) { return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action && <button className="soft-button" onClick={onAction}><Icon name="plus"/> {action}</button>}</header>; }
