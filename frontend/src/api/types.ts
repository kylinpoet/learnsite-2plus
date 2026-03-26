export type ThemeStyle = 'workshop' | 'material' | 'natural'
export type LoginRole = 'student' | 'teacher'
export type UserRole = 'student' | 'teacher' | 'school_admin' | 'platform_admin'
export type ManagedTeacherRole = 'teacher' | 'school_admin'
export type ResourceAudience = 'student' | 'teacher' | 'all'
export type AttendanceStatus = 'pending' | 'present' | 'late' | 'absent' | 'excused'
export type SubmissionStatus = 'draft' | 'submitted' | 'reviewed'
export type ReviewDecision = 'approved' | 'revision_requested' | 'rejected'
export type AuditLogLevel = 'info' | 'warning' | 'risk'
export type BackupSnapshotStatus = 'ready' | 'restored'
export type TeacherDraftStatus = 'draft' | 'accepted' | 'rejected'
export type CourseActivityType = 'rich_text' | 'interactive_page'

export interface SchoolSummary {
  id: number
  code: string
  name: string
  city: string
  slogan: string
  theme_style: ThemeStyle
}

export interface SchoolSettingsUpdatePayload {
  name: string
  city: string
  slogan: string
  theme_style: ThemeStyle
}

export interface ThemeStyleOption {
  id: ThemeStyle
  name: string
  description: string
}

export interface BootstrapResponse {
  schools: SchoolSummary[]
  theme_styles: ThemeStyleOption[]
}

export interface SessionInfo {
  token: string
  role: UserRole
  username: string
  display_name: string
  school_code: string
  school_name: string
  theme_style: ThemeStyle
  expires_at: string
}

export interface LoginResponse {
  session: SessionInfo
  redirect_path: string
}

export interface TodoItem {
  title: string
  status: 'pending' | 'active' | 'done'
}

export interface SubmissionHistoryEntry {
  id: number
  entry_type: 'draft_saved' | 'submitted' | 'reviewed'
  summary: string
  actor_name: string
  occurred_at: string
  version?: number | null
  decision?: ReviewDecision | null
}

export interface StudentHomeResponse {
  school_name: string
  student_name: string
  class_name: string
  lesson_title: string
  lesson_stage: string
  assignment_title: string
  assignment_prompt: string
  session_status: string
  progress_percent: number
  progress_summary: string
  saved_at: string
  todo_items: TodoItem[]
  highlights: string[]
  help_open: boolean
  attendance_status: AttendanceStatus
  submission: StudentSubmissionSummary
  submission_history: SubmissionHistoryEntry[]
  resources: StudentResourceSummary[]
}

export interface StudentDashboardResponse {
  school_name: string
  student_name: string
  class_name: string
  lesson_title: string
  lesson_stage: string
  session_status: string
  progress_percent: number
  progress_summary: string
  todo_items: TodoItem[]
  highlights: string[]
  help_open: boolean
  attendance_status: AttendanceStatus
}

export interface StudentAttendanceHistoryEntry {
  session_id: number
  lesson_title: string
  class_name: string
  status: AttendanceStatus
  marked_at?: string | null
  started_at: string
}

export interface StudentAttendanceResponse {
  session_id?: number | null
  school_name: string
  student_name: string
  class_name: string
  lesson_title: string
  session_status: string
  attendance_status: AttendanceStatus
  checked_in_at?: string | null
  last_seen_at?: string | null
  can_check_in: boolean
  help_open: boolean
  attendance_history: StudentAttendanceHistoryEntry[]
}

export interface StudentAssignmentsResponse {
  session_id?: number | null
  school_name: string
  student_name: string
  class_name: string
  lesson_title: string
  lesson_stage: string
  assignment_title: string
  assignment_prompt: string
  session_status: string
  submission: StudentSubmissionSummary
  submission_history: SubmissionHistoryEntry[]
  activities: CourseActivitySummary[]
}

export interface StudentActivityDetailResponse {
  session_id?: number | null
  school_name: string
  student_name: string
  class_name: string
  lesson_title: string
  session_status: string
  activity: CourseActivitySummary
}

export interface StudentResourcesResponse {
  school_name: string
  student_name: string
  resources: StudentResourceSummary[]
}

export interface StudentSubmissionSummary {
  id?: number
  title: string
  content: string
  status: SubmissionStatus
  version: number
  draft_saved_at?: string | null
  submitted_at?: string | null
  teacher_feedback?: string | null
  review_decision?: ReviewDecision | null
  reviewed_at?: string | null
  reviewed_by?: string | null
  can_edit: boolean
}

