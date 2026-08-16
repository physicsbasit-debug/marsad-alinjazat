import type { AchievementAssessmentDetails, ArchiveYearDetail, ArchiveYearsIndex, BootstrapData, CurriculumPlanDetails, EventDetails, EventMediaRecord, MeetingDetails, OfficialReport, OfficialReportQuery, OfficialReportSection, SupervisionVisitDetails, TeacherCvItem, TeacherProfileDetails } from '../types';

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
    upcomingVisits: 1,
    planProgress: 69,
    visitProgress: 80,
    requestCompletion: 91,
    achievementMastery: 60,
    openAchievementActions: 2,
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
  meetings: [
    { id: 1, title: 'اجتماع قسم العلوم الأول', meetingType: 'اجتماع قسم', meetingDate: '2026-09-03', meetingTime: '10:30', location: 'قاعة العلوم', academicYear: '2026/2027', status: 'planned', attendeeCount: 6, decisionCount: 3, openDecisionCount: 2, overdueDecisionCount: 0, completedDecisionCount: 1, createdAt: '2026-08-15T06:20:00+00:00', updatedAt: '2026-08-15T06:20:00+00:00' },
    { id: 2, title: 'مراجعة نتائج الاختبار القصير', meetingType: 'اجتماع متابعة', meetingDate: '2026-09-24', meetingTime: '12:00', location: 'غرفة الاجتماعات', academicYear: '2026/2027', status: 'planned', attendeeCount: 4, decisionCount: 2, openDecisionCount: 1, overdueDecisionCount: 0, completedDecisionCount: 1, createdAt: '2026-08-15T06:25:00+00:00', updatedAt: '2026-08-15T06:25:00+00:00' },
    { id: 3, title: 'الاستعداد لبداية العام الدراسي', meetingType: 'اجتماع تنسيقي', meetingDate: '2026-08-10', meetingTime: '09:00', location: 'قاعة العلوم', academicYear: '2026/2027', status: 'held', attendeeCount: 5, decisionCount: 2, openDecisionCount: 1, overdueDecisionCount: 1, completedDecisionCount: 1, createdAt: '2026-08-10T05:00:00+00:00', updatedAt: '2026-08-14T05:00:00+00:00' },
  ],
  decisionAttention: [
    { id: 301, meetingId: 3, meetingTitle: 'الاستعداد لبداية العام الدراسي', title: 'تحديث توزيع أعمال القسم', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', dueDate: '2026-08-14', status: 'overdue', baseStatus: 'in_progress', notes: 'اعتماد النسخة النهائية بعد مراجعة الأنصبة.', createdAt: '2026-08-10T06:00:00+00:00', updatedAt: '2026-08-14T05:00:00+00:00' },
    { id: 101, meetingId: 1, meetingTitle: 'اجتماع قسم العلوم الأول', title: 'توحيد نموذج التخطيط الأسبوعي', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', dueDate: '2026-09-10', status: 'in_progress', baseStatus: 'in_progress', notes: '', createdAt: '2026-08-15T06:30:00+00:00', updatedAt: '2026-08-15T06:30:00+00:00' },
    { id: 102, meetingId: 1, meetingTitle: 'اجتماع قسم العلوم الأول', title: 'تجهيز خطة الزيارات الصفية', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', dueDate: '2026-09-17', status: 'new', baseStatus: 'new', notes: '', createdAt: '2026-08-15T06:31:00+00:00', updatedAt: '2026-08-15T06:31:00+00:00' },
    { id: 201, meetingId: 2, meetingTitle: 'مراجعة نتائج الاختبار القصير', title: 'تحديد الطلبة المستهدفين بالتدخل', responsibleTeacherId: 4, responsibleName: 'سالم الرواحي', dueDate: '2026-09-28', status: 'new', baseStatus: 'new', notes: '', createdAt: '2026-08-15T06:32:00+00:00', updatedAt: '2026-08-15T06:32:00+00:00' },
  ],
  plans: [
    { id: 1, title: 'خطة الفيزياء للفصل الأول', subject: 'الفيزياء', grade: 'العاشر', term: 'الفصل الأول', academicYear: '2026/2027', ownerTeacherId: 1, ownerName: 'أحمد السالمي', startDate: '2026-08-23', endDate: '2026-12-17', notes: 'تركيز على الربط بين المفاهيم والتطبيقات العملية.', status: 'active', unitCount: 3, completedUnitCount: 1, overdueUnitCount: 1, progressPercent: 62, createdAt: '2026-08-15T07:50:00+00:00', updatedAt: '2026-08-15T08:00:00+00:00' },
    { id: 2, title: 'خطة الكيمياء للفصل الأول', subject: 'الكيمياء', grade: 'العاشر', term: 'الفصل الأول', academicYear: '2026/2027', ownerTeacherId: 2, ownerName: 'خالد الهنائي', startDate: '2026-08-23', endDate: '2026-12-17', notes: 'متابعة أسبوعية لمعدل إنجاز الوحدات.', status: 'active', unitCount: 3, completedUnitCount: 1, overdueUnitCount: 0, progressPercent: 60, createdAt: '2026-08-15T07:52:00+00:00', updatedAt: '2026-08-15T08:02:00+00:00' },
    { id: 3, title: 'خطة العلوم للصف التاسع', subject: 'العلوم', grade: 'التاسع', term: 'الفصل الأول', academicYear: '2026/2027', ownerTeacherId: 3, ownerName: 'محمد المعمري', startDate: '2026-08-23', endDate: '2026-12-17', notes: '', status: 'active', unitCount: 3, completedUnitCount: 2, overdueUnitCount: 1, progressPercent: 85, createdAt: '2026-08-15T07:54:00+00:00', updatedAt: '2026-08-15T08:04:00+00:00' },
  ],
  planningAttention: [
    { id: 12, planId: 1, planTitle: 'خطة الفيزياء للفصل الأول', planSubject: 'الفيزياء', planGrade: 'العاشر', title: 'الحركة والقوى', sequence: 2, plannedStart: '2026-08-05', plannedEnd: '2026-08-13', progressPercent: 65, status: 'in_progress', effectiveStatus: 'overdue', delayReason: 'احتاجت الوحدة إلى حصص دعم إضافية قبل الانتقال للمحتوى التالي.', notes: '', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', createdAt: '2026-08-15T07:50:00+00:00', updatedAt: '2026-08-15T08:00:00+00:00' },
    { id: 32, planId: 3, planTitle: 'خطة العلوم للصف التاسع', planSubject: 'العلوم', planGrade: 'التاسع', title: 'الوراثة والتنوع', sequence: 3, plannedStart: '2026-08-08', plannedEnd: '2026-08-14', progressPercent: 55, status: 'in_progress', effectiveStatus: 'overdue', delayReason: 'تأخر النشاط العملي المرتبط بالوحدة.', notes: '', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', createdAt: '2026-08-15T07:54:00+00:00', updatedAt: '2026-08-15T08:04:00+00:00' },
  ],
  visits: [
    { id: 1, teacherId: 1, teacherName: 'أحمد السالمي', teacherSubject: 'الفيزياء', visitType: 'زيارة صفية', visitDate: '2026-08-18', periodLabel: 'الحصة الثالثة', grade: 'العاشر', lessonTitle: 'القوى والحركة', objectives: 'متابعة توظيف الأسئلة السابرة وربط المفهوم بالتطبيق.', strengths: '', developmentAreas: '', recommendations: '', followupDate: null, followupNotes: '', academicYear: '2026/2027', status: 'planned', effectiveStatus: 'planned', actionCount: 0, openActionCount: 0, completedActionCount: 0, overdueActionCount: 0, createdAt: '2026-08-15T08:20:00+00:00', updatedAt: '2026-08-15T08:20:00+00:00' },
    { id: 2, teacherId: 2, teacherName: 'خالد الهنائي', teacherSubject: 'الكيمياء', visitType: 'زيارة تطويرية', visitDate: '2026-08-10', periodLabel: 'الحصة الثانية', grade: 'العاشر', lessonTitle: 'الترابط الكيميائي', objectives: 'متابعة تنويع التمثيلات البصرية والتقويم أثناء التعلم.', strengths: 'تنظيم واضح للمحتوى، وأسئلة تربط المعرفة السابقة بالمفهوم الجديد.', developmentAreas: 'زيادة زمن تعلم الطلبة النشط وتقليل الشرح المباشر في منتصف الدرس.', recommendations: 'إدخال مهمة ثنائية قصيرة قبل التقويم الختامي، وتوثيق أثرها في الزيارة التالية.', followupDate: '2026-08-14', followupNotes: 'ينبغي مراجعة تطبيق المهمة الثنائية وأثرها على مشاركة الطلبة.', academicYear: '2026/2027', status: 'needs_followup', effectiveStatus: 'overdue', actionCount: 2, openActionCount: 1, completedActionCount: 1, overdueActionCount: 1, createdAt: '2026-08-10T09:00:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' },
    { id: 3, teacherId: 3, teacherName: 'محمد المعمري', teacherSubject: 'العلوم', visitType: 'زيارة متابعة', visitDate: '2026-08-05', periodLabel: 'الحصة الخامسة', grade: 'التاسع', lessonTitle: 'الوراثة والتنوع', objectives: 'التحقق من تنفيذ توصيات الزيارة السابقة.', strengths: 'تحسن واضح في إدارة الحوار وتوزيع الأسئلة بين الطلبة.', developmentAreas: 'الاستمرار في تنويع التغذية الراجعة.', recommendations: 'المحافظة على الممارسة الحالية ومشاركة نموذج ناجح مع القسم.', followupDate: '2026-08-12', followupNotes: 'أغلقت المتابعة بعد التحقق من التطبيق.', academicYear: '2026/2027', status: 'closed', effectiveStatus: 'closed', actionCount: 1, openActionCount: 0, completedActionCount: 1, overdueActionCount: 0, closedAt: '2026-08-12T08:30:00+00:00', createdAt: '2026-08-05T08:00:00+00:00', updatedAt: '2026-08-12T08:30:00+00:00' },
    { id: 4, teacherId: 5, teacherName: 'يوسف البلوشي', teacherSubject: 'العلوم', visitType: 'زيارة صفية', visitDate: '2026-08-13', periodLabel: 'الحصة الرابعة', grade: 'الثامن', lessonTitle: 'الموجات', objectives: 'متابعة وضوح التعليمات وإدارة زمن الأنشطة.', strengths: '', developmentAreas: '', recommendations: '', followupDate: null, followupNotes: '', academicYear: '2026/2027', status: 'planned', effectiveStatus: 'overdue', actionCount: 0, openActionCount: 0, completedActionCount: 0, overdueActionCount: 0, createdAt: '2026-08-11T08:00:00+00:00', updatedAt: '2026-08-11T08:00:00+00:00' },
    { id: 5, teacherId: 4, teacherName: 'سالم الرواحي', teacherSubject: 'الأحياء', visitType: 'زيارة صفية', visitDate: '2026-08-12', periodLabel: 'الحصة الأولى', grade: 'التاسع', lessonTitle: 'النقل في النباتات', objectives: 'متابعة بناء المفهوم من الأدلة والملاحظات.', strengths: 'استخدام جيد للأسئلة والتجربة القصيرة في بداية الدرس.', developmentAreas: 'إتاحة وقت أطول لتفسير الطلبة للنتائج.', recommendations: 'زيادة وقت التفسير قبل تثبيت الإجابة العلمية.', followupDate: null, followupNotes: '', academicYear: '2026/2027', status: 'completed', effectiveStatus: 'completed', actionCount: 0, openActionCount: 0, completedActionCount: 0, overdueActionCount: 0, createdAt: '2026-08-12T07:00:00+00:00', updatedAt: '2026-08-12T08:00:00+00:00' },
  ],
  supervisionAttention: [
    { id: 4, teacherId: 5, teacherName: 'يوسف البلوشي', teacherSubject: 'العلوم', visitType: 'زيارة صفية', visitDate: '2026-08-13', periodLabel: 'الحصة الرابعة', grade: 'الثامن', lessonTitle: 'الموجات', objectives: 'متابعة وضوح التعليمات وإدارة زمن الأنشطة.', strengths: '', developmentAreas: '', recommendations: '', followupDate: null, followupNotes: '', academicYear: '2026/2027', status: 'planned', effectiveStatus: 'overdue', actionCount: 0, openActionCount: 0, completedActionCount: 0, overdueActionCount: 0, createdAt: '2026-08-11T08:00:00+00:00', updatedAt: '2026-08-11T08:00:00+00:00' },
    { id: 2, teacherId: 2, teacherName: 'خالد الهنائي', teacherSubject: 'الكيمياء', visitType: 'زيارة تطويرية', visitDate: '2026-08-10', periodLabel: 'الحصة الثانية', grade: 'العاشر', lessonTitle: 'الترابط الكيميائي', objectives: 'متابعة تنويع التمثيلات البصرية والتقويم أثناء التعلم.', strengths: 'تنظيم واضح للمحتوى، وأسئلة تربط المعرفة السابقة بالمفهوم الجديد.', developmentAreas: 'زيادة زمن تعلم الطلبة النشط وتقليل الشرح المباشر في منتصف الدرس.', recommendations: 'إدخال مهمة ثنائية قصيرة قبل التقويم الختامي، وتوثيق أثرها في الزيارة التالية.', followupDate: '2026-08-14', followupNotes: 'ينبغي مراجعة تطبيق المهمة الثنائية وأثرها على مشاركة الطلبة.', academicYear: '2026/2027', status: 'needs_followup', effectiveStatus: 'overdue', actionCount: 2, openActionCount: 1, completedActionCount: 1, overdueActionCount: 1, createdAt: '2026-08-10T09:00:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' },
  ],
  assessments: [
    { id: 1, title: 'الاختبار القصير الأول', assessmentType: 'اختبار قصير', subject: 'الفيزياء', grade: 'العاشر', assessmentDate: '2026-09-15', term: 'الفصل الأول', academicYear: '2026/2027', teacherId: 1, teacherName: 'أحمد السالمي', maxScore: 40, studentCount: 28, averageScore: 26.8, highestScore: 39, lowestScore: 12, masteryThresholdPct: 60, masteryReferenceSource: 'بيانات معاينة غير تشغيلية — ليست معيارًا عُمانيًا', masteryReferenceYear: 'preview', masteryReferenceNote: 'القيمة معروضة لاختبار الواجهة فقط ويجب استبدالها في التشغيل الفعلي بمرجع عُماني معتمد.', masteredCount: 17, nearMasteryCount: 7, interventionCount: 4, notes: 'النتيجة مستقرة إجمالًا مع حاجة مجموعة صغيرة إلى مراجعة مركزة قبل التقويم التالي.', status: 'reviewed', masteryPercent: 61, averagePercent: 67, actionCount: 2, remedialActionCount: 1, enrichmentActionCount: 1, openActionCount: 1, overdueActionCount: 0, measuredActionCount: 1, targetMetActionCount: 1, unmeasuredCompletedActionCount: 0, impactReviewActionCount: 0, createdAt: '2026-09-15T10:00:00+00:00', updatedAt: '2026-09-16T08:00:00+00:00' },
    { id: 2, title: 'تقويم الروابط الكيميائية', assessmentType: 'اختبار قصير', subject: 'الكيمياء', grade: 'العاشر', assessmentDate: '2026-08-10', term: 'الفصل الأول', academicYear: '2026/2027', teacherId: 2, teacherName: 'خالد الهنائي', maxScore: 40, studentCount: 30, averageScore: 21, highestScore: 37, lowestScore: 8, masteryThresholdPct: 60, masteryReferenceSource: 'بيانات معاينة غير تشغيلية — ليست معيارًا عُمانيًا', masteryReferenceYear: 'preview', masteryReferenceNote: 'القيمة معروضة لاختبار الواجهة فقط ويجب استبدالها في التشغيل الفعلي بمرجع عُماني معتمد.', masteredCount: 14, nearMasteryCount: 8, interventionCount: 8, notes: 'انخفاض نسبة الفئة المحققة للحد المسجل يستلزم تدخلًا موجّهًا وإعادة قياس، دون افتراض مهارة محددة من الدرجة الكلية وحدها.', status: 'recorded', masteryPercent: 47, averagePercent: 53, actionCount: 2, remedialActionCount: 1, enrichmentActionCount: 0, openActionCount: 1, overdueActionCount: 1, measuredActionCount: 0, targetMetActionCount: 0, unmeasuredCompletedActionCount: 0, impactReviewActionCount: 0, createdAt: '2026-08-10T10:00:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' },
    { id: 3, title: 'تقويم الوراثة والتنوع', assessmentType: 'مهمة أدائية', subject: 'العلوم', grade: 'التاسع', assessmentDate: '2026-08-12', term: 'الفصل الأول', academicYear: '2026/2027', teacherId: 3, teacherName: 'محمد المعمري', maxScore: 20, studentCount: 26, averageScore: 15.5, highestScore: 20, lowestScore: 8, masteryThresholdPct: 60, masteryReferenceSource: 'بيانات معاينة غير تشغيلية — ليست معيارًا عُمانيًا', masteryReferenceYear: 'preview', masteryReferenceNote: 'القيمة معروضة لاختبار الواجهة فقط ويجب استبدالها في التشغيل الفعلي بمرجع عُماني معتمد.', masteredCount: 19, nearMasteryCount: 5, interventionCount: 2, notes: 'سجل المعاينة يبيّن نسبة أعلى للفئة المحققة للحد المسجل، مع متابعة محدودة للفئة دون الحد.', status: 'reviewed', masteryPercent: 73, averagePercent: 78, actionCount: 1, remedialActionCount: 0, enrichmentActionCount: 0, openActionCount: 0, overdueActionCount: 0, measuredActionCount: 1, targetMetActionCount: 0, unmeasuredCompletedActionCount: 0, impactReviewActionCount: 1, createdAt: '2026-08-12T10:00:00+00:00', updatedAt: '2026-08-13T08:00:00+00:00' },
  ],
  achievementAttention: [
    { id: 2, title: 'تقويم الروابط الكيميائية', assessmentType: 'اختبار قصير', subject: 'الكيمياء', grade: 'العاشر', assessmentDate: '2026-08-10', term: 'الفصل الأول', academicYear: '2026/2027', teacherId: 2, teacherName: 'خالد الهنائي', maxScore: 40, studentCount: 30, averageScore: 21, highestScore: 37, lowestScore: 8, masteryThresholdPct: 60, masteryReferenceSource: 'بيانات معاينة غير تشغيلية — ليست معيارًا عُمانيًا', masteryReferenceYear: 'preview', masteryReferenceNote: 'القيمة معروضة لاختبار الواجهة فقط ويجب استبدالها في التشغيل الفعلي بمرجع عُماني معتمد.', masteredCount: 14, nearMasteryCount: 8, interventionCount: 8, notes: 'انخفاض نسبة الفئة المحققة للحد المسجل يستلزم تدخلًا موجّهًا وإعادة قياس، دون افتراض مهارة محددة من الدرجة الكلية وحدها.', status: 'recorded', masteryPercent: 47, averagePercent: 53, actionCount: 2, remedialActionCount: 1, enrichmentActionCount: 0, openActionCount: 1, overdueActionCount: 1, measuredActionCount: 0, targetMetActionCount: 0, unmeasuredCompletedActionCount: 0, impactReviewActionCount: 0, createdAt: '2026-08-10T10:00:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' },
    { id: 3, title: 'تقويم الوراثة والتنوع', assessmentType: 'مهمة أدائية', subject: 'العلوم', grade: 'التاسع', assessmentDate: '2026-08-12', term: 'الفصل الأول', academicYear: '2026/2027', teacherId: 3, teacherName: 'محمد المعمري', maxScore: 20, studentCount: 26, averageScore: 15.5, highestScore: 20, lowestScore: 8, masteryThresholdPct: 60, masteryReferenceSource: 'بيانات معاينة غير تشغيلية — ليست معيارًا عُمانيًا', masteryReferenceYear: 'preview', masteryReferenceNote: 'القيمة معروضة لاختبار الواجهة فقط ويجب استبدالها في التشغيل الفعلي بمرجع عُماني معتمد.', masteredCount: 19, nearMasteryCount: 5, interventionCount: 2, notes: 'سجل المعاينة يبيّن نسبة أعلى للفئة المحققة للحد المسجل، مع متابعة محدودة للفئة دون الحد.', status: 'reviewed', masteryPercent: 73, averagePercent: 78, actionCount: 1, remedialActionCount: 0, enrichmentActionCount: 0, openActionCount: 0, overdueActionCount: 0, measuredActionCount: 1, targetMetActionCount: 0, unmeasuredCompletedActionCount: 0, impactReviewActionCount: 1, createdAt: '2026-08-12T10:00:00+00:00', updatedAt: '2026-08-13T08:00:00+00:00' },
  ],
  documents: [
    { id: 1, requestId: 2, teacherId: 2, title: 'الخطة الفصلية', category: 'خطة فصلية', subject: 'الكيمياء', grade: 'العاشر', academicYear: '2026/2027', originalName: 'خطة_الكيمياء_الفصل_الأول.pdf', mimeType: 'application/pdf', sizeBytes: 735000, storageProvider: 'preview', status: 'inbox', uploadedAt: '2026-08-15T05:00:00+00:00' },
    { id: 2, requestId: 4, teacherId: 4, title: 'تحليل النتائج', category: 'تحليل نتائج', subject: 'الأحياء', grade: 'التاسع', academicYear: '2026/2027', originalName: 'تحليل_نتائج_الأحياء.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', sizeBytes: 184000, storageProvider: 'preview', status: 'approved', uploadedAt: '2026-08-14T05:00:00+00:00', approvedAt: '2026-08-15T05:00:00+00:00' },
  ],
  activities: [
    { id: 1, activity_type: 'document', title: 'خالد رفع الخطة الفصلية', detail: 'الكيمياء • الصف العاشر', created_at: '2026-08-15T05:00:00+00:00' },
    { id: 2, activity_type: 'request', title: 'طلب اختبار جديد', detail: 'الفيزياء • الصف العاشر', created_at: '2026-08-15T04:00:00+00:00' },
    { id: 3, activity_type: 'event', title: 'توثيق مبادرة اقرأ علمًا', detail: '31 مشاركًا', created_at: '2026-08-14T05:00:00+00:00' },
    { id: 4, activity_type: 'planning', title: 'تحديث وحدة الحركة والقوى', detail: 'الفيزياء • التقدم 65%', created_at: '2026-08-15T08:00:00+00:00' },
    { id: 5, activity_type: 'meeting', title: 'تحديث قرار: توزيع أعمال القسم', detail: 'قيد التنفيذ', created_at: '2026-08-14T04:30:00+00:00' },
    { id: 6, activity_type: 'supervision', title: 'تحديث متابعة: خالد الهنائي', detail: 'زيارة تطويرية • تحتاج متابعة', created_at: '2026-08-14T09:00:00+00:00' },
    { id: 7, activity_type: 'achievement', title: 'تسجيل نتيجة: تقويم الروابط الكيميائية', detail: 'الكيمياء • إتقان 47%', created_at: '2026-08-14T09:10:00+00:00' },
  ],
  drive: {
    configured: false,
    connected: false,
    rootFolderId: null,
    scope: 'https://www.googleapis.com/auth/drive.file',
    storageMode: 'local',
  },
};


const previewAssessmentDetails: Record<number, AchievementAssessmentDetails> = {
  1: {
    ...previewBootstrap.assessments[0],
    actions: [
      { id: 101, assessmentId: 1, actionType: 'remedial', title: 'مراجعة مركزة للطلبة دون حد الإتقان', targetGroup: '4 طلاب دون حد الإتقان', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', startDate: '2026-09-17', dueDate: '2026-09-24', status: 'in_progress', baseStatus: 'in_progress', baselineIndicator: 'إتقان 61% على مستوى الصف', targetIndicator: 'تحسن المجموعة المستهدفة في إعادة القياس', outcomeIndicator: '', notes: 'تستخدم أسئلة تشخيصية قصيرة قبل إعادة القياس.', createdAt: '2026-09-16T08:10:00+00:00', updatedAt: '2026-09-16T08:10:00+00:00' },
      { id: 102, assessmentId: 1, actionType: 'enrichment', title: 'مسألة إثرائية للطلبة المتقنين', targetGroup: 'الطلبة المتقنون', responsibleTeacherId: 6, responsibleName: 'ناصر الحوسني', startDate: '2026-09-18', dueDate: '2026-09-22', status: 'completed', baseStatus: 'completed', baselineIndicator: '', targetIndicator: 'إنتاج حلول متعددة', outcomeIndicator: 'أنجزت المهمة', notes: '', completedAt: '2026-09-22T08:00:00+00:00', createdAt: '2026-09-16T08:12:00+00:00', updatedAt: '2026-09-22T08:00:00+00:00', metric: { actionId: 102, metricName: 'مؤشر متابعة داخلي تجريبي', unit: 'نقطة', direction: 'higher_better', baselineValue: 10, targetValue: 15, outcomeValue: 16, measuredAt: '2026-09-22', referenceSource: 'هدف داخلي تجريبي في بيانات المعاينة فقط', referenceYear: '2026', referenceNote: 'ليس معيارًا وزاريًا ولا يستخدم في التشغيل الفعلي.', notes: '', impactStatus: 'target_met', impactDelta: 6, improvementValue: 6, targetGap: 0, createdAt: '2026-09-16T08:12:00+00:00', updatedAt: '2026-09-22T08:00:00+00:00' } },
    ],
    timeline: [{ id: 8101, activity_type: 'achievement', title: 'تسجيل نتيجة: الاختبار القصير الأول', detail: 'الفيزياء • العاشر', created_at: '2026-09-15T10:00:00+00:00' }],
    analysisReady: true,
  },
  2: {
    ...previewBootstrap.assessments[1],
    actions: [
      { id: 201, assessmentId: 2, actionType: 'remedial', title: 'جلسات مراجعة قصيرة قبل إعادة القياس', targetGroup: '8 طلاب يحتاجون تدخلًا', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', startDate: '2026-08-11', dueDate: '2026-08-14', status: 'overdue', baseStatus: 'in_progress', baselineIndicator: 'قيمة تجريبية في بيانات المعاينة', targetIndicator: 'هدف تجريبي مسجل في المعاينة فقط', outcomeIndicator: '', notes: 'يتم تحديد سبب التعثر باختبار تشخيصي قصير قبل التنفيذ.', createdAt: '2026-08-10T10:10:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00', metric: { actionId: 201, metricName: 'مؤشر متابعة داخلي تجريبي', unit: 'نقطة', direction: 'higher_better', baselineValue: 10, targetValue: 15, outcomeValue: null, measuredAt: null, referenceSource: 'هدف داخلي تجريبي في بيانات المعاينة فقط', referenceYear: '2026', referenceNote: 'ليس معيارًا وزاريًا ولا يستخدم في التشغيل الفعلي.', notes: '', impactStatus: 'pending', impactDelta: null, improvementValue: null, targetGap: null, createdAt: '2026-08-10T10:10:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' } },
      { id: 202, assessmentId: 2, actionType: 'followup', title: 'إعادة قياس بعد التدخل', targetGroup: 'المجموعة المستهدفة', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', startDate: '2026-08-17', dueDate: '2026-08-20', status: 'new', baseStatus: 'new', baselineIndicator: 'إتقان 47%', targetIndicator: 'هدف تجريبي مسجل في المعاينة فقط', outcomeIndicator: '', notes: '', createdAt: '2026-08-10T10:12:00+00:00', updatedAt: '2026-08-10T10:12:00+00:00' },
    ],
    timeline: [{ id: 8201, activity_type: 'achievement', title: 'تسجيل نتيجة: تقويم الروابط الكيميائية', detail: 'الكيمياء • العاشر', created_at: '2026-08-10T10:00:00+00:00' }],
    analysisReady: true,
  },
  3: { ...previewBootstrap.assessments[2], actions: [{ id: 301, assessmentId: 3, actionType: 'followup', title: 'متابعة طالبين في التقويم التالي', targetGroup: 'طالبان دون حد الإتقان', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', startDate: '2026-08-13', dueDate: '2026-08-20', status: 'completed', baseStatus: 'completed', baselineIndicator: '2 من 26 دون الحد', targetIndicator: 'تحسن في التقويم التالي', outcomeIndicator: 'تحسن مسجل', notes: '', completedAt: '2026-08-20T08:00:00+00:00', createdAt: '2026-08-13T08:00:00+00:00', updatedAt: '2026-08-20T08:00:00+00:00', metric: { actionId: 301, metricName: 'مؤشر متابعة داخلي تجريبي', unit: 'نقطة', direction: 'higher_better', baselineValue: 10, targetValue: 15, outcomeValue: 10, measuredAt: '2026-08-20', referenceSource: 'هدف داخلي تجريبي في بيانات المعاينة فقط', referenceYear: '2026', referenceNote: 'ليس معيارًا وزاريًا ولا يستخدم في التشغيل الفعلي.', notes: '', impactStatus: 'no_change', impactDelta: 0, improvementValue: 0, targetGap: 5, createdAt: '2026-08-13T08:00:00+00:00', updatedAt: '2026-08-20T08:00:00+00:00' } }], timeline: [{ id: 8301, activity_type: 'achievement', title: 'مراجعة نتيجة: تقويم الوراثة والتنوع', detail: 'العلوم • التاسع', created_at: '2026-08-13T08:00:00+00:00' }], analysisReady: true },
};

export function getPreviewAssessmentDetails(assessmentId: number): AchievementAssessmentDetails {
  const detail = previewAssessmentDetails[assessmentId];
  if (!detail) throw new Error('سجل التحصيل غير موجود في بيانات المعاينة.');
  return detail;
}


const previewSupervisionDetails: Record<number, SupervisionVisitDetails> = {
  1: { ...previewBootstrap.visits[0], actions: [], timeline: [{ id: 7101, activity_type: 'supervision', title: 'إنشاء زيارة: أحمد السالمي', detail: 'زيارة صفية • 2026-08-18', created_at: '2026-08-15T08:20:00+00:00' }], reportReady: false },
  2: {
    ...previewBootstrap.visits[1],
    actions: [
      { id: 201, visitId: 2, title: 'تنفيذ مهمة تعلم ثنائية قبل التقويم الختامي', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', dueDate: '2026-08-14', status: 'overdue', baseStatus: 'in_progress', notes: 'تجربتها في درسين وتوثيق ملاحظات المشاركة.', createdAt: '2026-08-10T09:10:00+00:00', updatedAt: '2026-08-14T09:00:00+00:00' },
      { id: 202, visitId: 2, title: 'إعداد سؤال خروج قصير مرتبط بهدف الدرس', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', dueDate: '2026-08-12', status: 'completed', baseStatus: 'completed', notes: 'تم تطبيقه وحفظ نموذج منه.', completedAt: '2026-08-12T10:00:00+00:00', createdAt: '2026-08-10T09:12:00+00:00', updatedAt: '2026-08-12T10:00:00+00:00' },
    ],
    timeline: [
      { id: 7203, activity_type: 'supervision', title: 'تحديث إجراء: تنفيذ مهمة تعلم ثنائية قبل التقويم الختامي', detail: 'in_progress', created_at: '2026-08-14T09:00:00+00:00' },
      { id: 7202, activity_type: 'supervision', title: 'إجراء متابعة: إعداد سؤال خروج قصير مرتبط بهدف الدرس', detail: 'completed', created_at: '2026-08-12T10:00:00+00:00' },
      { id: 7201, activity_type: 'supervision', title: 'إنشاء زيارة: خالد الهنائي', detail: 'زيارة تطويرية • 2026-08-10', created_at: '2026-08-10T09:00:00+00:00' },
    ],
    reportReady: true,
  },
  3: { ...previewBootstrap.visits[2], actions: [{ id: 301, visitId: 3, title: 'تطبيق التوصية ومراجعة أثرها', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', dueDate: '2026-08-12', status: 'completed', baseStatus: 'completed', notes: 'تم التحقق خلال زيارة المتابعة.', completedAt: '2026-08-12T08:20:00+00:00', createdAt: '2026-08-05T08:10:00+00:00', updatedAt: '2026-08-12T08:20:00+00:00' }], timeline: [{ id: 7301, activity_type: 'supervision', title: 'إغلاق متابعة: محمد المعمري', detail: 'closed', created_at: '2026-08-12T08:30:00+00:00' }], reportReady: true },
  4: { ...previewBootstrap.visits[3], actions: [], timeline: [{ id: 7401, activity_type: 'supervision', title: 'إنشاء زيارة: يوسف البلوشي', detail: 'زيارة صفية • 2026-08-13', created_at: '2026-08-11T08:00:00+00:00' }], reportReady: false },
  5: { ...previewBootstrap.visits[4], actions: [], timeline: [{ id: 7501, activity_type: 'supervision', title: 'تنفيذ زيارة: سالم الرواحي', detail: 'completed', created_at: '2026-08-12T08:00:00+00:00' }], reportReady: true },
};

export function getPreviewSupervisionVisit(visitId: number): SupervisionVisitDetails {
  const detail = previewSupervisionDetails[visitId];
  if (!detail) throw new Error('الزيارة غير موجودة في بيانات المعاينة.');
  return detail;
}


const previewPlanDetails: Record<number, CurriculumPlanDetails> = {
  1: {
    ...previewBootstrap.plans[0],
    units: [
      { id: 11, planId: 1, title: 'القياس والكميات الفيزيائية', sequence: 1, plannedStart: '2026-07-27', plannedEnd: '2026-08-04', progressPercent: 100, status: 'completed', effectiveStatus: 'completed', delayReason: '', notes: 'اكتملت وفق الخطة.', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', createdAt: '2026-08-15T07:50:00+00:00', updatedAt: '2026-08-15T07:58:00+00:00' },
      { ...previewBootstrap.planningAttention[0] },
      { id: 13, planId: 1, title: 'الطاقة والشغل', sequence: 3, plannedStart: '2026-08-14', plannedEnd: '2026-08-28', progressPercent: 20, status: 'in_progress', effectiveStatus: 'in_progress', delayReason: '', notes: '', responsibleTeacherId: 6, responsibleName: 'ناصر الحوسني', createdAt: '2026-08-15T07:50:00+00:00', updatedAt: '2026-08-15T08:00:00+00:00' },
    ],
    timeline: [
      { id: 6102, activity_type: 'planning', title: 'تحديث وحدة: الحركة والقوى', detail: 'التقدم 65%', created_at: '2026-08-15T08:00:00+00:00' },
      { id: 6101, activity_type: 'planning', title: 'إنشاء خطة: خطة الفيزياء للفصل الأول', detail: 'الفيزياء • العاشر • الفصل الأول', created_at: '2026-08-15T07:50:00+00:00' },
    ],
  },
  2: {
    ...previewBootstrap.plans[1],
    units: [
      { id: 21, planId: 2, title: 'بنية الذرة', sequence: 1, plannedStart: '2026-08-23', plannedEnd: '2026-09-03', progressPercent: 100, status: 'completed', effectiveStatus: 'completed', delayReason: '', notes: '', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', createdAt: '2026-08-15T07:52:00+00:00', updatedAt: '2026-08-15T08:02:00+00:00' },
      { id: 22, planId: 2, title: 'الترابط الكيميائي', sequence: 2, plannedStart: '2026-09-04', plannedEnd: '2026-09-17', progressPercent: 80, status: 'in_progress', effectiveStatus: 'in_progress', delayReason: '', notes: '', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', createdAt: '2026-08-15T07:52:00+00:00', updatedAt: '2026-08-15T08:02:00+00:00' },
      { id: 23, planId: 2, title: 'التفاعلات والحسابات', sequence: 3, plannedStart: '2026-09-18', plannedEnd: '2026-10-08', progressPercent: 0, status: 'not_started', effectiveStatus: 'not_started', delayReason: '', notes: '', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', createdAt: '2026-08-15T07:52:00+00:00', updatedAt: '2026-08-15T08:02:00+00:00' },
    ],
    timeline: [{ id: 6201, activity_type: 'planning', title: 'إنشاء خطة: خطة الكيمياء للفصل الأول', detail: 'الكيمياء • العاشر • الفصل الأول', created_at: '2026-08-15T07:52:00+00:00' }],
  },
  3: {
    ...previewBootstrap.plans[2],
    units: [
      { id: 31, planId: 3, title: 'الخلايا والأنظمة الحيوية', sequence: 1, plannedStart: '2026-07-27', plannedEnd: '2026-08-06', progressPercent: 100, status: 'completed', effectiveStatus: 'completed', delayReason: '', notes: '', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', createdAt: '2026-08-15T07:54:00+00:00', updatedAt: '2026-08-15T08:04:00+00:00' },
      { id: 33, planId: 3, title: 'التكاثر والنمو', sequence: 2, plannedStart: '2026-08-07', plannedEnd: '2026-08-12', progressPercent: 100, status: 'completed', effectiveStatus: 'completed', delayReason: '', notes: '', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', createdAt: '2026-08-15T07:54:00+00:00', updatedAt: '2026-08-15T08:04:00+00:00' },
      { ...previewBootstrap.planningAttention[1] },
    ],
    timeline: [{ id: 6301, activity_type: 'planning', title: 'تحديث وحدة: الوراثة والتنوع', detail: 'التقدم 55%', created_at: '2026-08-15T08:04:00+00:00' }],
  },
};

export function getPreviewPlanDetails(planId: number): CurriculumPlanDetails {
  const detail = previewPlanDetails[planId];
  if (!detail) throw new Error('الخطة غير موجودة في بيانات المعاينة.');
  return detail;
}

const previewMeetingDetails: Record<number, MeetingDetails> = {
  1: {
    ...previewBootstrap.meetings[0],
    agenda: 'مراجعة خطة القسم للفصل الأول\nتوحيد أدوات التخطيط الأسبوعي\nتنظيم الزيارات الصفية والتبادل المهني',
    discussionSummary: 'ناقش الفريق أولويات بداية الفصل، وتم الاتفاق على توحيد نموذج التخطيط وربط الزيارات بأهداف تطويرية واضحة لكل معلم.',
    notes: 'يراجع تنفيذ القرارات في الاجتماع القادم.',
    attendees: previewBootstrap.teachers.map((teacher) => ({ ...teacher, attendanceStatus: 'present' as const })),
    decisions: [
      { id: 101, meetingId: 1, title: 'توحيد نموذج التخطيط الأسبوعي', responsibleTeacherId: 2, responsibleName: 'خالد الهنائي', dueDate: '2026-09-10', status: 'in_progress', baseStatus: 'in_progress', notes: 'إعداد نموذج موحد مختصر قابل للتوثيق.', createdAt: '2026-08-15T06:30:00+00:00', updatedAt: '2026-08-15T06:30:00+00:00' },
      { id: 102, meetingId: 1, title: 'تجهيز خطة الزيارات الصفية', responsibleTeacherId: 3, responsibleName: 'محمد المعمري', dueDate: '2026-09-17', status: 'new', baseStatus: 'new', notes: 'توزيع الزيارات حسب الاحتياج المهني.', createdAt: '2026-08-15T06:31:00+00:00', updatedAt: '2026-08-15T06:31:00+00:00' },
      { id: 103, meetingId: 1, title: 'اعتماد توزيع منسقي الأنشطة', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', dueDate: '2026-09-05', status: 'completed', baseStatus: 'completed', notes: '', completedAt: '2026-08-15T07:00:00+00:00', createdAt: '2026-08-15T06:32:00+00:00', updatedAt: '2026-08-15T07:00:00+00:00' },
    ],
    timeline: [
      { id: 5003, activity_type: 'meeting', title: 'اعتماد قرار: توزيع منسقي الأنشطة', detail: 'مكتمل', created_at: '2026-08-15T07:00:00+00:00' },
      { id: 5002, activity_type: 'meeting', title: 'إضافة قرارات الاجتماع', detail: '3 قرارات قابلة للمتابعة', created_at: '2026-08-15T06:32:00+00:00' },
      { id: 5001, activity_type: 'meeting', title: 'إنشاء اجتماع: اجتماع قسم العلوم الأول', detail: '6 حاضرًا', created_at: '2026-08-15T06:20:00+00:00' },
    ],
    minutesReady: true,
  },
  2: {
    ...previewBootstrap.meetings[1],
    agenda: 'قراءة المؤشرات العامة\nتحديد الفئات المستهدفة\nتوزيع مسؤوليات المتابعة',
    discussionSummary: 'تم الاتفاق على التعامل مع النتائج كمدخل تشخيصي وتحديد تدخلات قابلة للقياس بدل الاكتفاء بوصف الانخفاض.',
    notes: '',
    attendees: previewBootstrap.teachers.slice(0, 4).map((teacher) => ({ ...teacher, attendanceStatus: 'present' as const })),
    decisions: [
      { id: 201, meetingId: 2, title: 'تحديد الطلبة المستهدفين بالتدخل', responsibleTeacherId: 4, responsibleName: 'سالم الرواحي', dueDate: '2026-09-28', status: 'new', baseStatus: 'new', notes: '', createdAt: '2026-08-15T06:32:00+00:00', updatedAt: '2026-08-15T06:32:00+00:00' },
      { id: 202, meetingId: 2, title: 'إعداد نموذج متابعة الأثر', responsibleTeacherId: 6, responsibleName: 'ناصر الحوسني', dueDate: '2026-10-02', status: 'completed', baseStatus: 'completed', notes: '', completedAt: '2026-08-15T07:15:00+00:00', createdAt: '2026-08-15T06:35:00+00:00', updatedAt: '2026-08-15T07:15:00+00:00' },
    ],
    timeline: [
      { id: 5101, activity_type: 'meeting', title: 'إنشاء اجتماع: مراجعة نتائج الاختبار القصير', detail: '4 حاضرين', created_at: '2026-08-15T06:25:00+00:00' },
    ],
    minutesReady: true,
  },
  3: {
    ...previewBootstrap.meetings[2],
    agenda: 'توزيع أعمال القسم\nالاستعداد للخطط الفصلية\nتنظيم ملفات المادة',
    discussionSummary: 'راجع الفريق جاهزية بداية العام وحدد مسؤوليات أساسية لضمان وضوح العمل منذ الأسبوع الأول.',
    notes: 'قرار توزيع الأعمال يحتاج إغلاقًا.',
    attendees: previewBootstrap.teachers.slice(0, 5).map((teacher) => ({ ...teacher, attendanceStatus: 'present' as const })),
    decisions: [
      { id: 301, meetingId: 3, title: 'تحديث توزيع أعمال القسم', responsibleTeacherId: 1, responsibleName: 'أحمد السالمي', dueDate: '2026-08-14', status: 'overdue', baseStatus: 'in_progress', notes: 'اعتماد النسخة النهائية بعد مراجعة الأنصبة.', createdAt: '2026-08-10T06:00:00+00:00', updatedAt: '2026-08-14T05:00:00+00:00' },
      { id: 302, meetingId: 3, title: 'إنشاء مجلدات العام الدراسي', responsibleTeacherId: 5, responsibleName: 'يوسف البلوشي', dueDate: '2026-08-12', status: 'completed', baseStatus: 'completed', notes: '', completedAt: '2026-08-12T08:00:00+00:00', createdAt: '2026-08-10T06:10:00+00:00', updatedAt: '2026-08-12T08:00:00+00:00' },
    ],
    timeline: [
      { id: 5202, activity_type: 'meeting', title: 'تحديث قرار: توزيع أعمال القسم', detail: 'قيد التنفيذ', created_at: '2026-08-14T05:00:00+00:00' },
      { id: 5201, activity_type: 'meeting', title: 'إنشاء اجتماع: الاستعداد لبداية العام الدراسي', detail: '5 حاضرين', created_at: '2026-08-10T05:00:00+00:00' },
    ],
    minutesReady: true,
  },
};

export function getPreviewMeetingDetails(meetingId: number): MeetingDetails {
  const detail = previewMeetingDetails[meetingId];
  if (!detail) throw new Error('الاجتماع غير موجود في بيانات المعاينة.');
  return detail;
}

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
      visitCount: previewBootstrap.visits.filter((item) => item.teacherId === teacherId).length,
      openFollowupCount: previewBootstrap.visits.filter((item) => item.teacherId === teacherId && item.status === 'needs_followup').length,
    },
  };
}

function previewStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    active: 'نشطة', completed: 'مكتملة', archived: 'مؤرشفة', planned: 'مخططة', held: 'منفذة',
    cancelled: 'ملغاة', needs_followup: 'تحتاج متابعة', closed: 'مغلقة', overdue: 'متأخرة',
    draft: 'مسودة', recorded: 'مسجلة', reviewed: 'مراجعة مكتملة', new: 'جديد', in_progress: 'قيد التنفيذ',
    approved: 'معتمد', review: 'قيد المراجعة', received: 'مستلم', waiting_upload: 'بانتظار الرفع', late: 'متأخر',
  };
  return labels[value] || value;
}

function previewReportSection(id: string, title: string, columns: Array<[string, string]>, rows: OfficialReportSection['rows'], description = ''): OfficialReportSection {
  return { id, title, description, columns: columns.map(([key, label]) => ({ key, label })), rows };
}

function previewPct(numerator: number, denominator: number): number {
  return denominator ? Math.round((100 * numerator) / denominator) : 0;
}

export function getPreviewOfficialReport(input: OfficialReportQuery): OfficialReport {
  const { reportType, academicYear, term, teacherId } = input;
  const termFilter = term === 'العام كاملًا' ? '' : term;
  const plans = previewBootstrap.plans.filter((item) => item.academicYear === academicYear && (!termFilter || item.term === termFilter));
  const assessments = previewBootstrap.assessments.filter((item) => item.academicYear === academicYear && (!termFilter || item.term === termFilter));
  const visits = previewBootstrap.visits.filter((item) => item.academicYear === academicYear);
  const meetings = previewBootstrap.meetings.filter((item) => item.academicYear === academicYear);
  const events = previewBootstrap.events;
  const generatedAt = new Date().toISOString();
  const base: OfficialReport = { reportType, academicYear, term, generatedAt, teacher: null, title: '', subtitle: '', summary: '', metrics: [], sections: [], sourceCounts: {} };

  if (reportType === 'teacher') {
    const teacher = previewBootstrap.teachers.find((item) => item.id === teacherId);
    if (!teacher) throw new Error('اختر معلمًا موجودًا لإنشاء تقرير المعلم.');
    const requests = previewBootstrap.requests.filter((item) => item.teacherId === teacher.id);
    const documents = previewBootstrap.documents.filter((item) => item.teacherId === teacher.id);
    const teacherVisits = visits.filter((item) => item.teacherId === teacher.id);
    const teacherAssessments = assessments.filter((item) => item.teacherId === teacher.id);
    return {
      ...base, teacher,
      title: `التقرير المهني للمعلم: ${teacher.name}`,
      subtitle: `سجل مهني وتشغيلي خلال ${term} من العام الدراسي ${academicYear}`,
      summary: 'يعرض التقرير الأعمال المرتبطة مباشرة بالمعلم من الملفات والتحصيل والإشراف والمشاركات دون تحويل المؤشرات إلى أحكام غير موثقة.',
      metrics: [
        { label: 'اكتمال الملف', value: `${teacher.cvCompletion}%` },
        { label: 'الوثائق', value: documents.length },
        { label: 'الزيارات', value: teacherVisits.length },
        { label: 'التقويمات', value: teacherAssessments.length },
      ],
      sections: [
        previewReportSection('requests', 'الطلبات', [['title','الطلب'],['status','الحالة'],['subject','المادة']], requests.map((item) => ({ title: item.title, status: previewStatusLabel(item.status), subject: item.subject }))),
        previewReportSection('visits', 'الزيارات والإشراف', [['date','التاريخ'],['type','النوع'],['lesson','الدرس'],['status','الحالة']], teacherVisits.map((item) => ({ date: item.visitDate, type: item.visitType, lesson: item.lessonTitle || '—', status: previewStatusLabel(item.effectiveStatus) }))),
        previewReportSection('assessments', 'التحصيل', [['title','التقويم'],['scope','النطاق'],['mastery','وفق الحد المسجل'],['average','المتوسط']], teacherAssessments.map((item) => ({ title: item.title, scope: `${item.subject} • ${item.grade}`, mastery: `${item.masteryPercent}%`, average: `${item.averagePercent}%` }))),
      ],
      sourceCounts: { requests: requests.length, documents: documents.length, visits: teacherVisits.length, assessments: teacherAssessments.length },
    };
  }

  if (reportType === 'planning') return {
    ...base, title: 'تقرير التخطيط ومتابعة المنهج', subtitle: `${term} • ${academicYear}`,
    summary: 'يعرض التقرير تقدم الخطط والوحدات المتأخرة كما هي مسجلة في مرصد الإنجازات.',
    metrics: [
      { label: 'الخطط', value: plans.length },
      { label: 'متوسط الإنجاز', value: `${plans.length ? Math.round(plans.reduce((s,x)=>s+x.progressPercent,0)/plans.length) : 0}%` },
      { label: 'الوحدات المتأخرة', value: plans.reduce((s,x)=>s+x.overdueUnitCount,0) },
    ],
    sections: [previewReportSection('plans','الخطط',[['title','الخطة'],['scope','المادة والصف'],['owner','المسؤول'],['progress','الإنجاز'],['status','الحالة']], plans.map((x)=>({title:x.title,scope:`${x.subject} • ${x.grade}`,owner:x.ownerName||'—',progress:`${x.progressPercent}%`,status:previewStatusLabel(x.status)})))],
    sourceCounts: { plans: plans.length },
  };

  if (reportType === 'achievement') {
    const rows = assessments.filter((item) => item.status !== 'draft');
    const students = rows.reduce((s,x)=>s+x.studentCount,0); const mastered = rows.reduce((s,x)=>s+x.masteredCount,0);
    const actions = rows.flatMap((item) => getPreviewAssessmentDetails(item.id).actions.map((action) => ({ item, action })));
    const measured = actions.filter(({ action }) => action.metric?.outcomeValue !== null && action.metric?.outcomeValue !== undefined).length;
    const targetMet = actions.filter(({ action }) => action.metric?.impactStatus === 'target_met').length;
    const impactLabel = (value?: string | null) => ({pending:'لم يُقَس بعد',target_met:'حقق الهدف المسجل',improved_not_met:'تحسن ولم يبلغ الهدف المسجل',no_change:'لم يحدث تغير',regressed:'تراجع المؤشر'} as Record<string,string>)[value || ''] || '—';
    return { ...base, title:'تقرير التحصيل والنتائج', subtitle:`${term} • ${academicYear}`, summary:'يجمع التقرير نتائج التقويمات والتدخلات وقياس أثرها كما سُجلت. لا يضع حدًا تربويًا من تلقاء نفسه ولا يحول الدرجة الكلية إلى تشخيص مهاري غير موجود في البيانات.', metrics:[{label:'التقويمات',value:rows.length},{label:'الطلبة',value:students},{label:'نسبة فئة الإتقان وفق الحدود المسجلة',value:`${previewPct(mastered,students)}%`},{label:'تدخلات مفتوحة',value:rows.reduce((s,x)=>s+x.openActionCount,0)},{label:'تدخلات مقاسة',value:measured},{label:'حققت الهدف المسجل',value:targetMet,detail:measured?`${previewPct(targetMet,measured)}% من التدخلات المقاسة`:'لا توجد قياسات نهائية'}], sections:[previewReportSection('assessments','التقويمات',[['title','التقويم'],['scope','النطاق'],['teacher','المعلم'],['average','المتوسط'],['mastery','فئة الإتقان وفق الحد المسجل']],rows.map((x)=>({title:x.title,scope:`${x.subject} • ${x.grade}`,teacher:x.teacherName||'—',average:`${x.averagePercent}%`,mastery:`${x.masteryPercent}%`}))),previewReportSection('interventions','التدخلات والمتابعات وقياس الأثر',[['title','التدخل'],['type','النوع'],['targetGroup','الفئة المستهدفة'],['metric','المؤشر'],['baseline','خط الأساس'],['target','الهدف المسجل'],['outcome','النتيجة'],['impact','الأثر الحسابي'],['reference','مصدر المعيار/الهدف']],actions.map(({action})=>({title:action.title,type:action.actionType==='remedial'?'علاجي':action.actionType==='enrichment'?'إثرائي':'متابعة',targetGroup:action.targetGroup||'—',metric:action.metric?.metricName||'—',baseline:action.metric?`${action.metric.baselineValue}${action.metric.unit?` ${action.metric.unit}`:''}`:'—',target:action.metric?`${action.metric.targetValue}${action.metric.unit?` ${action.metric.unit}`:''}`:'—',outcome:action.metric?.outcomeValue!==null&&action.metric?.outcomeValue!==undefined?`${action.metric.outcomeValue}${action.metric.unit?` ${action.metric.unit}`:''}`:'—',impact:action.metric?impactLabel(action.metric.impactStatus):'لم يُسجل مقياس',reference:action.metric?.referenceSource||'هدف برنامج داخلي غير منسوب لمرجع'})),'الحكم هنا حسابي بالنسبة للهدف المسجل فقط، ولا يعني اعتماد معيار تربوي ما لم يكن مصدره موثقًا.')], sourceCounts:{assessments:rows.length,interventions:actions.length,measuredInterventions:measured} };
  }


  if (reportType === 'supervision') return { ...base, title:'تقرير الإشراف الفني والزيارات', subtitle:`العام الدراسي ${academicYear}`, summary:'يوثق التقرير الزيارات وحالات المتابعة من السجلات الفعلية.', metrics:[{label:'الزيارات',value:visits.length},{label:'مغلقة',value:visits.filter(x=>x.status==='closed').length},{label:'متابعات مفتوحة',value:visits.reduce((s,x)=>s+x.openActionCount,0)}], sections:[previewReportSection('visits','الزيارات',[['teacher','المعلم'],['date','التاريخ'],['type','النوع'],['status','الحالة']],visits.map((x)=>({teacher:x.teacherName,date:x.visitDate,type:x.visitType,status:previewStatusLabel(x.effectiveStatus)})))], sourceCounts:{visits:visits.length} };

  if (reportType === 'meetings') {
    const total=meetings.reduce((s,x)=>s+x.decisionCount,0), done=meetings.reduce((s,x)=>s+x.completedDecisionCount,0);
    return { ...base, title:'تقرير الاجتماعات والقرارات', subtitle:`العام الدراسي ${academicYear}`, summary:'يعرض التقرير الاجتماعات والقرارات وحالة التنفيذ.', metrics:[{label:'الاجتماعات',value:meetings.length},{label:'القرارات',value:total},{label:'نسبة التنفيذ',value:`${previewPct(done,total)}%`},{label:'قرارات مفتوحة',value:meetings.reduce((s,x)=>s+x.openDecisionCount,0)}], sections:[previewReportSection('meetings','الاجتماعات',[['title','الاجتماع'],['date','التاريخ'],['type','النوع'],['decisions','القرارات'],['open','مفتوحة']],meetings.map((x)=>({title:x.title,date:x.meetingDate,type:x.meetingType,decisions:x.decisionCount,open:x.openDecisionCount})))], sourceCounts:{meetings:meetings.length,decisions:total} };
  }

  if (reportType === 'events') return { ...base, title:'تقرير الفعاليات والتوثيق', subtitle:`العام الدراسي ${academicYear}`, summary:'يلخص التقرير الفعاليات والمبادرات والمشاركة والأدلة التوثيقية.', metrics:[{label:'الفعاليات',value:events.length},{label:'المشاركون',value:events.reduce((s,x)=>s+x.participantCount,0)},{label:'الأدلة',value:events.reduce((s,x)=>s+(x.mediaCount||0),0)}], sections:[previewReportSection('events','الفعاليات',[['title','الفعالية'],['date','التاريخ'],['type','النوع'],['participants','المشاركون'],['evidence','الأدلة']],events.map((x)=>({title:x.title,date:x.eventDate,type:x.eventType,participants:x.participantCount,evidence:x.mediaCount||0})))], sourceCounts:{events:events.length} };

  const activePlans=plans.filter((x)=>x.status==='active'); const students=assessments.filter(x=>x.status!=='draft').reduce((s,x)=>s+x.studentCount,0); const mastered=assessments.filter(x=>x.status!=='draft').reduce((s,x)=>s+x.masteredCount,0); const decisions=meetings.reduce((s,x)=>s+x.decisionCount,0); const done=meetings.reduce((s,x)=>s+x.completedDecisionCount,0);
  return { ...base, title:'التقرير الشامل لأعمال القسم', subtitle:`ملخص مؤسسي لأعمال القسم خلال ${term} من العام الدراسي ${academicYear}`, summary:'يجمع هذا التقرير مؤشرات المعلمين والتخطيط والتحصيل والإشراف والاجتماعات والفعاليات في وثيقة واحدة مرتبطة بسجلاتها الأصلية.', metrics:[{label:'المعلمون',value:previewBootstrap.teachers.length},{label:'تقدم الخطط',value:`${activePlans.length?Math.round(activePlans.reduce((s,x)=>s+x.progressPercent,0)/activePlans.length):0}%`},{label:'نسبة الفئة المحققة للحدود المسجلة',value:`${previewPct(mastered,students)}%`},{label:'إغلاق الزيارات',value:`${previewPct(visits.filter(x=>x.status==='closed').length,visits.length)}%`},{label:'تنفيذ القرارات',value:`${previewPct(done,decisions)}%`}], sections:[previewReportSection('teachers','المعلمون',[['name','المعلم'],['subject','المادة'],['workload','النصاب'],['cv','اكتمال الملف']],previewBootstrap.teachers.map(x=>({name:x.name,subject:x.subject,workload:x.workload,cv:`${x.cvCompletion}%`}))),previewReportSection('planning','التخطيط والمنهج',[['title','الخطة'],['scope','النطاق'],['progress','الإنجاز']],plans.map(x=>({title:x.title,scope:`${x.subject} • ${x.grade}`,progress:`${x.progressPercent}%`}))),previewReportSection('achievement','التحصيل',[['title','التقويم'],['mastery','وفق الحد المسجل'],['average','المتوسط']],assessments.filter(x=>x.status!=='draft').map(x=>({title:x.title,mastery:`${x.masteryPercent}%`,average:`${x.averagePercent}%`}))),previewReportSection('events','الفعاليات',[['title','الفعالية'],['date','التاريخ'],['participants','المشاركون']],events.map(x=>({title:x.title,date:x.eventDate,participants:x.participantCount})))], sourceCounts:{teachers:previewBootstrap.teachers.length,plans:plans.length,assessments:assessments.length,visits:visits.length,meetings:meetings.length,events:events.length} };
}


function previewAcademicYearFromDate(value?: string | null): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  if (!Number.isFinite(year) || month < 1 || month > 12) return null;
  const first = month >= 8 ? year : year - 1;
  return `${first}/${first + 1}`;
}

function previewArchiveScope(academicYear: string): ArchiveYearDetail {
  const plans = previewBootstrap.plans.filter((item) => item.academicYear === academicYear);
  const assessments = previewBootstrap.assessments.filter((item) => item.academicYear === academicYear);
  const visits = previewBootstrap.visits.filter((item) => item.academicYear === academicYear);
  const meetings = previewBootstrap.meetings.filter((item) => item.academicYear === academicYear);
  const events = previewBootstrap.events.filter((item) => previewAcademicYearFromDate(item.eventDate) === academicYear);
  const documents = previewBootstrap.documents.filter((item) => (item.academicYear || previewAcademicYearFromDate(item.uploadedAt)) === academicYear);
  const requests = previewBootstrap.requests.filter((item) => previewAcademicYearFromDate(item.createdAt) === academicYear);

  const linked = new Map<number, number>();
  const addTeacher = (id?: number | null) => { if (id) linked.set(id, (linked.get(id) || 0) + 1); };
  requests.forEach((item) => addTeacher(item.teacherId));
  documents.forEach((item) => addTeacher(item.teacherId));
  plans.forEach((item) => addTeacher(item.ownerTeacherId));
  visits.forEach((item) => addTeacher(item.teacherId));
  assessments.forEach((item) => addTeacher(item.teacherId));
  events.forEach((event) => getPreviewEventDetails(event.id).teachers.forEach((teacher) => addTeacher(teacher.id)));
  meetings.forEach((meeting) => {
    previewMeetingDetails[meeting.id]?.attendees.forEach((teacher) => addTeacher(teacher.id));
    previewMeetingDetails[meeting.id]?.decisions.forEach((decision) => addTeacher(decision.responsibleTeacherId));
  });

  const teachers = previewBootstrap.teachers
    .filter((teacher) => linked.has(teacher.id))
    .map((teacher) => ({ id: teacher.id, name: teacher.name, subject: teacher.subject, linkedRecords: linked.get(teacher.id) || 0 }))
    .sort((a, b) => b.linkedRecords - a.linkedRecords || a.name.localeCompare(b.name, 'ar'));

  const decisions = meetings.reduce((sum, item) => sum + item.decisionCount, 0);
  const sourceCounts = {
    teachers: teachers.length,
    plans: plans.length,
    assessments: assessments.length,
    visits: visits.length,
    meetings: meetings.length,
    decisions,
    events: events.length,
    documents: documents.length,
    requests: requests.length,
  };
  const totalRecords = plans.length + assessments.length + visits.length + meetings.length + events.length + documents.length + requests.length;
  const dates = [
    ...plans.map((item) => item.updatedAt),
    ...assessments.map((item) => item.updatedAt),
    ...visits.map((item) => item.updatedAt),
    ...meetings.map((item) => item.updatedAt),
    ...events.map((item) => item.updatedAt),
    ...documents.map((item) => item.uploadedAt),
    ...requests.map((item) => item.updatedAt),
  ].filter(Boolean).sort();

  return {
    academicYear,
    isCurrent: academicYear === previewBootstrap.academicYear,
    generatedAt: new Date().toISOString(),
    totalRecords,
    teacherCount: teachers.length,
    documentCount: documents.length,
    decisionCount: decisions,
    latestRecordAt: dates.at(-1) || null,
    sourceCounts,
    coverage: [
      { id: 'planning', label: 'التخطيط والمنهج', count: plans.length, detail: `${plans.reduce((sum, item) => sum + item.unitCount, 0)} وحدة منهج` },
      { id: 'achievement', label: 'التحصيل والنتائج', count: assessments.length, detail: `${assessments.reduce((sum, item) => sum + item.openActionCount, 0)} تدخلات مفتوحة • ${assessments.reduce((sum, item) => sum + item.measuredActionCount, 0)} مقاسة` },
      { id: 'supervision', label: 'الإشراف والمتابعة', count: visits.length, detail: `${visits.reduce((sum, item) => sum + item.openActionCount, 0)} متابعات مفتوحة` },
      { id: 'meetings', label: 'الاجتماعات والقرارات', count: meetings.length, detail: `${decisions} قرارًا` },
      { id: 'events', label: 'الفعاليات والتوثيق', count: events.length, detail: `${events.reduce((sum, item) => sum + (item.mediaCount || 0), 0)} أدلة` },
      { id: 'documents', label: 'الوثائق والطلبات', count: documents.length + requests.length, detail: `${documents.length} وثيقة • ${requests.length} طلبات` },
    ],
    teachers,
    sections: [
      previewReportSection('planning', 'التخطيط والمنهج', [['title','الخطة'],['scope','النطاق'],['term','الفصل'],['owner','المسؤول'],['progress','الإنجاز'],['status','الحالة']], plans.map((item) => ({ title: item.title, scope: `${item.subject} • ${item.grade}`, term: item.term, owner: item.ownerName || '—', progress: `${item.progressPercent}%`, status: previewStatusLabel(item.status) }))),
      previewReportSection('achievement', 'التحصيل والنتائج', [['title','التقويم'],['scope','النطاق'],['term','الفصل'],['teacher','المعلم'],['mastery','فئة الإتقان وفق الحد المسجل'],['actions','تدخلات مفتوحة'],['measured','تدخلات مقاسة']], assessments.map((item) => ({ title: item.title, scope: `${item.subject} • ${item.grade}`, term: item.term, teacher: item.teacherName || '—', mastery: `${item.masteryPercent}%`, actions: item.openActionCount, measured: item.measuredActionCount }))),
      previewReportSection('supervision', 'الإشراف والمتابعة', [['teacher','المعلم'],['date','التاريخ'],['type','النوع'],['lesson','الدرس'],['status','الحالة'],['followup','متابعة']], visits.map((item) => ({ teacher: item.teacherName, date: item.visitDate, type: item.visitType, lesson: item.lessonTitle || '—', status: previewStatusLabel(item.effectiveStatus), followup: item.openActionCount }))),
      previewReportSection('meetings', 'الاجتماعات والقرارات', [['title','الاجتماع'],['date','التاريخ'],['type','النوع'],['decisions','القرارات'],['open','مفتوحة']], meetings.map((item) => ({ title: item.title, date: item.meetingDate, type: item.meetingType, decisions: item.decisionCount, open: item.openDecisionCount }))),
      previewReportSection('events', 'الفعاليات والتوثيق', [['title','الفعالية'],['date','التاريخ'],['type','النوع'],['participants','المشاركون'],['evidence','الأدلة']], events.map((item) => ({ title: item.title, date: item.eventDate, type: item.eventType, participants: item.participantCount, evidence: item.mediaCount || 0 }))),
      previewReportSection('documents', 'الوثائق والمراجع', [['title','الوثيقة'],['category','النوع'],['scope','النطاق'],['status','الحالة'],['uploaded','تاريخ الرفع']], documents.map((item) => ({ title: item.title, category: item.category, scope: [item.subject, item.grade].filter(Boolean).join(' • ') || '—', status: previewStatusLabel(item.status), uploaded: item.uploadedAt.slice(0, 10) }))),
      previewReportSection('requests', 'طلبات الملفات', [['title','الطلب'],['teacher','المعلم'],['type','النوع'],['scope','النطاق'],['status','الحالة']], requests.map((item) => ({ title: item.title, teacher: item.teacherName, type: item.requestType, scope: `${item.subject} • ${item.grade}`, status: previewStatusLabel(item.status) }))),
    ],
  };
}

export function getPreviewArchiveYears(): ArchiveYearsIndex {
  const years = new Set<string>([previewBootstrap.academicYear]);
  previewBootstrap.plans.forEach((item) => years.add(item.academicYear));
  previewBootstrap.assessments.forEach((item) => years.add(item.academicYear));
  previewBootstrap.visits.forEach((item) => years.add(item.academicYear));
  previewBootstrap.meetings.forEach((item) => years.add(item.academicYear));
  previewBootstrap.documents.forEach((item) => { const year = item.academicYear || previewAcademicYearFromDate(item.uploadedAt); if (year) years.add(year); });
  previewBootstrap.events.forEach((item) => { const year = previewAcademicYearFromDate(item.eventDate); if (year) years.add(year); });
  previewBootstrap.requests.forEach((item) => { const year = previewAcademicYearFromDate(item.createdAt); if (year) years.add(year); });
  const ordered = [...years].sort((a, b) => Number(b.slice(0, 4)) - Number(a.slice(0, 4)));
  return {
    currentAcademicYear: previewBootstrap.academicYear,
    generatedAt: new Date().toISOString(),
    years: ordered.map((year) => {
      const detail = previewArchiveScope(year);
      const { generatedAt: _generatedAt, coverage: _coverage, teachers: _teachers, sections: _sections, ...summary } = detail;
      return summary;
    }),
  };
}

export function getPreviewArchiveYear(academicYear: string): ArchiveYearDetail {
  const index = getPreviewArchiveYears();
  if (!index.years.some((item) => item.academicYear === academicYear)) throw new Error('العام الدراسي غير موجود في الأرشيف.');
  return previewArchiveScope(academicYear);
}
