export type DriveStatus = {
  configured: boolean;
  connected: boolean;
  rootFolderId: string | null;
  scope: string;
  storageMode: 'local' | 'google_drive' | string;
};

export type Teacher = {
  id: number;
  name: string;
  subject: string;
  specialization?: string | null;
  qualification?: string | null;
  experienceYears: number;
  workload: number;
  cvCompletion: number;
  email?: string | null;
  phone?: string | null;
};

export type UploadRequest = {
  id: number;
  teacherId: number;
  teacherName: string;
  requestType: string;
  subject: string;
  grade: string;
  title: string;
  deadline?: string | null;
  notes?: string | null;
  allowedFiles: string;
  status: RequestStatus;
  academicYear?: string | null;
  expiresAt: string;
  createdAt: string;
  updatedAt: string;
};

export type RequestStatus =
  | 'waiting_upload'
  | 'received'
  | 'review'
  | 'approved'
  | 'needs_revision'
  | 'late'
  | 'cancelled';

export type DocumentRecord = {
  id: number;
  requestId?: number | null;
  teacherId?: number | null;
  title: string;
  category: string;
  subject?: string | null;
  grade?: string | null;
  academicYear?: string | null;
  originalName: string;
  mimeType?: string | null;
  sizeBytes: number;
  storageProvider: string;
  storageFileId?: string | null;
  storagePath?: string | null;
  webViewLink?: string | null;
  status: string;
  uploadedAt: string;
  approvedAt?: string | null;
};

export type DirectDocumentInput = {
  title: string;
  category: string;
  academicYear: string;
  teacherId?: number | null;
  subject: string;
  grade: string;
};