export interface ActivitySubmissionSummary {
  id: number
  submitted_by_name: string
  submitted_at: string
  payload_preview: string
}

export interface CourseActivitySummary {
  id: number
  title: string
  activity_type: CourseActivityType
  position: number
  summary?: string | null
  instructions_html: string
  has_interactive_asset: boolean
  interactive_asset_name?: string | null
  interactive_launch_url?: string | null
  interactive_preview_url?: string | null
  interactive_submission_api_url?: string | null
  submission_count: number
  last_submitted_at?: string | null
  latest_submission?: ActivitySubmissionSummary | null
  recent_submissions: ActivitySubmissionSummary[]
}

export interface SubmissionUpsertPayload {
  title: string
  content: string
}

export interface SubmissionActionResponse {
  message: string
  submission: StudentSubmissionSummary
  updated_at: string
}

export interface ActivitySubmissionResponse {
  message: string
  submission: ActivitySubmissionSummary
  updated_at: string
}

export interface RadarSummary {
  online: number
  expected: number
  absent: number
  idle: number
  not_started: number
  help_requests: number
}

export interface StudentResourceSummary {
  id: number
  title: string
  description?: string | null
  category_id?: number | null
  category_name?: string | null
  classroom_name?: string | null
  original_filename: string
  file_size: number
  file_size_label: string
  download_count: number
  uploaded_at: string
}

export interface TeacherDraft {
  id: number
  draft_type: string
  title: string
  content: string
  created_at: string
  updated_at?: string | null
  status: TeacherDraftStatus
}

export interface TeacherAnalyticsAttentionStudent {
  student_name: string
  student_username: string
  progress_percent: number
  presence_status: string
  reason: string
}

export interface TeacherSessionAnalytics {
  attendance_rate: number
  average_progress: number
  submission_rate: number
  reviewed_rate: number
  present_count: number
  late_count: number
  absent_count: number
  pending_count: number
  draft_count: number
  submitted_count: number
  reviewed_count: number
  approved_count: number
  revision_requested_count: number
  rejected_count: number
  attention_students: TeacherAnalyticsAttentionStudent[]
  highlights: string[]
}

export interface TeacherCourseSummary {
  id: number
  title: string
  stage_label: string
  overview?: string | null
  assignment_title: string
  assignment_prompt: string
  activity_count?: number
  is_published: boolean
  published_at?: string | null
}

export interface TeacherReflectionSummary {
  id?: number | null
  strengths: string
  risks: string
  next_actions: string
  student_support_plan: string
  ai_draft_content?: string | null
  updated_at?: string | null
}

export interface TeacherDashboardResponse {
  session_id?: number | null
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  assignment_title: string
  session_status: string
  radar: RadarSummary
  workbench_steps: TodoItem[]
  launch_options: TeacherLaunchOption[]
  managed_classrooms: TeacherClassroomSummary[]
  analytics: TeacherSessionAnalytics
  student_roster_scope: string
  student_roster_live: boolean
  student_roster: TeacherStudentRosterEntry[]
}

export interface TeacherAttendanceResponse {
  session_id?: number | null
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  session_status: string
  radar: RadarSummary
  analytics: TeacherSessionAnalytics
  student_roster_scope: string
  student_roster_live: boolean
  student_roster: TeacherStudentRosterEntry[]
  attendance_records: AttendanceRecordSummary[]
  help_requests: TeacherHelpRequestSummary[]
}

export interface TeacherSubmissionsResponse {
  session_id?: number | null
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  assignment_title: string
  session_status: string
  submissions: SubmissionQueueItem[]
  analytics: TeacherSessionAnalytics
}

export interface TeacherConsoleResponse {
  session_id?: number | null
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  assignment_title: string
  session_status: string
  radar: RadarSummary
  workbench_steps: TodoItem[]
  lesson_plans: TeacherCourseSummary[]
  managed_classrooms: TeacherClassroomSummary[]
  resource_categories: ResourceCategorySummary[]
  student_roster_scope: string
  student_roster_live: boolean
  student_roster: TeacherStudentRosterEntry[]
  launch_options: TeacherLaunchOption[]
  resources: TeacherResourceSummary[]
  attendance_records: AttendanceRecordSummary[]
  help_requests: TeacherHelpRequestSummary[]
  submissions: SubmissionQueueItem[]
  analytics: TeacherSessionAnalytics
  reflection: TeacherReflectionSummary
  ai_drafts: TeacherDraft[]
}

