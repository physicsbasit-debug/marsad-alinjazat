import { Icon } from '../components/Icon';
import type { EventRecord } from '../types';
import { PageHeader } from './Teachers';

export function Events({ events, onAddEvent }: { events: EventRecord[]; onAddEvent: () => void }) {
  return <div className="page"><PageHeader eyebrow="الذاكرة البصرية" title="الفعاليات والتوثيق" description="سجل فعالية متكامل: الهدف، التنفيذ، النتائج، الصور والأدلة، ثم تقرير جاهز عند الحاجة." action="توثيق فعالية" onAction={onAddEvent} />
    <div className="feature-banner"><div className="banner-icon"><Icon name="image" size={28}/></div><div><strong>التوثيق هنا ليس مجلد صور</strong><p>كل فعالية تحفظ كسجل تربوي قابل للبحث والتقرير والرجوع إليه عبر السنوات.</p></div></div>
    <div className="event-grid">{events.map(event=><article className="event-card" key={event.id}><div className={`event-cover ${event.coverTone}`}><span className="event-date"><Icon name="calendar" size={15}/>{new Intl.DateTimeFormat('ar-OM',{day:'numeric',month:'long',year:'numeric'}).format(new Date(`${event.eventDate}T12:00:00`))}</span><span className="event-type">{event.eventType}</span></div><div className="event-body"><h3>{event.title}</h3><p>{event.summary || event.goals || 'فعالية موثقة ضمن سجل المادة.'}</p><div className="event-meta"><span><Icon name="teachers" size={16}/>{event.participantCount} مشاركًا</span><span><Icon name="image" size={16}/>{event.mediaCount || 0} دليلًا</span></div><div className="card-footer"><span className="status-pill approved"><Icon name="check" size={14}/> موثق</span><button className="text-button">عرض الفعالية <Icon name="arrow" size={16}/></button></div></div></article>)}</div>
  </div>;
}
