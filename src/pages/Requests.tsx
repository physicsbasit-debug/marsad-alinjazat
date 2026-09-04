import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import type { RequestStatus, UploadRequest } from '../types';
import { PageHeader } from './Teachers';

const labels: Record<RequestStatus, string> = {
  waiting_upload: 'بانتظار الرفع', received: 'تم الاستلام', review: 'للمراجعة', approved: 'معتمد', needs_revision: 'يحتاج تعديل', late: 'متأخر', cancelled: 'ملغي',
};

export function Requests({ requests, onNewRequest, onStatus, canCreate = true, sourceNotice }: { requests: UploadRequest[]; onNewRequest: () => void; onStatus: (id: number, status: RequestStatus) => Promise<void>; canCreate?: boolean; sourceNotice?: string }) {
  const [filter, setFilter] = useState<'all' | RequestStatus>('all');
  const [query, setQuery] = useState('');
  const visible = useMemo(() => requests.filter((item) => (filter === 'all' || item.status === filter) && `${item.title} ${item.teacherName} ${item.subject}`.includes(query.trim())), [requests, filter, query]);
  return <div className="page"><PageHeader eyebrow="الاستلام والمتابعة" title="طلبات الملفات" description="اطلب الملف مرة واحدة، شارك الرابط، واستلمه في صندوق المراجعة مع تتبع واضح للحالة." />
    {sourceNotice&&<div className="quiet-note">{sourceNotice}</div>}<div className="request-toolbar"><button className="primary-button" onClick={onNewRequest} disabled={!canCreate} title={!canCreate?'إنشاء الرابط ينتظر مرحلة الرفع العام والتخزين.':undefined}><Icon name="plus"/> {canCreate?'طلب جديد':'إنشاء الطلب مؤجل'}</button><div className="filter-row"><Filter value="all" current={filter} set={setFilter} label="الكل"/><Filter value="waiting_upload" current={filter} set={setFilter} label="بانتظار الرفع"/><Filter value="review" current={filter} set={setFilter} label="للمراجعة"/><Filter value="approved" current={filter} set={setFilter} label="معتمد"/><Filter value="late" current={filter} set={setFilter} label="متأخر"/></div><label className="inline-search"><Icon name="search" size={18}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="ابحث في الطلبات..." /></label></div>
    <div className="table-shell"><table className="data-table"><thead><tr><th>المطلوب</th><th>المعلم</th><th>الموعد</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>{visible.map((item)=><tr key={item.id}><td><div className="cell-title"><strong>{item.title}</strong><span>{item.requestType} • {item.subject} • الصف {item.grade}</span></div></td><td>{item.teacherName}</td><td>{formatDate(item.deadline)}</td><td><span className={`status-pill ${item.status}`}>{labels[item.status]}</span></td><td>{item.status === 'review' || item.status === 'received' ? <button className="approve-button" onClick={()=>onStatus(item.id,'approved')}><Icon name="check" size={15}/> اعتماد</button> : <button className="icon-button"><Icon name="more"/></button>}</td></tr>)}</tbody></table>{visible.length===0&&<div className="empty-state">لا توجد طلبات مطابقة.</div>}</div>
  </div>;
}
function Filter({ value, current, set, label }: { value: 'all' | RequestStatus; current: 'all' | RequestStatus; set: (v:'all'|RequestStatus)=>void; label:string }) { return <button className={`filter-chip ${current===value?'active':''}`} onClick={()=>set(value)}>{label}</button>; }
function formatDate(date?: string | null) { if(!date) return 'بدون موعد'; return new Intl.DateTimeFormat('ar-OM',{day:'numeric',month:'short'}).format(new Date(`${date}T12:00:00`)); }
