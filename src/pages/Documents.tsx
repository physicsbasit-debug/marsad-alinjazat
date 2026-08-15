import { Icon } from '../components/Icon';
import type { DocumentRecord } from '../types';
import { PageHeader } from './Teachers';

export function Documents({ documents }: { documents: DocumentRecord[] }) {
  return <div className="page"><PageHeader eyebrow="المكتبة المؤسسية" title="الوثائق والمراجع" description="الملف في Drive، أما هنا فالمعنى: نوعه، مادته، صفه، صاحبه، سنته وحالته." action="إضافة وثيقة" />
    {documents.length===0?<div className="library-empty"><div className="empty-illustration"><Icon name="document" size={36}/></div><h2>المكتبة جاهزة لأول ملف حقيقي</h2><p>أول ملف يصل عبر رابط طلب سيظهر هنا تلقائيًا بعد الرفع، بدل إضافة عينات مزيفة إلى قاعدة البيانات.</p></div>:
    <div className="document-grid">{documents.map(doc=><article className="document-card" key={doc.id}><span className="doc-icon"><Icon name="document"/></span><div><strong>{doc.title}</strong><p>{doc.originalName}</p><small>{doc.subject} • {doc.grade} • {doc.academicYear}</small></div>{doc.webViewLink?<a href={doc.webViewLink} target="_blank" rel="noreferrer" className="icon-button"><Icon name="external"/></a>:<span className="local-badge">محلي</span>}</article>)}</div>}
  </div>;
}
