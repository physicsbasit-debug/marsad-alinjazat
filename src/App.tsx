import { useEffect, useMemo, useState } from 'react';
import { Icon } from './components/Icon';
import { Modal } from './components/Modal';
import { GlobalSearch } from './components/GlobalSearch';
import { createEvent, createTeacher, createUploadRequest, getBootstrap, getDriveAuthUrl, updateRequestStatus } from './lib/api';
import { Dashboard } from './pages/Dashboard';
import { Documents } from './pages/Documents';
import { Events } from './pages/Events';
import { MeetingModal, Meetings } from './pages/Meetings';
import { Planning } from './pages/Planning';
import { Reports } from './pages/Reports';
import { Archive } from './pages/Archive';
import { Achievement, AssessmentModal } from './pages/Achievement';
import { Supervision, SupervisionVisitModal } from './pages/Supervision';
import { PublicUpload } from './pages/PublicUpload';
import { Requests } from './pages/Requests';
import { Teachers } from './pages/Teachers';
import type { BootstrapData, CreateEventInput, CreateRequestInput, CreateTeacherInput, RequestStatus, SearchResult } from './types';

const nav = [
  ['dashboard','home','الرئيسية'],['teachers','teachers','المعلمون'],['planning','planning','التخطيط والمنهج'],['achievement','chart','التحصيل والنتائج'],['supervision','supervision','الإشراف والمتابعة'],['requests','upload','طلبات الملفات'],['meetings','meeting','الاجتماعات والقرارات'],['events','spark','الفعاليات والتوثيق'],['documents','document','الوثائق والمراجع'],['reports','report','التقارير'],['archive','archive','الأرشيف التاريخي'],
] as const;

type View = typeof nav[number][0];

export default function App() {
  const publicToken = useMemo(()=>window.location.pathname.match(/^\/upload\/([^/]+)$/)?.[1]||null,[]);
  if(publicToken) return <PublicUpload token={publicToken}/>;
  return <AdminApp/>;
}

