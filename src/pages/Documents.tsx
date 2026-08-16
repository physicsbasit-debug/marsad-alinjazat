import { useState } from 'react';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { uploadDirectDocument } from '../lib/api';
import type { DirectDocumentInput, DocumentRecord, Teacher } from '../types';
import { PageHeader } from './Teachers';

export function Documents({
  documents,
  teachers,
  academicYear,
  onRefresh,
}: {
  documents: DocumentRecord[];
  teachers: Teacher[];
  academicYear: string;
  onRefresh: () => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  return <div className="page"><PageHeader eyebrow="المكتبة المؤسسية" title="الوثائق والمراجع" description="الملف في Drive، أما هنا فالمعنى: نوعه، مادته، صفه، صاحبه، سنته وحالته." action="إضافة وثيقة" onAction={()=>setAdding(true)} />
    {documents.length===0?<div className="library-empty"><div className="empty-illustration"><Icon name="document" size={36}/></div><h2>لا توجد وثائق لهذا العام</h2><p>يمكن رفع وثيقة مباشرة لهذا العام، أو ستظهر الملفات المستلمة عبر طلبات الملفات تلقائيًا.</p></div>:
    <div className="document-grid">{documents.map(doc=><article className="document-card" key={doc.id}><span className="doc-icon"><Icon name="document"/></span><div><strong>{doc.title}</strong><p>{doc.originalName}</p><small>{[doc.subject,doc.grade,doc.academicYear].filter(Boolean).join(' • ')}</small></div>{doc.webViewLink?<a href={doc.webViewLink} target="_blank" rel="noreferrer" className="icon-button"><Icon name="external"/></a>:<span className="local-badge">محلي</span>}</article>)}</div>}
    <DirectDocumentModal open={adding} teachers={teachers} academicYear={academicYear} onClose={()=>setAdding(false)} onCreated={async()=>{setAdding(false);await onRefresh();}}/>
  </div>;
}

function DirectDocumentModal({
  open,
  teachers,
  academicYear,
  onClose,
  onCreated,
}: {
  open: boolean;
  teachers: Teacher[];
  academicYear: string;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');

  async function submit(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();
    const formElement=event.currentTarget;
    const form=new FormData(formElement);
    const file=form.get('file');
    if(!(file instanceof File)||!file.size){setMessage('اختر ملفًا للوثيقة.');return;}
    const teacherRaw=String(form.get('teacherId')||'').trim();
    const input:DirectDocumentInput={
      title:String(form.get('title')||''),
      category:String(form.get('category')||'وثيقة'),
      academicYear:String(form.get('academicYear')||''),
      teacherId:teacherRaw?Number(teacherRaw):null,
      subject:String(form.get('subject')||''),
      grade:String(form.get('grade')||''),
    };
    setBusy(true);setMessage('');
    try{await uploadDirectDocument(input,file);formElement.reset();await onCreated();}
    catch(error){setMessage(error instanceof Error?error.message:'تعذر رفع الوثيقة.');}
    finally{setBusy(false);}
  }

  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}>
    <div className="modal-heading"><span className="eyebrow">وثيقة مؤسسية</span><h2>إضافة وثيقة إلى سجل العام</h2><p>استخدم العام الذي تنتمي إليه الوثيقة فعليًا. الرفع اليوم لا يغيّر سنة السجل التاريخية.</p></div>
    <div className="form-grid">
      <label className="full">الملف<input type="file" name="file" required accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.webp"/></label>
      <label className="full">عنوان الوثيقة<input name="title" required placeholder="مثال: تحليل نتائج الاختبار النهائي"/></label>
      <label>العام الدراسي للسجل<input name="academicYear" required readOnly value={academicYear} dir="ltr"/><small className="field-hint">يُحدد من تقويم عام العمل أعلى التطبيق.</small></label>
      <label>التصنيف<select name="category" defaultValue="وثيقة"><option>وثيقة</option><option>خطة</option><option>اختبار</option><option>تحليل نتائج</option><option>محضر</option><option>تقرير</option><option>مرجع</option><option>وثيقة أخرى</option></select></label>
      <label>المادة<input name="subject" placeholder="مثال: الفيزياء"/></label>
      <label>الصف<input name="grade" placeholder="مثال: العاشر"/></label>
      <label className="full">المعلم المرتبط<select name="teacherId" defaultValue=""><option value="">دون ربط بمعلم</option>{teachers.map(teacher=><option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select></label>
    </div>
    {message&&<div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}
    <div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={busy}>{busy?'جاري الرفع...':'رفع الوثيقة'}</button></div>
  </form></Modal>;
}
