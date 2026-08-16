import type { SearchQuery, SearchResponse, SearchResult, SearchSection } from '../types';
import {
  getPreviewArchiveYear,
  getPreviewArchiveYears,
  getPreviewAssessmentDetails,
  getPreviewEventDetails,
  getPreviewMeetingDetails,
  getPreviewPlanDetails,
  getPreviewSupervisionVisit,
  getPreviewTeacherProfile,
  previewBootstrap,
} from './preview';

const sectionLabels: Record<Exclude<SearchSection, 'all'>, string> = {
  teachers: 'المعلمون', planning: 'التخطيط والمنهج', achievement: 'التحصيل والنتائج', supervision: 'الإشراف والمتابعة',
  requests: 'طلبات الملفات', meetings: 'الاجتماعات والقرارات', events: 'الفعاليات والتوثيق', documents: 'الوثائق والمراجع',
};

const statusLabels: Record<string, string> = {
  waiting_upload: 'بانتظار الرفع', received: 'تم الاستلام', review: 'للمراجعة', approved: 'معتمد', needs_revision: 'يحتاج تعديل', late: 'متأخر', cancelled: 'ملغي',
  planned: 'مخطط', held: 'منعقد', active: 'نشطة', archived: 'مؤرشفة', not_started: 'لم تبدأ', in_progress: 'قيد التنفيذ', completed: 'مكتمل', needs_followup: 'تحتاج متابعة', closed: 'مغلقة', overdue: 'متأخر', draft: 'مسودة', recorded: 'مسجلة', reviewed: 'مراجعة مكتملة', new: 'جديد',
};

function normalizeArabic(value = ''): string {
  return value.normalize('NFKC').toLocaleLowerCase('ar').replace(/ـ/g, '').replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, '')
    .replace(/[أإآٱ]/g, 'ا').replace(/ؤ/g, 'و').replace(/ئ/g, 'ي').replace(/ى/g, 'ي').replace(/\s+/g, ' ').trim();
}

function yearFromDate(value?: string | null): string | null {
  const match = value?.match(/^(\d{4})-(\d{2})/);
  if (!match) return null;
  const year = Number(match[1]); const month = Number(match[2]);
  if (month < 1 || month > 12) return null;
  const first = month >= 8 ? year : year - 1;
  return `${first}/${first + 1}`;
}

function excerpt(...values: Array<string | number | null | undefined>): string {
  const text = values.filter((value) => value !== null && value !== undefined && String(value).trim()).map(String).join(' • ').replace(/\s+/g, ' ');
  return text.length > 170 ? `${text.slice(0, 169).trim()}…` : text;
}

function score(query: string, title: string, searchable: string): number {
  const q = normalizeArabic(query); const t = normalizeArabic(title); const h = normalizeArabic(searchable);
  if (!q || !h) return 0;
  if (t === q) return 120; if (t.startsWith(q)) return 108; if (t.includes(q)) return 96; if (h.includes(q)) return 78;
  const tokens = q.split(' ').filter(Boolean); const titleHits = tokens.filter((token) => t.includes(token)).length; const hits = tokens.filter((token) => h.includes(token)).length;
  if (titleHits === tokens.length) return 88; if (hits === tokens.length) return 66;
  const required = tokens.length > 1 ? Math.max(2, Math.ceil(tokens.length / 2)) : 1;
  return hits >= required ? 30 + hits * 8 : 0;
}

type Candidate = Omit<SearchResult, 'key' | 'sectionLabel'> & { searchable: string };

