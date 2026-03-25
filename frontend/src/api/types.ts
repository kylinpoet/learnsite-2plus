export type ThemeStyle = 'workshop' | 'material' | 'natural'
export type LoginRole = 'student' | 'teacher'
export type UserRole = 'student' | 'teacher' | 'school_admin' | 'platform_admin'
export type AttendanceStatus = 'pending' | 'present' | 'late' | 'absent' | 'excused'
export type SubmissionStatus = 'draft' | 'submitted' | 'reviewed'

export interface SchoolSummary {
  id: number
  code: string
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
}

export interface LoginResponse {
  session: SessionInfo
  redirect_path: string
}

export interface TodoItem {
  title: string
  status: 'pending' | 'active' | 'done'
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
}

export interface StudentSubmissionSummary {
  id?: number
  title: string
  content: string
  status: SubmissionStatus
  version: number
  draft_saved_at?: string | null
  submitted_at?: string | null
  can_edit: boolean
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

export interface RadarSummary {
  online: number
  expected: number
  absent: number
  idle: number
  not_started: number
  help_requests: number
}

export interface TeacherDraft {
  id: number
  draft_type: string
  title: string
  content: string
  created_at: string
  status: string
}

export interface TeacherConsoleResponse {
  session_id: number
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  assignment_title: string
  session_status: string
  radar: RadarSummary
  workbench_steps: TodoItem[]
  launch_options: TeacherLaunchOption[]
  attendance_records: AttendanceRecordSummary[]
  submissions: SubmissionQueueItem[]
  ai_drafts: TeacherDraft[]
}

export interface TeacherLaunchOption {
  classroom_id: number
  classroom_name: string
  course_id: number
  course_title: string
  stage_label: string
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

export interface AttendanceMarkPayload {
  status: AttendanceStatus
  note?: string
}

export interface StartSessionPayload {
  classroom_id: number
  course_id: number
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
}

export interface MigrationPreviewRow {
  field_name: string
  legacy_value: string
  new_value: string
  status: string
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

export interface AdminOverviewResponse {
  school_name: string
  admin_name: string
  active_school_count: number
  managed_schools: SchoolSummary[]
  active_migration: MigrationBatch
  legacy_mappings: LegacyMappingSummary[]
  can_execute_migration: boolean
  can_rollback_migration: boolean
  guardrails: string[]
}
