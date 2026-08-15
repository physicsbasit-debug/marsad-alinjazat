import type { BootstrapData, EventDetails, EventMediaRecord, TeacherCvItem, TeacherProfileDetails } from '../types';

function eventVisual(title: string, accent: string, secondary: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="${accent}"/><stop offset="1" stop-color="${secondary}"/></linearGradient><radialGradient id="r"><stop stop-color="#fff" stop-opacity=".34"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs><rect width="1400" height="800" fill="url(#g)"/><circle cx="1100" cy="170" r="270" fill="url(#r)"/><circle cx="240" cy="650" r="330" fill="url(#r)"/><g fill="none" stroke="#fff" stroke-opacity=".18" stroke-width="10"><circle cx="700" cy="400" r="150"/><path d="M430 400h540M700 130v540M520 220l360 360M880 220L520 580"/></g><text x="700" y="410" text-anchor="middle" direction="rtl" fill="#fff" font-size="72" font-family="Arial" font-weight="700">${title}</text><text x="700" y="475" text-anchor="middle" direction="rtl" fill="#fff" fill-opacity=".78" font-size="30" font-family="Arial">مرصد الإنجازات • التوثيق المهني</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

const eventVisuals = {
  science: eventVisual('أسبوع العلوم', '#167d77', '#123f58'),
  physics: eventVisual('مسابقة الفيزياء', '#17364d', '#4c728d'),
  reading: eventVisual('مبادرة اقرأ علمًا', '#9a7433', '#52604a'),
  student: eventVisual('منتجات طلابية', '#27635e', '#74a99d'),
};

export const previewBootstrap: BootstrapData = {
  academicYear: '2026/2027',
  term: 'الفصل الأول',
  dashboard: {
    teacherCount: 6,
    openRequests: 3,
    needsReview: 2,
    lateRequests: 1,
    openDecisions: 4,
    upcomingVisits: 2,
    planProgress: 82,
    visitProgress: 70,
    requestCompletion: 91,
  },
  teachers: [
    { id: 1, name: 'أحمد السالمي', subject: 'الفيزياء', specialization: 'فيزياء', qualification: 'بكالوريوس تربية', experienceYears: 12, workload: 18, cvCompletion: 100, email: 'ahmed@example.edu' },
    { id: 2, name: 'خالد الهنائي', subject: 'الكيمياء', specialization: 'كيمياء', qualification: 'بكالوريوس تربية', experienceYears: 8, workload: 20, cvCompletion: 78, email: 'khalid@example.edu' },
    { id: 3, name: 'محمد المعمري', subject: 'العلوم', specialization: 'علوم عامة', qualification: 'بكالوريوس تربية', experienceYears: 15, workload: 16, cvCompletion: 92, email: 'mohammed@example.edu' },
    { id: 4, name: 'سالم الرواحي', subject: 'الأحياء', specialization: 'أحياء', qualification: 'بكالوريوس تربية', experienceYears: 10, workload: 19, cvCompletion: 84, email: 'salim@example.edu' },
    { id: 5, name: 'يوسف البلوشي', subject: 'العلوم', specialization: 'علوم عامة', qualification: 'بكالوريوس تربية', experienceYears: 6, workload: 21, cvCompletion: 65, email: 'yousuf@example.edu' },
    { id: 6, name: 'ناصر الحوسني', subject: 'الفيزياء', specialization: 'فيزياء', qualification: 'ماجستير مناهج', experienceYears: 13, workload: 17, cvCompletion: 95, email: 'nasser@example.edu' },
  ],
  requests: [
    { id: 1, teacherId: 1, teacherName: 'أحمد السالمي', requestType: 'اختبار', subject: 'الفيزياء', grade: 'العاشر', title: 'الاختبار القصير الأول', deadline: '2026-08-18', notes: '', allowedFiles: 'PDF / Word / Excel', status: 'review', expiresAt: '2026-09-18T00:00:00+00:00', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 2, teacherId: 2, teacherName: 'خالد الهنائي', requestType: 'خطة فصلية', subject: 'الكيمياء', grade: 'العاشر', title: 'الخطة الفصلية', deadline: '2026-08-19', notes: '', allowedFiles: 'PDF / Word / Excel', status: 'received', expiresAt: '2026-09-19T00:00:00+00:00', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 3, teacherId: 3, teacherName: 'محمد المعمري', requestType: 'نشاط', subject: 'العلوم', grade: 'الثامن', title: 'نموذج نشاط علمي', deadline: '2026-08-13', notes: '', allowedFiles: 'PDF / Word / Excel', status: 'late', expiresAt: '2026-09-13T00:00:00+00:00', createdAt: '2026-08-10T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 4, teacherId: 4, teacherName: 'سالم الرواحي', requestType: 'تحليل نتائج', subject: 'الأحياء', grade: 'التاسع', title: 'تحليل النتائج', deadline: '2026-08-20', notes: '', allowedFiles: 'PDF / Word / Excel', status: 'approved', expiresAt: '2026-09-20T00:00:00+00:00', createdAt: '2026-08-12T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
  ],
  events: [
    { id: 1, title: 'أسبوع العلوم', eventType: 'فعالية', eventDate: '2026-10-12', location: 'المدرسة', audience: 'طلبة الصفوف 8-10', participantCount: 42, goals: 'تعزيز الثقافة العلمية', summary: 'فعاليات وتجارب تعليمية ومسابقات', outcomes: 'مشاركة واسعة', recommendations: 'توسيع مشاركة الطلبة', coverTone: 'teal', mediaCount: 3, coverMediaId: 1001, coverMediaUrl: eventVisuals.science, createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 2, title: 'مسابقة الفيزياء', eventType: 'مسابقة', eventDate: '2026-11-27', location: 'قاعة متعددة الأغراض', audience: 'الصف العاشر', participantCount: 18, goals: 'تنمية حل المشكلات', summary: 'مسابقة تطبيقية', outcomes: 'تحسن التفاعل', recommendations: 'تكرارها فصليًا', coverTone: 'navy', mediaCount: 2, coverMediaId: 2001, coverMediaUrl: eventVisuals.physics, createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 3, title: 'مبادرة اقرأ علمًا', eventType: 'مبادرة', eventDate: '2026-09-30', location: 'مركز مصادر التعلم', audience: 'الصف التاسع', participantCount: 31, goals: 'تعزيز القراءة العلمية', summary: 'قراءات قصيرة ونقاشات', outcomes: 'منتجات طلابية', recommendations: 'ربطها بالمنهج', coverTone: 'gold', mediaCount: 2, coverMediaId: 3001, coverMediaUrl: eventVisuals.reading, createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
  ],
  documents: [
    { id: 1, requestId: 2, teacherId: 2, title: 'الخطة الفصلية', category: 'خطة فصلية', subject: 'الكيمياء', grade: 'العاشر', academicYear: '2026/2027', originalName: 'خطة_الكيمياء_الفصل_الأول.pdf', mimeType: 'application/pdf', sizeBytes: 735000, storageProvider: 'preview', status: 'inbox', uploadedAt: '2026-08-15T05:00:00+00:00' },
    { id: 2, requestId: 4, teacherId: 4, title: 'تحليل النتائج', category: 'تحليل نتائج', subject: 'الأحياء', grade: 'التاسع', academicYear: '2026/2027', originalName: 'تحليل_نتائج_الأحياء.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', sizeBytes: 184000, storageProvider: 'preview', status: 'approved', uploadedAt: '2026-08-14T05:00:00+00:00', approvedAt: '2026-08-15T05:00:00+00:00' },
  ],
  activities: [
    { id: 1, activity_type: 'document', title: 'خالد رفع الخطة الفصلية', detail: 'الكيمياء • الصف العاشر', created_at: '2026-08-15T05:00:00+00:00' },
    { id: 2, activity_type: 'request', title: 'طلب اختبار جديد', detail: 'الفيزياء • الصف العاشر', created_at: '2026-08-15T04:00:00+00:00' },
    { id: 3, activity_type: 'event', title: 'توثيق مبادرة اقرأ علمًا', detail: '31 مشاركًا', created_at: '2026-08-14T05:00:00+00:00' },
  ],
  drive: {
    configured: false,
    connected: false,
    rootFolderId: null,
    scope: 'https://www.googleapis.com/auth/drive.file',
    storageMode: 'local',
  },
};


const previewEventMedia: Record<number, EventMediaRecord[]> = {
  1: [
    { id: 1001, eventId: 1, originalName: 'غلاف_أسبوع_العلوم.jpg', mimeType: 'image/jpeg', sizeBytes: 930000, storageProvider: 'preview', contentUrl: eventVisuals.science, caption: 'الغلاف الرسمي للفعالية', position: 0, isCover: true, createdAt: '2026-10-12T08:00:00+04:00' },
    { id: 1002, eventId: 1, originalName: 'محطات_علمية.jpg', mimeType: 'image/jpeg', sizeBytes: 740000, storageProvider: 'preview', contentUrl: eventVisuals.student, caption: 'نماذج من المحطات والمنتجات الطلابية', position: 1, isCover: false, createdAt: '2026-10-12T09:10:00+04:00' },
    { id: 1003, eventId: 1, originalName: 'خطة_تنفيذ_الفعالية.pdf', mimeType: 'application/pdf', sizeBytes: 310000, storageProvider: 'preview', caption: 'خطة التنفيذ المعتمدة', position: 2, isCover: false, createdAt: '2026-10-12T09:20:00+04:00' },
  ],
  2: [
    { id: 2001, eventId: 2, originalName: 'غلاف_مسابقة_الفيزياء.jpg', mimeType: 'image/jpeg', sizeBytes: 820000, storageProvider: 'preview', contentUrl: eventVisuals.physics, caption: 'المشهد الرئيس للمسابقة', position: 0, isCover: true, createdAt: '2026-11-27T09:00:00+04:00' },
    { id: 2002, eventId: 2, originalName: 'نتائج_المسابقة.pdf', mimeType: 'application/pdf', sizeBytes: 220000, storageProvider: 'preview', caption: 'النتائج الختامية', position: 1, isCover: false, createdAt: '2026-11-27T11:00:00+04:00' },
  ],
  3: [
    { id: 3001, eventId: 3, originalName: 'غلاف_اقرأ_علما.jpg', mimeType: 'image/jpeg', sizeBytes: 760000, storageProvider: 'preview', contentUrl: eventVisuals.reading, caption: 'الغلاف الرسمي للمبادرة', position: 0, isCover: true, createdAt: '2026-09-30T08:30:00+04:00' },
    { id: 3002, eventId: 3, originalName: 'منتجات_الطلبة.jpg', mimeType: 'image/jpeg', sizeBytes: 690000, storageProvider: 'preview', contentUrl: eventVisuals.student, caption: 'نماذج من المنتجات الطلابية', position: 1, isCover: false, createdAt: '2026-09-30T10:00:00+04:00' },
  ],
};

export function getPreviewEventDetails(eventId: number): EventDetails {
  const event = previewBootstrap.events.find((item) => item.id === eventId);
  if (!event) throw new Error('الفعالية غير موجودة في بيانات المعاينة.');
  const teacherIds = eventId === 1 ? [1, 2, 3] : eventId === 2 ? [1, 6] : [3, 5];
  return {
    ...event,
    media: previewEventMedia[eventId] || [],
    teachers: previewBootstrap.teachers.filter((teacher) => teacherIds.includes(teacher.id)).map((teacher) => ({ ...teacher, event_role: 'مشارك' })),
  };
}


const previewCvItems: Record<number, TeacherCvItem[]> = {
  1: [
    { id: 101, teacherId: 1, itemType: 'qualification', title: 'بكالوريوس تربية في الفيزياء', organization: 'جامعة السلطان قابوس', startYear: 2009, endYear: 2013, description: 'تخصص فيزياء وتربية علمية.', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 102, teacherId: 1, itemType: 'course', title: 'التقويم من أجل التعلم', organization: 'برنامج تطوير مهني', startYear: 2025, endYear: 2025, description: 'تطبيق استراتيجيات التقويم التكويني وبناء التغذية الراجعة.', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
    { id: 103, teacherId: 1, itemType: 'achievement', title: 'قيادة مبادرة تحسين التحصيل', organization: 'قسم العلوم', startYear: 2026, endYear: 2026, description: 'تنسيق تدخل تربوي مبني على تحليل النتائج ومتابعة الأثر.', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
  ],
  2: [
    { id: 201, teacherId: 2, itemType: 'course', title: 'استراتيجيات تدريس العلوم', organization: 'تدريب مهني', startYear: 2025, endYear: 2025, description: 'ممارسات صفية نشطة في تدريس الكيمياء.', createdAt: '2026-08-15T05:00:00+00:00', updatedAt: '2026-08-15T05:00:00+00:00' },
  ],
};

export function getPreviewTeacherProfile(teacherId: number): TeacherProfileDetails {
  const teacher = previewBootstrap.teachers.find((item) => item.id === teacherId);
  if (!teacher) throw new Error('المعلم غير موجود في بيانات المعاينة.');
  const cvItems = previewCvItems[teacherId] || [];
  return {
    teacher,
    profile: {
      employeeNumber: teacherId === 1 ? 'SCI-001' : '',
      schoolJoinYear: teacherId === 1 ? 2018 : null,
      grades: teacher.subject === 'العلوم' ? 'الثامن، التاسع' : 'العاشر',
      responsibilities: teacherId === 1 ? 'تنسيق الفيزياء، متابعة الاختبارات الموحدة، دعم أعضاء القسم.' : '',
      professionalSummary: `معلم ${teacher.subject} بخبرة ${teacher.experienceYears} سنوات، يركز على جودة التعلم والتقويم وتحسين الممارسات الصفية.`,
    },
    cvItems,
    stats: {
      requestCount: previewBootstrap.requests.filter((item) => item.teacherId === teacherId).length,
      documentCount: previewBootstrap.documents.filter((item) => item.teacherId === teacherId).length,
      approvedDocumentCount: previewBootstrap.documents.filter((item) => item.teacherId === teacherId && item.status === 'approved').length,
    },
  };
}