export function getPreviewGlobalSearch(input: SearchQuery): SearchResponse {
  const q = input.q.trim().replace(/\s+/g, ' ').slice(0, 120);
  const normalizedQuery = normalizeArabic(q);
  const section = input.section || 'all'; const academicYear = input.academicYear || 'all'; const limit = Math.max(1, Math.min(input.limit || 40, 100));
  const candidates: Candidate[] = [];
  const use = (value: Exclude<SearchSection, 'all'>) => section === 'all' || section === value;
  const inYear = (value?: string | null) => academicYear === 'all' || value === academicYear;

  if (normalizedQuery.length >= 2 && use('teachers')) {
    const linked = academicYear === 'all' ? null : new Set(
      getPreviewArchiveYears().years.some((item) => item.academicYear === academicYear)
        ? getPreviewArchiveYear(academicYear).teachers.map((teacher) => teacher.id)
        : [],
    );
    previewBootstrap.teachers.forEach((teacher) => {
      if (linked && !linked.has(teacher.id)) return;
      const profile = getPreviewTeacherProfile(teacher.id);
      candidates.push({ section: 'teachers', entityType: 'teacher', entityId: teacher.id, title: teacher.name, subtitle: excerpt(teacher.subject, teacher.specialization || teacher.qualification), excerpt: excerpt(profile.profile.professionalSummary, profile.profile.responsibilities, ...profile.cvItems.map((item) => item.title)), academicYear: academicYear === 'all' ? null : academicYear, subject: teacher.subject, teacherName: teacher.name, targetView: 'teachers', targetId: teacher.id, searchable: excerpt(teacher.name, teacher.subject, teacher.specialization, teacher.qualification, teacher.email, teacher.phone, profile.profile.employeeNumber, profile.profile.grades, profile.profile.responsibilities, profile.profile.professionalSummary, ...profile.cvItems.flatMap((item) => [item.title, item.organization, item.description])) });
    });
  }

  if (normalizedQuery.length >= 2 && use('planning')) previewBootstrap.plans.filter((plan) => inYear(plan.academicYear)).forEach((plan) => {
    candidates.push({ section: 'planning', entityType: 'plan', entityId: plan.id, title: plan.title, subtitle: excerpt(plan.subject, plan.grade, plan.term, plan.ownerName), excerpt: excerpt(plan.notes), academicYear: plan.academicYear, date: plan.updatedAt, status: statusLabels[plan.status] || plan.status, subject: plan.subject, grade: plan.grade, teacherName: plan.ownerName, targetView: 'planning', targetId: plan.id, searchable: excerpt(plan.title, plan.subject, plan.grade, plan.term, plan.notes, plan.ownerName, plan.status) });
    getPreviewPlanDetails(plan.id).units.forEach((unit) => candidates.push({ section: 'planning', entityType: 'curriculum_unit', entityId: unit.id, title: unit.title, subtitle: excerpt('وحدة منهج', plan.title, plan.subject, plan.grade), excerpt: excerpt(unit.delayReason, unit.notes), academicYear: plan.academicYear, date: unit.plannedEnd || unit.plannedStart, status: statusLabels[unit.effectiveStatus] || unit.effectiveStatus, subject: plan.subject, grade: plan.grade, teacherName: unit.responsibleName, targetView: 'planning', targetId: plan.id, searchable: excerpt(unit.title, plan.title, plan.subject, plan.grade, unit.delayReason, unit.notes, unit.responsibleName, unit.effectiveStatus) }));
  });

  if (normalizedQuery.length >= 2 && use('achievement')) previewBootstrap.assessments.filter((item) => inYear(item.academicYear)).forEach((item) => {
    candidates.push({ section: 'achievement', entityType: 'assessment', entityId: item.id, title: item.title, subtitle: excerpt(item.assessmentType, item.subject, item.grade, item.teacherName), excerpt: excerpt(item.notes), academicYear: item.academicYear, date: item.assessmentDate, status: statusLabels[item.status] || item.status, subject: item.subject, grade: item.grade, teacherName: item.teacherName, targetView: 'achievement', targetId: item.id, searchable: excerpt(item.title, item.assessmentType, item.subject, item.grade, item.term, item.notes, item.teacherName, item.status) });
    getPreviewAssessmentDetails(item.id).actions.forEach((action) => candidates.push({ section: 'achievement', entityType: 'achievement_action', entityId: action.id, title: action.title, subtitle: excerpt('تدخل تحصيلي', item.title, action.targetGroup, action.responsibleName), excerpt: excerpt(action.metric?.metricName, action.metric?.referenceSource, action.baselineIndicator, action.targetIndicator, action.outcomeIndicator, action.notes), academicYear: item.academicYear, date: action.dueDate || action.startDate || item.assessmentDate, status: statusLabels[action.status] || action.status, subject: item.subject, grade: item.grade, teacherName: action.responsibleName, targetView: 'achievement', targetId: item.id, searchable: excerpt(action.title, item.title, action.targetGroup, action.baselineIndicator, action.targetIndicator, action.outcomeIndicator, action.notes, action.responsibleName, item.subject, item.grade, action.metric?.metricName, action.metric?.unit, action.metric?.referenceSource, action.metric?.referenceYear, action.metric?.referenceNote, action.metric?.notes) }));
  });

  if (normalizedQuery.length >= 2 && use('supervision')) previewBootstrap.visits.filter((visit) => inYear(visit.academicYear)).forEach((visit) => {
    candidates.push({ section: 'supervision', entityType: 'visit', entityId: visit.id, title: visit.lessonTitle || `${visit.visitType} • ${visit.teacherName}`, subtitle: excerpt(visit.visitType, visit.teacherName, visit.teacherSubject, visit.grade), excerpt: excerpt(visit.strengths, visit.developmentAreas, visit.recommendations, visit.followupNotes), academicYear: visit.academicYear, date: visit.visitDate, status: statusLabels[visit.effectiveStatus] || visit.effectiveStatus, subject: visit.teacherSubject, grade: visit.grade, teacherName: visit.teacherName, targetView: 'supervision', targetId: visit.id, searchable: excerpt(visit.teacherName, visit.teacherSubject, visit.visitType, visit.grade, visit.lessonTitle, visit.objectives, visit.strengths, visit.developmentAreas, visit.recommendations, visit.followupNotes) });
    getPreviewSupervisionVisit(visit.id).actions.forEach((action) => candidates.push({ section: 'supervision', entityType: 'supervision_action', entityId: action.id, title: action.title, subtitle: excerpt('متابعة إشرافية', visit.teacherName, visit.lessonTitle, action.responsibleName), excerpt: excerpt(action.notes), academicYear: visit.academicYear, date: action.dueDate || visit.visitDate, status: statusLabels[action.status] || action.status, subject: visit.teacherSubject, grade: visit.grade, teacherName: action.responsibleName || visit.teacherName, targetView: 'supervision', targetId: visit.id, searchable: excerpt(action.title, visit.visitType, visit.lessonTitle, visit.teacherName, action.responsibleName, action.notes, visit.teacherSubject, visit.grade) }));
  });

  if (normalizedQuery.length >= 2 && use('requests')) previewBootstrap.requests.filter((item) => inYear(item.academicYear || yearFromDate(item.createdAt))).forEach((item) => candidates.push({ section: 'requests', entityType: 'request', entityId: item.id, title: item.title, subtitle: excerpt(item.requestType, item.teacherName, item.subject, item.grade), excerpt: excerpt(item.notes), academicYear: item.academicYear || yearFromDate(item.createdAt), date: item.deadline || item.createdAt, status: statusLabels[item.status] || item.status, subject: item.subject, grade: item.grade, teacherName: item.teacherName, targetView: 'requests', targetId: item.id, searchable: excerpt(item.title, item.requestType, item.teacherName, item.subject, item.grade, item.notes, item.allowedFiles, item.status) }));

  if (normalizedQuery.length >= 2 && use('meetings')) previewBootstrap.meetings.filter((meeting) => inYear(meeting.academicYear)).forEach((meeting) => {
    const detail = getPreviewMeetingDetails(meeting.id);
    candidates.push({ section: 'meetings', entityType: 'meeting', entityId: meeting.id, title: meeting.title, subtitle: excerpt(meeting.meetingType, meeting.location), excerpt: excerpt(detail.agenda, detail.discussionSummary, detail.notes), academicYear: meeting.academicYear, date: meeting.meetingDate, status: statusLabels[meeting.status] || meeting.status, targetView: 'meetings', targetId: meeting.id, searchable: excerpt(meeting.title, meeting.meetingType, meeting.location, detail.agenda, detail.discussionSummary, detail.notes) });
    detail.decisions.forEach((decision) => candidates.push({ section: 'meetings', entityType: 'decision', entityId: decision.id, title: decision.title, subtitle: excerpt('قرار', meeting.title, decision.responsibleName), excerpt: excerpt(decision.notes), academicYear: meeting.academicYear, date: decision.dueDate || meeting.meetingDate, status: statusLabels[decision.status] || decision.status, teacherName: decision.responsibleName, targetView: 'meetings', targetId: meeting.id, searchable: excerpt(decision.title, meeting.title, decision.responsibleName, decision.notes) }));
  });

  if (normalizedQuery.length >= 2 && use('events')) previewBootstrap.events.filter((event) => inYear(event.academicYear || yearFromDate(event.eventDate))).forEach((event) => {
    const detail = getPreviewEventDetails(event.id);
    candidates.push({ section: 'events', entityType: 'event', entityId: event.id, title: event.title, subtitle: excerpt(event.eventType, event.audience, event.location), excerpt: excerpt(event.goals, event.summary, event.outcomes, event.recommendations), academicYear: event.academicYear || yearFromDate(event.eventDate), date: event.eventDate, status: 'موثق', targetView: 'events', targetId: event.id, searchable: excerpt(event.title, event.eventType, event.location, event.audience, event.goals, event.summary, event.outcomes, event.recommendations, ...detail.teachers.map((teacher) => teacher.name)) });
  });

  if (normalizedQuery.length >= 2 && use('documents')) previewBootstrap.documents.filter((doc) => inYear(doc.academicYear || yearFromDate(doc.uploadedAt))).forEach((doc) => candidates.push({ section: 'documents', entityType: 'document', entityId: doc.id, title: doc.title, subtitle: excerpt(doc.category, doc.subject, doc.grade), excerpt: excerpt(doc.originalName), academicYear: doc.academicYear || yearFromDate(doc.uploadedAt), date: doc.uploadedAt, status: statusLabels[doc.status] || doc.status, subject: doc.subject, grade: doc.grade, targetView: 'documents', targetId: doc.id, searchable: excerpt(doc.title, doc.category, doc.subject, doc.grade, doc.originalName, doc.status) }));

  const scored = candidates.map((candidate) => ({ candidate, score: score(q, candidate.title, candidate.searchable) })).filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || (b.candidate.date || '').localeCompare(a.candidate.date || '') || a.candidate.title.localeCompare(b.candidate.title, 'ar'));
  const counts: SearchResponse['counts'] = {};
  scored.forEach(({ candidate }) => { counts[candidate.section] = (counts[candidate.section] || 0) + 1; });
  const results = scored.slice(0, limit).map(({ candidate }) => {
    const { searchable: _searchable, ...result } = candidate;
    return { ...result, key: `${result.section}:${result.entityType}:${result.entityId}`, sectionLabel: sectionLabels[result.section] };
  });
  return { query: q, normalizedQuery, section, academicYear, generatedAt: new Date().toISOString(), total: scored.length, counts, availableYears: getPreviewArchiveYears().years.map((item) => item.academicYear), results };
}
