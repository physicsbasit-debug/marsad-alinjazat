import { Icon } from '../components/Icon';
import type { BootstrapData } from '../types';

export function Dashboard({ data, onQuickAction }: { data: BootstrapData; onQuickAction: (action: string) => void }) {
  const d = data.dashboard;
  const planningAttention = data.planningAttention.slice(0, 1);
  const achievementAttention = data.achievementAttention.slice(0, Math.max(0, 2 - planningAttention.length));
  const supervisionAttention = data.supervisionAttention.slice(0, Math.max(0, 3 - planningAttention.length - achievementAttention.length));
  const decisionAttention = data.decisionAttention.slice(0, Math.max(0, 4 - planningAttention.length - achievementAttention.length - supervisionAttention.length));
  const requestAttention = data.requests
    .filter((item) => ['late', 'review', 'waiting_upload', 'received'].includes(item.status))
    .slice(0, Math.max(0, 4 - planningAttention.length - achievementAttention.length - supervisionAttention.length - decisionAttention.length));
  const [weekStart, weekEnd] = currentWeekBounds();
  const scheduleEntries = [
    ...data.meetings
      .filter((item) => item.status !== 'cancelled' && item.meetingDate >= weekStart && item.meetingDate <= weekEnd)
      .map((item) => ({ id: `meeting-${item.id}`, date: item.meetingDate, time: item.meetingTime || '', title: item.title, meta: `${item.meetingTime || 'دون وقت'} • ${item.location || 'دون مكان'}` })),
    ...data.visits
      .filter((item) => item.status === 'planned' && item.visitDate >= weekStart && item.visitDate <= weekEnd)
      .map((item) => ({ id: `visit-${item.id}`, date: item.visitDate, time: '', title: `زيارة ${item.teacherName}`, meta: `${item.visitType} • ${item.grade || 'دون صف'}${item.periodLabel ? ` • ${item.periodLabel}` : ''}` })),
  ].sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`)).slice(0, 4);
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
          <div className="panel-heading"><div><span className="eyebrow danger">يحتاج انتباهك</span><h2>الأولوية الآن</h2></div><span className="counter">{d.openRequests + d.openDecisions + data.planningAttention.length + data.supervisionAttention.length + data.achievementAttention.length}</span></div>
          <div className="attention-list">
            {planningAttention.map((item) => <div className="attention-item" key={`planning-${item.id}`}><span className="attention-dot late"></span><div><strong>{item.title}</strong><small>{item.planSubject} • {item.planGrade} • {item.responsibleName || 'دون مسؤول'}{item.plannedEnd ? ` • انتهت ${formatShortDate(item.plannedEnd)}` : ''}</small></div><Icon name="planning" size={18}/></div>)}
            {achievementAttention.map((item) => <div className="attention-item" key={`achievement-${item.id}`}><span className="attention-dot late"></span><div><strong>{item.title}</strong><small>{item.subject} • {item.grade} • إتقان {item.masteryPercent}% من حد {item.masteryThresholdPct}%{item.overdueActionCount ? ` • ${item.overdueActionCount} تدخل متأخر` : ''}</small></div><Icon name="chart" size={18}/></div>)}
            {supervisionAttention.map((item) => <div className="attention-item" key={`supervision-${item.id}`}><span className="attention-dot late"></span><div><strong>{item.teacherName}</strong><small>{item.visitType} • {item.grade || 'دون صف'} • {item.status === 'needs_followup' && item.followupDate ? `متابعة ${formatShortDate(item.followupDate)}` : `زيارة ${formatShortDate(item.visitDate)}`}</small></div><Icon name="supervision" size={18}/></div>)}
            {decisionAttention.map((item) => <div className="attention-item" key={`decision-${item.id}`}><span className={`attention-dot ${item.status === 'overdue' ? 'late' : 'received'}`}></span><div><strong>{item.title}</strong><small>{item.meetingTitle || 'قرار اجتماع'} • {item.responsibleName || 'دون مسؤول'}{item.dueDate ? ` • حتى ${formatShortDate(item.dueDate)}` : ''}</small></div><Icon name="meeting" size={18}/></div>)}
            {requestAttention.map((item) => (
              <div className="attention-item" key={`request-${item.id}`}>
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
            {scheduleEntries.length ? scheduleEntries.map((item) => <ScheduleItem key={item.id} day={weekdayName(item.date)} title={item.title} meta={item.meta} />) : <div className="quiet-note">لا توجد اجتماعات أو زيارات مجدولة هذا الأسبوع.</div>}
          </div>
        </article>
      </section>

      <section className="dashboard-grid lower">
        <article className="panel progress-panel">
          <div className="panel-heading"><div><span className="eyebrow">مؤشرات تشغيلية</span><h2>تقدم أعمال المادة</h2></div><span className="quiet-note">محدث اليوم</span></div>
          <Progress label="تنفيذ الخطة" value={d.planProgress} />
          <Progress label="الزيارات والمتابعة" value={d.visitProgress} />
          <Progress label="الطلبات المكتملة" value={d.requestCompletion} />
          <Progress label="الفئة المحققة للحد المسجل" value={d.achievementMastery} />
        </article>
        <article className="panel activity-panel">
          <div className="panel-heading"><div><span className="eyebrow">آخر النشاطات</span><h2>ما حدث مؤخرًا</h2></div></div>
          <div className="activity-list">
            {data.activities.slice(0, 4).map((item) => <div className="activity-row" key={item.id}><span className="activity-icon"><Icon name={item.activity_type === 'event' ? 'spark' : item.activity_type === 'meeting' ? 'meeting' : item.activity_type === 'planning' ? 'planning' : item.activity_type === 'supervision' ? 'supervision' : item.activity_type === 'achievement' ? 'chart' : item.activity_type === 'document' ? 'document' : 'upload'} size={18} /></span><div><strong>{item.title}</strong><small>{item.detail}</small></div></div>)}
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
function weekdayName(value: string) { return new Intl.DateTimeFormat('ar-OM', { weekday: 'long' }).format(new Date(`${value}T12:00:00`)); }
function formatShortDate(value: string) { return new Intl.DateTimeFormat('ar-OM', { day: 'numeric', month: 'short' }).format(new Date(`${value}T12:00:00`)); }
function currentWeekBounds(): [string, string] {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay());
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
  const format = (date: Date) => { const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return local.toISOString().slice(0, 10); };
  return [format(start), format(end)];
}
