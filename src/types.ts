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

export type EventRecord = {
  id: number;
  title: string;
  eventType: string;
  eventDate: string;
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
};

export type BootstrapData = {
  academicYear: string;
  term: string;
  dashboard: DashboardStats;
  teachers: Teacher[];
  requests: UploadRequest[];
  events: EventRecord[];
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
