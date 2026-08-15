import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { getPublicUploadInfo, uploadPublicFile } from '../lib/api';
import type { PublicUploadInfo } from '../types';

export function PublicUpload({ token }: { token: string }) {
  const [info, setInfo] = useState<PublicUploadInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  useEffect(()=>{getPublicUploadInfo(token).then(setInfo).catch((e:Error)=>setError(e.message)).finally(()=>setLoading(false));},[token]);
  async function submit(){ if(!file) return; setUploading(true); setError(''); try{await uploadPublicFile(token,file); setDone(true);}catch(e){setError(e instanceof Error?e.message:'تعذر رفع الملف.');}finally{setUploading(false);} }
  if(loading) return <PublicShell><div className="public-state"><div className="spinner"></div><p>جاري التحقق من رابط الطلب...</p></div></PublicShell>;
  if(error&&!info) return <PublicShell><div className="public-state error-state"><Icon name="alert" size={36}/><h2>تعذر فتح الطلب</h2><p>{error}</p></div></PublicShell>;
  if(done) return <PublicShell><div className="public-state success-state"><span className="success-orb"><Icon name="check" size={28}/></span><h2>تم استلام الملف بنجاح</h2><p>وصل الملف إلى صندوق مراجعة المعلم الأول. لا يلزمك أي إجراء آخر.</p></div></PublicShell>;
  return <PublicShell>{info&&<div className="upload-card"><span className="eyebrow">طلب رفع ملف</span><h1>{info.title}</h1><p className="upload-subtitle">{info.subject} • الصف {info.grade}</p><div className="request-summary"><div><span>المطلوب من</span><strong>{info.teacherName}</strong></div><div><span>نوع الملف</span><strong>{info.requestType}</strong></div><div><span>آخر موعد</span><strong>{info.deadline||'غير محدد'}</strong></div></div>{info.notes&&<div className="teacher-note"><strong>ملاحظة</strong><p>{info.notes}</p></div>}<label className={`drop-zone ${file?'has-file':''}`}><input type="file" onChange={(e)=>setFile(e.target.files?.[0]||null)} accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png"/><span className="drop-icon"><Icon name={file?'check':'upload'} size={26}/></span>{file?<><strong>{file.name}</strong><small>{(file.size/1024/1024).toFixed(2)} MB</small></>:<><strong>اسحب الملف هنا أو اختر من الجهاز</strong><small>{info.allowedFiles} • حتى {info.maxUploadMb} MB</small></>}</label>{error&&<div className="inline-error"><Icon name="alert" size={17}/>{error}</div>}<button className="primary-button wide" disabled={!file||uploading} onClick={submit}>{uploading?'جاري رفع الملف...':'رفع الملف'}</button></div>}</PublicShell>;
}
function PublicShell({children}:{children:React.ReactNode}){return <main className="public-upload-page"><div className="public-brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>إدارة أعمال المادة</small></div></div>{children}<footer>رابط تسليم آمن لهذا الطلب فقط</footer></main>}