export interface TeacherCopilotResponse {
  session_id?: number | null
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  session_status: string
  reflection: TeacherReflectionSummary
  analytics: TeacherSessionAnalytics
  ai_drafts: TeacherDraft[]
}

export interface TeacherResourcesResponse {
  school_name: string
  teacher_name: string
  managed_classrooms: TeacherClassroomSummary[]
  resource_categories: ResourceCategorySummary[]
  resources: TeacherResourceSummary[]
}

export interface TeacherCourseDetailResponse {
  course: TeacherCourseSummary
  activities: CourseActivitySummary[]
}

export interface TeacherCourseCollectionResponse {
  school_name: string
  teacher_name: string
  managed_classrooms: TeacherClassroomSummary[]
  launch_options: TeacherLaunchOption[]
  courses: TeacherCourseSummary[]
  selected_course?: TeacherCourseDetailResponse | null
}

export interface CreateDraftResponse {
  draft: TeacherDraft
}

export interface TeacherLaunchOption {
  classroom_id: number
  classroom_name: string
  course_id: number
  course_title: string
  stage_label: string
}

export interface TeacherClassroomSummary {
  id: number
  name: string
  grade_label: string
}

export interface TeacherStudentRosterEntry {
  student_id: number
  student_name: string
  student_username: string
  classroom_name: string
  attendance_status?: AttendanceStatus | null
  presence_status?: string | null
  progress_percent: number
  help_requested: boolean
  submission_id?: number | null
  submission_status?: SubmissionStatus | null
  review_decision?: ReviewDecision | null
  last_seen_at?: string | null
  attention_reason?: string | null
}

export interface TeacherResourceSummary {
  id: number
  title: string
  description?: string | null
  audience: ResourceAudience
  category_id?: number | null
  category_name?: string | null
  classroom_id?: number | null
  classroom_name?: string | null
  original_filename: string
  file_size: number
  file_size_label: string
  download_count: number
  uploaded_by_name: string
  uploaded_at: string
  active: boolean
  can_manage: boolean
}

export interface AttendanceRecordSummary {
  id: number
  student_name: string
  student_username: string
  status: AttendanceStatus
  marked_at?: string | null
  note?: string | null
  last_seen_at?: string | null
}

export interface ResourceCategorySummary {
  id: number
  name: string
  description?: string | null
  sort_order: number
  active: boolean
}

export interface AttendanceMarkPayload {
  status: AttendanceStatus
  note?: string
}

export interface StartSessionPayload {
  classroom_id: number
  course_id: number
}

export interface TeacherCourseActivitySavePayload {
  id?: number | null
  title: string
  activity_type: CourseActivityType
  summary?: string | null
  instructions_html: string
}

export interface TeacherCourseSavePayload {
  course_id?: number | null
  title: string
  stage_label: string
  overview?: string | null
  assignment_title: string
  assignment_prompt: string
  activities?: TeacherCourseActivitySavePayload[]
  publish_now: boolean
}

export interface TeacherHelpRequestSummary {
  id: number
  student_name: string
  student_username: string
  message: string
  created_at: string
  status: string
}

export interface SubmissionQueueItem {
  id: number
  student_name: string
  student_username: string
  title: string
  status: SubmissionStatus
  version: number
  draft_saved_at?: string | null
  submitted_at?: string | null
  help_requested: boolean
  review_decision?: ReviewDecision | null
  reviewed_at?: string | null
}

export interface SubmissionReviewSummary {
  id: number
  reviewer_name: string
  decision: ReviewDecision
  feedback: string
  created_at: string
}

export interface TeacherSubmissionDetail {
  id: number
  student_name: string
  student_username: string
  title: string
  content: string
  status: SubmissionStatus
  version: number
  draft_saved_at?: string | null
  submitted_at?: string | null
  teacher_feedback?: string | null
  review_decision?: ReviewDecision | null
  reviewed_at?: string | null
  help_requested: boolean
  help_messages: TeacherHelpRequestSummary[]
  history: SubmissionHistoryEntry[]
  reviews: SubmissionReviewSummary[]
}

export interface SubmissionReviewPayload {
  decision: ReviewDecision
  feedback: string
  resolve_help_requests: boolean
}

export interface TeacherReflectionPayload {
  strengths: string
  risks: string
  next_actions: string
  student_support_plan: string
}

export interface TeacherReflectionDraftResponse {
  draft: TeacherDraft
  reflection: TeacherReflectionSummary
}

