export type ThemeStyle = 'workshop' | 'material' | 'natural'
export type LoginRole = 'student' | 'teacher'
export type UserRole = 'student' | 'teacher' | 'school_admin' | 'platform_admin'

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
  progress_percent: number
  progress_summary: string
  saved_at: string
  todo_items: TodoItem[]
  highlights: string[]
  help_open: boolean
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
  school_name: string
  teacher_name: string
  class_name: string
  lesson_title: string
  session_status: string
  radar: RadarSummary
  workbench_steps: TodoItem[]
  ai_drafts: TeacherDraft[]
}

export interface MigrationPreviewRow {
  field_name: string
  legacy_value: string
  new_value: string
  status: string
}

export interface MigrationBatch {
  name: string
  status: string
  progress: number
  current_step: string
  error_count: number
  preview_rows: MigrationPreviewRow[]
}

export interface AdminOverviewResponse {
  school_name: string
  admin_name: string
  active_school_count: number
  managed_schools: SchoolSummary[]
  active_migration: MigrationBatch
  guardrails: string[]
}
