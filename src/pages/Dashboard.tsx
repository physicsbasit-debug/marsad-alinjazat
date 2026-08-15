import { Icon } from '../components/Icon';
import type { BootstrapData } from '../types';

export function Dashboard({ data, onQuickAction }: { data: BootstrapData; onQuickAction: (action: string) => void }) {
  const d = data.dashboard;
  return (
    <div className="page dashboard-page">
      <header className="hero-block">
        <div>
          <span className="eyebrow">مرصد الإنجازات</span>
          <h1>صباح الخير</h1>
          <p>هذه أهم الأعمال التي تحتاج انتباهك في قسم العلوم اليوم.</p>
        </div>
        <div className="hero-actions">
          <button className="primary-button" onClick={() => onQuickAction('request')}><Icon name="upload" /> طلب ملف</button>
          <button className="soft-button" onClick={() => onQuickAction('event')}><Icon name="spark" /> توثيق فعالية</button>
          <button className="soft-button" onClick={() => onQuickAction('visit')}><Icon name="supervision" /> زيارة</button>
          <button className="soft-button" onClick={() => onQuickAction('meeting')}><Icon name="meeting" /> اجتماع</button>
        </div>
      </header>

      <section className="metric-grid">
        <Metric value={d.lateRequests} label="طلبات متأخرة" tone="danger" icon="alert" />
        <Metric value={d.needsReview} label="بانتظار المراجعة" tone="amber" icon="clock" />
        <Metric value={d.upcomingVisits} label="زيارات قادمة" tone="blue" icon="supervision" />
        <Metric value={d.openDecisions} label="قرارات مفتوحة" tone="teal" icon="meeting" />
      </section>

      <section className="dashboard-grid">
        <article className="panel attention-panel">
          <div className="panel-heading"><div><span className="eyebrow danger">يحتاج انتباهك</span><h2>الأولوية الآن</h2></div><span className="counter">{d.openRequests}</span></div>
          <div className="attention-list">
            {data.requests.filter((item) => ['late', 'review', 'waiting_upload', 'received'].includes(item.status)).slice(0, 4).map((item) => (
              <div className="attention-item" key={item.id}>
                <span className={`attention-dot ${item.status}`}></span>
                <div><strong>{item.title}</strong><small>{item.teacherName} • {item.subject} • {item.grade}</small></div>
                <Icon name="chevron" size={18} />
              </div>
            ))}
          </div>
        </article>

        <article className="panel week-panel">
          <div className="panel-heading"><div><span className="eyebrow">هذا الأسبوع</span><h2>جدول مختصر</h2></div><Icon name="calendar" /></div>
          <div className="week-list">
            <ScheduleItem day="الأحد" title="اجتماع قسم العلوم" meta="10:30 صباحًا" />
            <ScheduleItem day="الثلاثاء" title="زيارة صفية" meta="الحصة الثالثة" />
            <ScheduleItem day="الخميس" title="نشاط علمي" meta="الصف التاسع" />
          </div>
        </article>
      </section>

      <section className="dashboard-grid lower">
        <article className="panel progress-panel">
          <div className="panel-heading"><div><span className="eyebrow">مؤشرات تشغيلية</span><h2>تقدم أعمال المادة</h2></div><span className="quiet-note">محدث اليوم</span></div>
          <Progress label="تنفيذ الخطة" value={d.planProgress} />
          <Progress label="الزيارات والمتابعة" value={d.visitProgress} />
          <Progress label="الطلبات المكتملة" value={d.requestCompletion} />
        </article>
        <article className="panel activity-panel">
          <div className="panel-heading"><div><span className="eyebrow">آخر النشاطات</span><h2>ما حدث مؤخرًا</h2></div></div>
          <div className="activity-list">
            {data.activities.slice(0, 4).map((item) => <div className="activity-row" key={item.id}><span className="activity-icon"><Icon name={item.activity_type === 'event' ? 'spark' : item.activity_type === 'document' ? 'document' : 'upload'} size={18} /></span><div><strong>{item.title}</strong><small>{item.detail}</small></div></div>)}
          </div>
        </article>
      </section>
    </div>
  );
}

function Metric({ value, label, tone, icon }: { value: number; label: string; tone: string; icon: 'alert' | 'clock' | 'supervision' | 'meeting' }) {
  return <article className={`metric-card ${tone}`}><span className="metric-icon"><Icon name={icon} /></span><div><strong>{value}</strong><span>{label}</span></div></article>;
}
function ScheduleItem({ day, title, meta }: { day: string; title: string; meta: string }) {
  return <div className="schedule-item"><span>{day}</span><div><strong>{title}</strong><small>{meta}</small></div></div>;
}
function Progress({ label, value }: { label: string; value: number }) {
  return <div className="progress-row"><div className="progress-meta"><strong>{label}</strong><span>{value}%</span></div><div className="progress-track"><span style={{ width: `${value}%` }} /></div></div>;
}