export interface TeacherDraftUpdatePayload {
  title: string
  content: string
}

export interface TeacherResourceStatusPayload {
  active: boolean
}

export interface ResourceCategoryCreatePayload {
  name: string
  description?: string | null
  sort_order: number
}

export interface ResourceCategoryStatusPayload {
  active: boolean
}

export interface BackupCreatePayload {
  note?: string | null
}

export interface BackupSnapshotSummary {
  id: number
  school_id?: number | null
  school_name: string
  actor_display_name: string
  actor_username: string
  actor_role: UserRole
  file_name: string
  file_size: number
  file_size_label: string
  status: BackupSnapshotStatus
  note?: string | null
  created_at: string
  restored_at?: string | null
}

export interface AdminAuditLogSummary {
  id: number
  actor_display_name: string
  actor_username: string
  actor_role: UserRole
  action: string
  target_type: string
  target_id?: string | null
  target_label: string
  level: AuditLogLevel
  summary: string
  detail?: string | null
  created_at: string
}

export interface MigrationPreviewRow {
  id: number
  field_name: string
  legacy_value: string
  new_value: string
  status: string
  issue_detail?: string | null
  resolution_note?: string | null
  resolved_at?: string | null
  requires_resolution: boolean
}

export interface MigrationBatch {
  id: number
  name: string
  status: string
  progress: number
  current_step: string
  error_count: number
  preview_rows: MigrationPreviewRow[]
}

export interface LegacyMappingSummary {
  id: number
  entity_type: string
  legacy_id: string
  new_id: string
  active: boolean
}

export interface MigrationFixPayload {
  new_value: string
  resolution_note: string
  status: 'mapped' | 'resolved'
}

export interface GovernanceSchoolSnapshot {
  school: SchoolSummary
  latest_batch_name?: string | null
  latest_batch_status?: string | null
  latest_batch_progress?: number | null
  current_step?: string | null
  unresolved_preview_count: number
  can_execute_migration: boolean
  can_rollback_migration: boolean
  is_current: boolean
}

export interface AcademicTermSummary {
  id: number
  school_year_label: string
  term_name: string
  start_on?: string | null
  end_on?: string | null
  is_active: boolean
  sort_order: number
}

export interface AdminClassroomSummary {
  id: number
  name: string
  grade_label: string
  student_count: number
}

export interface AdminStudentSummary {
  id: number
  username: string
  display_name: string
  classroom_id?: number | null
  classroom_name?: string | null
  active: boolean
}

export interface AdminTeacherSummary {
  id: number
  username: string
  display_name: string
  role: ManagedTeacherRole
  active: boolean
  assigned_classroom_ids: number[]
  assigned_classroom_names: string[]
}

export interface AdminOverviewResponse {
  school_name: string
  admin_name: string
  active_school_count: number
  current_school: SchoolSummary
  managed_schools: SchoolSummary[]
  school_snapshots: GovernanceSchoolSnapshot[]
  active_term?: AcademicTermSummary | null
  academic_terms: AcademicTermSummary[]
  classrooms: AdminClassroomSummary[]
  resource_categories: ResourceCategorySummary[]
  backup_snapshots: BackupSnapshotSummary[]
  recent_audit_logs: AdminAuditLogSummary[]
  teacher_accounts: AdminTeacherSummary[]
  students: AdminStudentSummary[]
  active_migration: MigrationBatch
  legacy_mappings: LegacyMappingSummary[]
  can_execute_migration: boolean
  can_rollback_migration: boolean
  unresolved_preview_count: number
  guardrails: string[]
}

export interface AcademicTermCreatePayload {
  school_year_label: string
  term_name: string
  start_on?: string | null
  end_on?: string | null
  activate_now: boolean
}

export interface StudentAssignmentPayload {
  classroom_id: number
}

export interface TeacherAccountSavePayload {
  teacher_id?: number | null
  username: string
  display_name: string
  role: ManagedTeacherRole
  password?: string | null
  classroom_ids: number[]
}

export interface StudentImportPayload {
  classroom_id: number
  rows_text: string
  default_password: string
}

export interface PasswordResetPayload {
  new_password: string
}

export interface UserStatusUpdatePayload {
  active: boolean
}

export interface StudentImportResult {
  imported_count: number
  updated_count: number
  skipped_count: number
}

export interface AdminStudentImportResponse {
  overview: AdminOverviewResponse
  result: StudentImportResult
}

export interface MessageResponse {
  message: string
  updated_at?: string | null
}