export type EventRecord = {
  id: number;
  title: string;
  eventType: string;
  eventDate: string;
  academicYear?: string | null;
  location?: string | null;
  audience?: string | null;
  participantCount: number;
  goals?: string | null;
  summary?: string | null;
  outcomes?: string | null;
  recommendations?: string | null;
  coverTone: 'teal' | 'navy' | 'gold' | string;
  mediaCount?: number;
  coverMediaId?: number | null;
  coverMediaUrl?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type EventMediaRecord = {
  id: number;
  eventId: number;
  originalName: string;
  mimeType?: string | null;
  sizeBytes: number;
  storageProvider: string;
  storageFileId?: string | null;
  storagePath?: string | null;
  webViewLink?: string | null;
  contentUrl?: string | null;
  caption: string;
  position: number;
  isCover: boolean;
  createdAt: string;
};

export type EventTeacher = Teacher & { event_role?: string | null };

export type EventDetails = EventRecord & {
  media: EventMediaRecord[];
  teachers: EventTeacher[];
};

export type EventMediaMetaInput = {
  caption: string;
  position: number;
  isCover: boolean;
};

export type MeetingStatus = 'planned' | 'held' | 'cancelled';
export type MeetingDecisionBaseStatus = 'new' | 'in_progress' | 'completed' | 'cancelled';
export type MeetingDecisionStatus = MeetingDecisionBaseStatus | 'overdue';

export type MeetingRecord = {
  id: number;
  title: string;
  meetingType: string;
  meetingDate: string;
  meetingTime?: string | null;
  location?: string | null;
  academicYear: string;
  status: MeetingStatus;
  attendeeCount: number;
  decisionCount: number;
  openDecisionCount: number;
  overdueDecisionCount: number;
  completedDecisionCount: number;
  createdAt: string;
  updatedAt: string;
};

export type MeetingDecision = {
  id: number;
  meetingId: number;
  meetingTitle?: string;
  title: string;
  responsibleTeacherId?: number | null;
  responsibleName?: string | null;
  dueDate?: string | null;
  status: MeetingDecisionStatus;
  baseStatus: MeetingDecisionBaseStatus;
  notes?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type MeetingAttendee = Teacher & { attendanceStatus: 'present' | 'absent' | 'excused' };

export type MeetingTimelineItem = {
  id: number;
  activity_type: string;
  title: string;
  detail?: string | null;
  created_at: string;
};

export type MeetingDetails = MeetingRecord & {
  agenda?: string | null;
  discussionSummary?: string | null;
  notes?: string | null;
  attendees: MeetingAttendee[];
  decisions: MeetingDecision[];
  timeline: MeetingTimelineItem[];
  minutesReady: boolean;
};

export type CreateMeetingInput = {
  title: string;
  meetingType: string;
  meetingDate: string;
  academicYear: string;
  meetingTime: string;
  location: string;
  agenda: string;
  discussionSummary: string;
  notes: string;
  status: MeetingStatus;
  attendeeIds: number[];
};

export type MeetingDecisionInput = {
  title: string;
  responsibleTeacherId?: number | null;
  responsibleName: string;
  dueDate?: string | null;
  status: MeetingDecisionBaseStatus;
  notes: string;
};

export type CurriculumPlanStatus = 'active' | 'completed' | 'archived';
export type CurriculumUnitBaseStatus = 'not_started' | 'in_progress' | 'completed';
export type CurriculumUnitEffectiveStatus = CurriculumUnitBaseStatus | 'overdue';

export type CurriculumPlanRecord = {
  id: number;
  title: string;
  subject: string;
  grade: string;
  term: string;
  academicYear: string;
  ownerTeacherId?: number | null;
  ownerName?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  notes?: string | null;
  status: CurriculumPlanStatus;
  unitCount: number;
  completedUnitCount: number;
  overdueUnitCount: number;
  progressPercent: number;
  createdAt: string;
  updatedAt: string;
};

export type CurriculumUnit = {
  id: number;
  planId: number;
  planTitle?: string;
  planSubject?: string;
  planGrade?: string;
  title: string;
  sequence: number;
  plannedStart?: string | null;
  plannedEnd?: string | null;
  progressPercent: number;
  status: CurriculumUnitBaseStatus;
  effectiveStatus: CurriculumUnitEffectiveStatus;
  delayReason?: string | null;
  notes?: string | null;
  responsibleTeacherId?: number | null;
  responsibleName?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type CurriculumPlanDetails = CurriculumPlanRecord & {
  units: CurriculumUnit[];
  timeline: Activity[];
};

export type CurriculumPlanInput = {
  title: string;
  subject: string;
  grade: string;
  term: string;
  academicYear: string;
  ownerTeacherId?: number | null;
  startDate?: string | null;
  endDate?: string | null;
  notes: string;
  status: CurriculumPlanStatus;
};

export type CurriculumUnitInput = {
  title: string;
  sequence: number;
  plannedStart?: string | null;
  plannedEnd?: string | null;
  progressPercent: number;
  status: CurriculumUnitBaseStatus;
  delayReason: string;
  notes: string;
  responsibleTeacherId?: number | null;
};

export type SupervisionVisitStatus = 'planned' | 'completed' | 'needs_followup' | 'closed';
export type SupervisionVisitEffectiveStatus = SupervisionVisitStatus | 'overdue';
export type SupervisionActionBaseStatus = 'new' | 'in_progress' | 'completed' | 'cancelled';
export type SupervisionActionStatus = SupervisionActionBaseStatus | 'overdue';

export type SupervisionVisitRecord = {
  id: number;
  teacherId: number;
  teacherName: string;
  teacherSubject?: string | null;
  visitType: string;
  visitDate: string;
  periodLabel?: string | null;
  grade?: string | null;
  lessonTitle?: string | null;
  objectives?: string | null;
  strengths?: string | null;
  developmentAreas?: string | null;
  recommendations?: string | null;
  followupDate?: string | null;
  followupNotes?: string | null;
  academicYear: string;
  status: SupervisionVisitStatus;
  effectiveStatus: SupervisionVisitEffectiveStatus;
  actionCount: number;
  openActionCount: number;
  completedActionCount: number;
  overdueActionCount: number;
  closedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type SupervisionAction = {
  id: number;
  visitId: number;
  title: string;
  responsibleTeacherId?: number | null;
  responsibleName?: string | null;
  dueDate?: string | null;
  status: SupervisionActionStatus;
  baseStatus: SupervisionActionBaseStatus;
  notes?: string | null;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type SupervisionVisitDetails = SupervisionVisitRecord & {
  actions: SupervisionAction[];
  timeline: Activity[];
  reportReady: boolean;
};

export type SupervisionVisitInput = {
  teacherId: number;
  visitType: string;
  visitDate: string;
  academicYear: string;
  periodLabel: string;
  grade: string;
  lessonTitle: string;
  objectives: string;
  strengths: string;
  developmentAreas: string;
  recommendations: string;
  followupDate?: string | null;
  followupNotes: string;
  status: SupervisionVisitStatus;
};

export type SupervisionActionInput = {
  title: string;
  responsibleTeacherId?: number | null;
  dueDate?: string | null;
  status: SupervisionActionBaseStatus;
  notes: string;
};

export type AchievementAssessmentStatus = 'draft' | 'recorded' | 'reviewed';
export type AchievementActionType = 'remedial' | 'enrichment' | 'followup';
export type AchievementActionBaseStatus = 'new' | 'in_progress' | 'completed' | 'cancelled';
export type AchievementActionStatus = AchievementActionBaseStatus | 'overdue';
export type AchievementImpactDirection = 'higher_better' | 'lower_better';
export type AchievementImpactStatus = 'pending' | 'target_met' | 'improved_not_met' | 'no_change' | 'regressed';

export type AchievementAssessmentRecord = {
  id: number;
  title: string;
  assessmentType: string;
  subject: string;
  grade: string;
  assessmentDate: string;
  term: string;
  academicYear: string;
  teacherId?: number | null;
  teacherName?: string | null;
  maxScore: number;
  studentCount: number;
  averageScore?: number | null;
  highestScore?: number | null;
  lowestScore?: number | null;
  masteryThresholdPct: number;
  masteryReferenceSource: string;
  masteryReferenceYear: string;
  masteryReferenceNote: string;
  masteredCount: number;
  nearMasteryCount: number;
  interventionCount: number;
  notes: string;
  status: AchievementAssessmentStatus;
  masteryPercent: number;
  averagePercent: number;
  actionCount: number;
  remedialActionCount: number;
  enrichmentActionCount: number;
  openActionCount: number;
  overdueActionCount: number;
  measuredActionCount: number;
  targetMetActionCount: number;
  unmeasuredCompletedActionCount: number;
  impactReviewActionCount: number;
  createdAt: string;
  updatedAt: string;
};

export type AchievementImpactMetric = {
  actionId: number;
  metricName: string;
  unit: string;
  direction: AchievementImpactDirection;
  baselineValue: number;
  targetValue: number;
  outcomeValue?: number | null;
  measuredAt?: string | null;
  referenceSource: string;
  referenceYear: string;
  referenceNote: string;
  notes: string;
  impactStatus: AchievementImpactStatus;
  impactDelta?: number | null;
  improvementValue?: number | null;
  targetGap?: number | null;
  createdAt: string;
  updatedAt: string;
};

export type AchievementImpactMetricInput = {
  metricName: string;
  unit: string;
  direction: AchievementImpactDirection;
  baselineValue: number;
  targetValue: number;
  outcomeValue?: number | null;
  measuredAt?: string | null;
  referenceSource: string;
  referenceYear: string;
  referenceNote: string;
  notes: string;
};

export type AchievementAction = {
  id: number;
  assessmentId: number;
  actionType: AchievementActionType;
  title: string;
  targetGroup: string;
  responsibleTeacherId?: number | null;
  responsibleName?: string | null;
  startDate?: string | null;
  dueDate?: string | null;
  status: AchievementActionStatus;
  baseStatus: AchievementActionBaseStatus;
  baselineIndicator: string;
  targetIndicator: string;
  outcomeIndicator: string;
  notes: string;
  completedAt?: string | null;
  createdAt: string;
  updatedAt: string;
  metric?: AchievementImpactMetric | null;
};

export type AchievementAssessmentDetails = AchievementAssessmentRecord & {
  actions: AchievementAction[];
  timeline: Activity[];
  analysisReady: boolean;
};

export type AchievementAssessmentInput = {
  title: string;
  assessmentType: string;
  subject: string;
  grade: string;
  assessmentDate: string;
  term: string;
  academicYear: string;
  teacherId?: number | null;
  maxScore: number;
  studentCount: number;
  averageScore?: number | null;
  highestScore?: number | null;
  lowestScore?: number | null;
  masteryThresholdPct: number;
  masteryReferenceSource: string;
  masteryReferenceYear: string;
  masteryReferenceNote: string;
  masteredCount: number;
  nearMasteryCount: number;
  interventionCount: number;
  notes: string;
  status: AchievementAssessmentStatus;
};

export type AchievementActionInput = {
  actionType: AchievementActionType;
  title: string;
  targetGroup: string;
  responsibleTeacherId?: number | null;
  startDate?: string | null;
  dueDate?: string | null;
  status: AchievementActionBaseStatus;
  baselineIndicator: string;
  targetIndicator: string;
  outcomeIndicator: string;
  notes: string;
};


export type Activity = {
  id: number;
  activity_type: string;
  title: string;
  detail?: string | null;
  created_at: string;
};

export type DashboardStats = {
  teacherCount: number;
  openRequests: number;
  needsReview: number;
  lateRequests: number;
  openDecisions: number;
  upcomingVisits: number;
  planProgress: number;
  visitProgress: number;
  requestCompletion: number;
  achievementMastery: number;
  achievementMasteryComparable: boolean;
  openAchievementActions: number;
};

export type BootstrapData = {
  academicYear: string;
  currentAcademicYear: string;
  availableAcademicYears: string[];
  term: string;
  dashboard: DashboardStats;
  teachers: Teacher[];
  teacherDirectory: Teacher[];
  requests: UploadRequest[];
  events: EventRecord[];
  meetings: MeetingRecord[];
  decisionAttention: MeetingDecision[];
  plans: CurriculumPlanRecord[];
  planningAttention: CurriculumUnit[];
  visits: SupervisionVisitRecord[];
  supervisionAttention: SupervisionVisitRecord[];
  assessments: AchievementAssessmentRecord[];
  achievementAttention: AchievementAssessmentRecord[];
  documents: DocumentRecord[];
  activities: Activity[];
  drive: DriveStatus;
};

export type CreateRequestInput = {
  teacherId: number;
  requestType: string;
  subject: string;
  grade: string;
  title: string;
  deadline?: string;
  notes?: string;
  allowedFiles: string;
};

export type PublicUploadInfo = {
  id: number;
  teacherName: string;
  title: string;
  requestType: string;
  subject: string;
  grade: string;
  deadline?: string | null;
  notes?: string | null;
  allowedFiles: string;
  maxUploadMb: number;
};



export type TeacherCvItemType = 'qualification' | 'course' | 'achievement' | 'experience';

export type TeacherCvItem = {
  id: number;
  teacherId: number;
  itemType: TeacherCvItemType;
  title: string;
  organization?: string | null;
  startYear?: number | null;
  endYear?: number | null;
  description?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type TeacherProfileDetails = {
  teacher: Teacher;
  profile: {
    employeeNumber?: string | null;
    schoolJoinYear?: number | null;
    grades?: string | null;
    responsibilities?: string | null;
    professionalSummary?: string | null;
  };
  cvItems: TeacherCvItem[];
  stats: {
    requestCount: number;
    documentCount: number;
    approvedDocumentCount: number;
    visitCount: number;
    openFollowupCount: number;
  };
};

export type UpdateTeacherProfileInput = {
  name: string;
  subject: string;
  specialization: string;
  qualification: string;
  experienceYears: number;
  workload: number;
  email: string;
  phone: string;
  employeeNumber: string;
  schoolJoinYear?: number | null;
  grades: string;
  responsibilities: string;
  professionalSummary: string;
};

export type CreateTeacherCvItemInput = {
  itemType: TeacherCvItemType;
  title: string;
  organization: string;
  startYear?: number | null;
  endYear?: number | null;
  description: string;
};

export type CreateTeacherInput = {
  academicYear: string;
  name: string;
  subject: string;
  specialization: string;
  qualification: string;
  experienceYears: number;
  workload: number;
  email: string;
  phone: string;
};

export type CreateEventInput = {
  title: string;
  eventType: string;
  eventDate: string;
  academicYear: string;
  location: string;
  audience: string;
  participantCount: number;
  goals: string;
  summary: string;
  outcomes: string;
  recommendations: string;
  teacherIds?: number[];
};

export type UpdateEventInput = CreateEventInput;

export type OfficialReportType = 'department' | 'teacher' | 'planning' | 'achievement' | 'supervision' | 'meetings' | 'events';

export type OfficialReportMetric = {
  label: string;
  value: string | number;
  detail?: string;
};

export type OfficialReportColumn = {
  key: string;
  label: string;
};

export type OfficialReportSection = {
  id: string;
  title: string;
  description?: string;
  columns: OfficialReportColumn[];
  rows: Array<Record<string, string | number | boolean | null | undefined>>;
};

export type OfficialReport = {
  reportType: OfficialReportType;
  title: string;
  subtitle: string;
  academicYear: string;
  term: string;
  generatedAt: string;
  summary: string;
  teacher?: Teacher | null;
  metrics: OfficialReportMetric[];
  sections: OfficialReportSection[];
  sourceCounts: Record<string, number>;
};

export type OfficialReportQuery = {
  reportType: OfficialReportType;
  academicYear: string;
  term: string;
  teacherId?: number | null;
};


export type ArchiveSourceCounts = {
  teachers: number;
  plans: number;
  assessments: number;
  visits: number;
  meetings: number;
  decisions: number;
  events: number;
  documents: number;
  requests: number;
};

export type ArchiveCoverageItem = {
  id: string;
  label: string;
  count: number;
  detail: string;
};

export type ArchiveTeacherRecord = {
  id: number;
  name: string;
  subject: string;
  linkedRecords: number;
};

export type ArchiveYearSummary = {
  academicYear: string;
  isCurrent: boolean;
  totalRecords: number;
  teacherCount: number;
  documentCount: number;
  decisionCount: number;
  latestRecordAt?: string | null;
  sourceCounts: ArchiveSourceCounts;
};

export type ArchiveYearsIndex = {
  currentAcademicYear: string;
  generatedAt: string;
  years: ArchiveYearSummary[];
};

export type ArchiveYearDetail = ArchiveYearSummary & {
  generatedAt: string;
  coverage: ArchiveCoverageItem[];
  teachers: ArchiveTeacherRecord[];
  sections: OfficialReportSection[];
};

export type SearchSection = 'all' | 'teachers' | 'planning' | 'achievement' | 'supervision' | 'requests' | 'meetings' | 'events' | 'documents';

export type SearchTargetView = Exclude<SearchSection, 'all'>;

export type SearchResult = {
  key: string;
  section: Exclude<SearchSection, 'all'>;
  sectionLabel: string;
  entityType: string;
  entityId: number;
  title: string;
  subtitle: string;
  excerpt: string;
  academicYear?: string | null;
  date?: string | null;
  status?: string | null;
  subject?: string | null;
  grade?: string | null;
  teacherName?: string | null;
  targetView: SearchTargetView;
  targetId?: number | null;
};

export type SearchQuery = {
  q: string;
  section?: SearchSection;
  academicYear?: string;
  limit?: number;
};

export type SearchResponse = {
  query: string;
  normalizedQuery: string;
  section: SearchSection;
  academicYear: string;
  generatedAt: string;
  total: number;
  counts: Partial<Record<Exclude<SearchSection, 'all'>, number>>;
  availableYears: string[];
  results: SearchResult[];
};