function AdminApp(){
  const [data,setData]=useState<BootstrapData|null>(null);
  const [view,setView]=useState<View>('dashboard');
  const [sidebar,setSidebar]=useState(false);
  const [quick,setQuick]=useState(false);
  const [requestModal,setRequestModal]=useState(false);
  const [teacherModal,setTeacherModal]=useState(false);
  const [eventModal,setEventModal]=useState(false);
  const [meetingModal,setMeetingModal]=useState(false);
  const [visitModal,setVisitModal]=useState(false);
  const [assessmentModal,setAssessmentModal]=useState(false);
  const [resultUrl,setResultUrl]=useState('');
  const [toast,setToast]=useState('');
  const [error,setError]=useState('');
  const [searchTarget,setSearchTarget]=useState<{view: View; id: number} | null>(null);
  const [yearInput,setYearInput]=useState('');

  async function refresh(yearOverride?:string):Promise<void>{
    const year=yearOverride||data?.academicYear;
    try{setError('');const next=await getBootstrap(year);setData(next);setYearInput(next.academicYear);}
    catch(e){const message=e instanceof Error?e.message:'تعذر تحميل البيانات.';if(data){setToast(message);}else{setError(message);}}
  }
  async function switchAcademicYear(value:string):Promise<boolean>{
    const normalized=value.replace(/\s/g,'');
    const match=normalized.match(/^(\d{4})\/(\d{4})$/);
    if(!match||Number(match[2])!==Number(match[1])+1){setToast('صيغة العام الدراسي يجب أن تكون مثل 2025/2026.');return false;}
    try{
      setError('');
      const next=await getBootstrap(normalized);
      setData(next);setYearInput(next.academicYear);setSearchTarget(null);
      return true;
    }catch(e){const message=e instanceof Error?e.message:'تعذر تحميل بيانات العام الدراسي.';if(data){setToast(message);}else{setError(message);}return false;}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{if(new URLSearchParams(window.location.search).get('drive')==='connected'){setToast('تم ربط Google Drive بنجاح');window.history.replaceState({},'', '/');void refresh();}},[]);
  useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),2600);return()=>clearTimeout(timer)},[toast]);

  async function changeStatus(id:number,status:RequestStatus){try{await updateRequestStatus(id,status);setToast('تم تحديث حالة الطلب');await refresh();}catch(e){setToast(e instanceof Error?e.message:'تعذر تحديث الطلب');}}
  function action(name:string){setQuick(false);if(name==='request'){if(data&&data.academicYear!==data.currentAcademicYear){setToast('طلبات الملفات تشغيلية للعام الجاري. أدخل السجلات التاريخية من وحداتها الأصلية.');return;}setRequestModal(true);return;}if(name==='event'){setEventModal(true);return;}if(name==='meeting'){setMeetingModal(true);return;}if(name==='visit'){setVisitModal(true);return;}if(name==='assessment'){setAssessmentModal(true);return;}setToast('تم تثبيت هذا الإجراء في بنية التطبيق.');}
  async function connectDrive(){try{const url=await getDriveAuthUrl();window.location.href=url;}catch(e){setToast(e instanceof Error?e.message:'تعذر بدء ربط Drive');}}

  async function navigateFromSearch(result: SearchResult){
    if(result.academicYear&&result.academicYear!==data?.academicYear){
      const changed=await switchAcademicYear(result.academicYear);
      if(!changed)return;
    }
    const nextView = result.targetView as View;
    const canOpenDirect = ['teachers','planning','achievement','supervision','meetings','events'].includes(nextView);
    setSearchTarget(canOpenDirect && result.targetId ? {view: nextView, id: result.targetId} : null);
    setView(nextView);
    setSidebar(false);
  }

  if(!data&&!error) return <Loading/>;
  if(error&&!data) return <div className="fatal-state"><Icon name="alert" size={36}/><h1>تعذر تشغيل التطبيق</h1><p>{error}</p><button className="primary-button" onClick={()=>void refresh()}>إعادة المحاولة</button></div>;
  if(!data) return null;

  return <div className="app-shell">
    <aside className={`sidebar ${sidebar?'open':''}`}>
      <div className="brand"><span className="brand-mark">م</span><div><strong>مرصد الإنجازات</strong><small>إدارة أعمال المادة</small></div><button className="icon-button mobile-close" onClick={()=>setSidebar(false)}><Icon name="close"/></button></div>
      <nav>{nav.map(([id,icon,label])=><button key={id} className={`nav-item ${view===id?'active':''}`} onClick={()=>{setView(id);setSidebar(false)}}><span className="nav-icon"><Icon name={icon}/></span><span>{label}</span>{id==='teachers'&&<b>{data.dashboard.teacherCount}</b>}{id==='requests'&&data.dashboard.openRequests>0&&<b className="warning-badge">{data.dashboard.openRequests}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><button className={`drive-card ${data.drive.connected?'connected':''}`} onClick={()=>!data.drive.connected&&void connectDrive()}><span className="drive-icon"><Icon name="drive"/></span><div><strong>Google Drive</strong><small>{data.drive.connected?'متصل وجاهز للحفظ':data.drive.configured?'جاهز للربط':'يحتاج إعداد OAuth'}</small></div><span className="connection-dot"></span></button><div className="mini-profile"><span className="avatar">م</span><div><strong>المعلم الأول</strong><small>إدارة المادة</small></div><Icon name="more" size={18}/></div></div>
    </aside>
    {sidebar&&<button className="sidebar-scrim" onClick={()=>setSidebar(false)} aria-label="إغلاق القائمة"/>}
    <main className="main-area">
      <header className="topbar"><button className="icon-button menu-button" onClick={()=>setSidebar(true)}><Icon name="menu"/></button><GlobalSearch currentAcademicYear={data.academicYear} onNavigate={navigateFromSearch}/><div className="top-actions"><AcademicYearControl value={yearInput||data.academicYear} currentYear={data.currentAcademicYear} years={data.availableAcademicYears} onChange={setYearInput} onApply={()=>void switchAcademicYear(yearInput||data.academicYear)}/><button className="icon-button bell"><Icon name="bell"/><span></span></button><div className="quick-wrap"><button className="primary-button" onClick={()=>setQuick(!quick)}><Icon name="plus"/> إضافة</button>{quick&&<div className="quick-menu"><Quick icon="upload" title="طلب ملف" detail="إنشاء رابط رفع لمعلم" action={()=>action('request')}/><Quick icon="spark" title="توثيق فعالية" detail="أهداف وصور ونتائج" action={()=>action('event')}/><Quick icon="supervision" title="تسجيل زيارة" detail="متابعة فنية" action={()=>action('visit')}/><Quick icon="meeting" title="اجتماع جديد" detail="محاور وقرارات" action={()=>action('meeting')}/><Quick icon="chart" title="نتيجة وتقويم" detail="تسجيل مؤشرات التحصيل" action={()=>action('assessment')}/></div>}</div></div></header>
      {data.academicYear!==data.currentAcademicYear&&<div className="historical-context-banner"><Icon name="archive" size={18}/><div><strong>مساحة عمل تاريخية: {data.academicYear}</strong><span>أي سجل جديد في الوحدات أدناه سيُحفظ لهذا العام ما لم تغيّر عام السجل داخل النموذج. العام الجاري هو {data.currentAcademicYear}.</span></div><button className="ghost-button" onClick={()=>void switchAcademicYear(data.currentAcademicYear)}>العودة للعام الجاري</button></div>}
      <section className="workspace">{view==='dashboard'?<Dashboard data={data} onQuickAction={action}/>:view==='teachers'?<Teachers teachers={data.teachers} requests={data.requests} documents={data.documents} visits={data.visits} academicYear={data.academicYear} currentAcademicYear={data.currentAcademicYear} onAddTeacher={()=>setTeacherModal(true)} onChanged={refresh} initialOpenId={searchTarget?.view==='teachers'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='requests'?<Requests requests={data.requests} onNewRequest={()=>setRequestModal(true)} onStatus={changeStatus}/>:view==='planning'?<Planning plans={data.plans} planningAttention={data.planningAttention} teachers={data.teachers} academicYear={data.academicYear} onRefresh={refresh} initialOpenId={searchTarget?.view==='planning'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='achievement'?<Achievement assessments={data.assessments} achievementAttention={data.achievementAttention} teachers={data.teachers} academicYear={data.academicYear} term={data.term} onAddAssessment={()=>setAssessmentModal(true)} onRefresh={refresh} initialOpenId={searchTarget?.view==='achievement'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='supervision'?<Supervision visits={data.visits} supervisionAttention={data.supervisionAttention} teachers={data.teachers} onAddVisit={()=>setVisitModal(true)} onRefresh={refresh} initialOpenId={searchTarget?.view==='supervision'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='meetings'?<Meetings meetings={data.meetings} teachers={data.teachers} onAddMeeting={()=>setMeetingModal(true)} onRefresh={refresh} initialOpenId={searchTarget?.view==='meetings'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='events'?<Events events={data.events} teachers={data.teachers} onAddEvent={()=>setEventModal(true)} onRefresh={refresh} initialOpenId={searchTarget?.view==='events'?searchTarget.id:null} onInitialOpened={()=>setSearchTarget(null)}/>:view==='documents'?<Documents documents={data.documents} teachers={data.teachers} academicYear={data.academicYear} onRefresh={refresh}/>:view==='reports'?<Reports teachers={data.teachers} academicYear={data.academicYear} term={data.term}/>:view==='archive'?<Archive currentAcademicYear={data.currentAcademicYear} onOpenYear={(year)=>{void switchAcademicYear(year).then((ok)=>{if(ok)setView('dashboard')})}}/>:<Placeholder view={view}/>}</section>
    </main>
    <RequestModal open={requestModal} teachers={data.teachers} onClose={()=>setRequestModal(false)} onCreated={async(url)=>{setRequestModal(false);setResultUrl(url);await refresh();}}/>
    <TeacherModal open={teacherModal} academicYear={data.academicYear} onClose={()=>setTeacherModal(false)} onCreated={async()=>{setTeacherModal(false);setToast('تمت إضافة المعلم');await refresh();}}/>
    <EventModal open={eventModal} teachers={data.teachers} academicYear={data.academicYear} onClose={()=>setEventModal(false)} onCreated={async()=>{setEventModal(false);setToast('تم توثيق الفعالية');await refresh();}}/>
    <MeetingModal open={meetingModal} teachers={data.teachers} academicYear={data.academicYear} onClose={()=>setMeetingModal(false)} onCreated={async()=>{setMeetingModal(false);setToast('تم إنشاء الاجتماع');await refresh();}}/>
    <SupervisionVisitModal open={visitModal} teachers={data.teachers} academicYear={data.academicYear} onClose={()=>setVisitModal(false)} onCreated={async()=>{setVisitModal(false);setToast('تم تسجيل الزيارة');await refresh();}}/>
    <AssessmentModal open={assessmentModal} teachers={data.teachers} academicYear={data.academicYear} term={data.term} onClose={()=>setAssessmentModal(false)} onCreated={async()=>{setAssessmentModal(false);setToast('تم تسجيل نتيجة التحصيل');await refresh();}}/>
    <Modal open={!!resultUrl} onClose={()=>setResultUrl('')} compact><div className="result-dialog"><span className="success-orb"><Icon name="check" size={26}/></span><span className="eyebrow">تم إنشاء الطلب</span><h2>رابط الرفع جاهز</h2><p>أرسل هذا الرابط للمعلم. يستطيع رفع الملف من الهاتف أو الكمبيوتر دون الدخول إلى لوحة الإدارة.</p><div className="link-box"><code>{resultUrl}</code><button className="icon-button" onClick={async()=>{await navigator.clipboard.writeText(resultUrl);setToast('تم نسخ الرابط')}}><Icon name="copy"/></button></div><button className="primary-button wide" onClick={()=>setResultUrl('')}>تم</button></div></Modal>
    {toast&&<div className="toast">{toast}</div>}
  </div>;
}

function RequestModal({open,teachers,onClose,onCreated}:{open:boolean;teachers:BootstrapData['teachers'];onClose:()=>void;onCreated:(url:string)=>Promise<void>}){
  const [saving,setSaving]=useState(false);const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const formElement=event.currentTarget;setSaving(true);setMessage('');const form=new FormData(formElement);const payload:CreateRequestInput={teacherId:Number(form.get('teacherId')),requestType:String(form.get('requestType')),subject:String(form.get('subject')),grade:String(form.get('grade')),title:String(form.get('title')),deadline:String(form.get('deadline')||''),notes:String(form.get('notes')||''),allowedFiles:String(form.get('allowedFiles'))};try{const result=await createUploadRequest(payload);await onCreated(result.uploadUrl);formElement.reset();}catch(e){setMessage(e instanceof Error?e.message:'تعذر إنشاء الطلب.');}finally{setSaving(false)}}
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">طلب جديد</span><h2>طلب ملف من معلم</h2><p>سينشئ النظام رابط تسليم خاصًا، ثم ينتقل الملف مباشرة إلى صندوق المراجعة.</p></div><div className="form-grid"><label>المعلم<select name="teacherId" required>{teachers.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label><label>نوع الملف<select name="requestType"><option>اختبار</option><option>خطة فصلية</option><option>نموذج تخطيط</option><option>نشاط</option><option>تحليل نتائج</option><option>ملف آخر</option></select></label><label>المادة<select name="subject"><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label><label>الصف<select name="grade"><option>العاشر</option><option>التاسع</option><option>الثامن</option></select></label><label className="full">عنوان الطلب<input name="title" required defaultValue="الاختبار القصير الأول"/></label><label>آخر موعد<input type="date" name="deadline"/></label><label>الملفات المسموحة<select name="allowedFiles"><option>PDF / Word / Excel</option><option>PDF فقط</option><option>جميع الملفات التعليمية</option></select></label><label className="full">ملاحظات<textarea name="notes" rows={3} placeholder="تعليمات مختصرة للمعلم..."/></label></div>{message&&<div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving?'جاري الإنشاء...':'إنشاء رابط الرفع'}</button></div></form></Modal>
}


function TeacherModal({open,academicYear,onClose,onCreated}:{open:boolean;academicYear:string;onClose:()=>void;onCreated:()=>Promise<void>}){
  const [saving,setSaving]=useState(false);const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const formElement=event.currentTarget;setSaving(true);setMessage('');const form=new FormData(formElement);const payload:CreateTeacherInput={academicYear:String(form.get('academicYear')||academicYear),name:String(form.get('name')),subject:String(form.get('subject')),specialization:String(form.get('specialization')||''),qualification:String(form.get('qualification')||''),experienceYears:Number(form.get('experienceYears')||0),workload:Number(form.get('workload')||0),email:String(form.get('email')||''),phone:String(form.get('phone')||'')};try{await createTeacher(payload);formElement.reset();await onCreated();}catch(e){setMessage(e instanceof Error?e.message:'تعذر إضافة المعلم أو ربطه بعام العمل.');}finally{setSaving(false)}}
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">ارتباط مهني سنوي</span><h2>إضافة معلم إلى عام العمل</h2><p>يُربط المعلم بالعام المحدد. إذا كان موجودًا مسبقًا بنفس البريد، أو بالاسم والمادة نفسيهما، يُستخدم ملفه المهني نفسه بدل إنشاء نسخة مكررة.</p></div><div className="form-grid"><label>العام الدراسي للسجل<input name="academicYear" required defaultValue={academicYear} placeholder="2025/2026"/></label><label className="full">اسم المعلم<input name="name" required placeholder="الاسم الرباعي"/></label><label>المادة<select name="subject"><option>الفيزياء</option><option>الكيمياء</option><option>الأحياء</option><option>العلوم</option></select></label><label>التخصص<input name="specialization" placeholder="مثال: فيزياء"/></label><label className="full">المؤهل<input name="qualification" placeholder="مثال: بكالوريوس تربية"/></label><label>سنوات الخبرة<input type="number" min="0" max="60" name="experienceYears" defaultValue="0"/></label><label>النصاب<input type="number" min="0" max="40" name="workload" defaultValue="0"/></label><label>البريد<input type="email" name="email" placeholder="name@example.edu"/></label><label>الهاتف<input name="phone" placeholder="اختياري"/></label></div>{message&&<div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving?'جاري الحفظ...':'إضافة المعلم'}</button></div></form></Modal>
}

function EventModal({open,teachers,academicYear,onClose,onCreated}:{open:boolean;teachers:BootstrapData['teachers'];academicYear:string;onClose:()=>void;onCreated:()=>Promise<void>}){
  const [saving,setSaving]=useState(false);const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const formElement=event.currentTarget;setSaving(true);setMessage('');const form=new FormData(formElement);const payload:CreateEventInput={title:String(form.get('title')),eventType:String(form.get('eventType')),eventDate:String(form.get('eventDate')),academicYear:String(form.get('academicYear')||academicYear),location:String(form.get('location')||''),audience:String(form.get('audience')||''),participantCount:Number(form.get('participantCount')||0),goals:String(form.get('goals')||''),summary:String(form.get('summary')||''),outcomes:String(form.get('outcomes')||''),recommendations:String(form.get('recommendations')||''),teacherIds:form.getAll('teacherIds').map((value)=>Number(value))};try{await createEvent(payload);formElement.reset();await onCreated();}catch(e){setMessage(e instanceof Error?e.message:'تعذر توثيق الفعالية.');}finally{setSaving(false)}}
  return <Modal open={open} onClose={onClose}><form className="request-form" onSubmit={submit}><div className="modal-heading"><span className="eyebrow">سجل توثيق</span><h2>توثيق فعالية</h2><p>سجل واحد يجمع الهدف والتنفيذ والفريق والأدلة والمخرجات، ثم يبقى قابلًا للتحديث بعد انتهاء الفعالية.</p></div><div className="form-grid"><label className="full">عنوان الفعالية<input name="title" required placeholder="مثال: أسبوع العلوم"/></label><label>نوع الفعالية<select name="eventType"><option>فعالية</option><option>مسابقة</option><option>مبادرة</option><option>زيارة علمية</option><option>برنامج طلابي</option><option>مشاركة مجتمعية</option></select></label><label>التاريخ<input type="date" name="eventDate" required/></label><label>العام الدراسي للسجل<input name="academicYear" required defaultValue={academicYear} placeholder="2025/2026"/></label><label>المكان<input name="location" placeholder="المدرسة / القاعة / ..."/></label><label>الفئة المستهدفة<input name="audience" placeholder="الصف العاشر مثلاً"/></label><label>عدد المشاركين<input type="number" min="0" max="100000" name="participantCount" defaultValue="0"/></label><label className="full">الأهداف<textarea name="goals" rows={2} placeholder="الأهداف التربوية للفعالية"/></label><label className="full">ملخص التنفيذ<textarea name="summary" rows={3} placeholder="ماذا نُفذ وكيف؟"/></label><label className="full">النتائج والمخرجات<textarea name="outcomes" rows={2}/></label><label className="full">التوصيات<textarea name="recommendations" rows={2}/></label><fieldset className="full event-create-team"><legend>المعلمون المشاركون</legend><div>{teachers.map((teacher)=><label key={teacher.id}><input type="checkbox" name="teacherIds" value={teacher.id}/><span className="avatar">{teacher.name[0]}</span><span><strong>{teacher.name}</strong><small>{teacher.subject}</small></span></label>)}</div></fieldset></div>{message&&<div className="inline-error"><Icon name="alert" size={17}/>{message}</div>}<div className="modal-actions"><button type="button" className="ghost-button" onClick={onClose}>إلغاء</button><button className="primary-button" disabled={saving}>{saving?'جاري الحفظ...':'حفظ التوثيق'}</button></div></form></Modal>
}

function AcademicYearControl({value,currentYear,years,onChange,onApply}:{value:string;currentYear:string;years:string[];onChange:(value:string)=>void;onApply:()=>void}){
  const historical=value!==currentYear;
  return <div className={`academic-year-control ${historical?'historical':''}`}><label><span>عام العمل</span><input list="academic-years" value={value} onChange={(event)=>onChange(event.target.value)} onKeyDown={(event)=>{if(event.key==='Enter'){event.preventDefault();onApply();}}}/><datalist id="academic-years">{Array.from(new Set([currentYear,...years])).map((year)=><option key={year} value={year}/>)}</datalist></label><button type="button" onClick={onApply}>عرض</button></div>;
}

function Quick({icon,title,detail,action}:{icon:'upload'|'spark'|'supervision'|'meeting'|'chart';title:string;detail:string;action:()=>void}){return <button onClick={action}><span><Icon name={icon}/></span><div><strong>{title}</strong><small>{detail}</small></div></button>}
function Placeholder({view}:{view:View}){return <div className="placeholder"><span className="placeholder-icon"><Icon name="spark" size={30}/></span><span className="eyebrow">ضمن النواة</span><h1>قريبًا</h1><p>هذه المساحة ضمن الهيكل الأساسي.</p><div className="tag-row"><span>{view}</span></div></div>}
function Loading(){return <div className="loading-screen"><span className="brand-mark large">م</span><div className="spinner"></div><p>جاري تجهيز مساحة المادة...</p></div>}
