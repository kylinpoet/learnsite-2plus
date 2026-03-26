from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AuditLogLevel,
    AttendanceStatus,
    BackupSnapshotStatus,
    CourseActivityType,
    ResourceAudience,
    ReviewDecision,
    SubmissionStatus,
    ThemeStyle,
    UserRole,
)


class SchoolSummary(BaseModel):
    id: int
    code: str
    name: str
    city: str
    slogan: str
    theme_style: ThemeStyle

    model_config = ConfigDict(from_attributes=True)


class ThemeStyleOption(BaseModel):
    id: ThemeStyle
    name: str
    description: str


class BootstrapResponse(BaseModel):
    schools: list[SchoolSummary]
    theme_styles: list[ThemeStyleOption]


class SessionInfo(BaseModel):
    token: str
    role: UserRole
    username: str
    display_name: str
    school_code: str
    school_name: str
    theme_style: ThemeStyle
    expires_at: datetime


class LoginRequest(BaseModel):
    role: Literal["student", "teacher", "admin"]
    school_code: str
    username: str
    password: str


class LoginResponse(BaseModel):
    session: SessionInfo
    redirect_path: str


class TodoItem(BaseModel):
    title: str
    status: Literal["pending", "active", "done"]


class SubmissionHistoryEntry(BaseModel):
    id: int
    entry_type: Literal["draft_saved", "submitted", "reviewed"]
    summary: str
    actor_name: str
    occurred_at: str
    version: int | None = None
    decision: ReviewDecision | None = None


class StudentSubmissionSummary(BaseModel):
    id: int | None = None
    title: str
    content: str
    status: SubmissionStatus
    version: int = 1
    draft_saved_at: str | None = None
    submitted_at: str | None = None
    teacher_feedback: str | None = None
    review_decision: ReviewDecision | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    can_edit: bool = True


class ActivitySubmissionSummary(BaseModel):
    id: int
    submitted_by_name: str
    submitted_at: str
    payload_preview: str


class CourseActivitySummary(BaseModel):
    id: int
    title: str
    activity_type: CourseActivityType
    position: int
    summary: str | None = None
    instructions_html: str = ""
    has_interactive_asset: bool = False
    interactive_asset_name: str | None = None
    interactive_launch_url: str | None = None
    interactive_preview_url: str | None = None
    interactive_submission_api_url: str | None = None
    submission_count: int = 0
    last_submitted_at: str | None = None
    latest_submission: ActivitySubmissionSummary | None = None
    recent_submissions: list[ActivitySubmissionSummary] = Field(default_factory=list)


class StudentHomeResponse(BaseModel):
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    lesson_stage: str
    assignment_title: str
    assignment_prompt: str
    session_status: str
    progress_percent: int
    progress_summary: str
    saved_at: str
    todo_items: list[TodoItem]
    highlights: list[str]
    help_open: bool
    attendance_status: AttendanceStatus
    submission: StudentSubmissionSummary
    submission_history: list[SubmissionHistoryEntry]
    resources: list["StudentResourceSummary"]


class StudentDashboardResponse(BaseModel):
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    lesson_stage: str
    session_status: str
    progress_percent: int
    progress_summary: str
    todo_items: list[TodoItem]
    highlights: list[str]
    help_open: bool
    attendance_status: AttendanceStatus


class StudentAttendanceHistoryEntry(BaseModel):
    session_id: int
    lesson_title: str
    class_name: str
    status: AttendanceStatus
    marked_at: str | None = None
    started_at: str


class StudentAttendanceResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    session_status: str
    attendance_status: AttendanceStatus
    checked_in_at: str | None = None
    last_seen_at: str | None = None
    can_check_in: bool
    help_open: bool
    attendance_history: list[StudentAttendanceHistoryEntry]


class StudentAssignmentsResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    lesson_stage: str
    assignment_title: str
    assignment_prompt: str
    session_status: str
    submission: StudentSubmissionSummary
    submission_history: list[SubmissionHistoryEntry]
    activities: list[CourseActivitySummary]


class StudentActivityDetailResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    session_status: str
    activity: CourseActivitySummary


class StudentResourcesResponse(BaseModel):
    school_name: str
    student_name: str
    resources: list["StudentResourceSummary"]


class HeartbeatRequest(BaseModel):
    task_progress: int = Field(default=72, ge=0, le=100)


class HelpRequestCreate(BaseModel):
    message: str


class SubmissionUpsertRequest(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=5000)


class SubmissionActionResponse(BaseModel):
    message: str
    submission: StudentSubmissionSummary
    updated_at: datetime


class ActivitySubmissionResponse(BaseModel):
    message: str
    submission: ActivitySubmissionSummary
    updated_at: datetime


class RadarSummary(BaseModel):
    online: int
    expected: int
    absent: int
    idle: int
    not_started: int
    help_requests: int


class TeacherLaunchOption(BaseModel):
    classroom_id: int
    classroom_name: str
    course_id: int
    course_title: str
    stage_label: str


class TeacherClassroomSummary(BaseModel):
    id: int
    name: str
    grade_label: str


class TeacherStudentRosterEntry(BaseModel):
    student_id: int
    student_name: str
    student_username: str
    classroom_name: str
    attendance_status: AttendanceStatus | None = None
    presence_status: str | None = None
    progress_percent: int
    help_requested: bool = False
    submission_id: int | None = None
    submission_status: SubmissionStatus | None = None
    review_decision: ReviewDecision | None = None
    last_seen_at: str | None = None
    attention_reason: str | None = None


class ResourceCategorySummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    sort_order: int
    active: bool


class StudentResourceSummary(BaseModel):
    id: int
    title: str
    description: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    classroom_name: str | None = None
    original_filename: str
    file_size: int
    file_size_label: str
    download_count: int
    uploaded_at: str


class TeacherResourceSummary(BaseModel):
    id: int
    title: str
    description: str | None = None
    audience: ResourceAudience
    category_id: int | None = None
    category_name: str | None = None
    classroom_id: int | None = None
    classroom_name: str | None = None
    original_filename: str
    file_size: int
    file_size_label: str
    download_count: int
    uploaded_by_name: str
    uploaded_at: str
    active: bool
    can_manage: bool


class TeacherCourseSummary(BaseModel):
    id: int
    title: str
    stage_label: str
    overview: str | None = None
    assignment_title: str
    assignment_prompt: str
    activity_count: int = 0
    is_published: bool
    published_at: str | None = None


class TeacherDashboardResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    assignment_title: str
    session_status: str
    radar: RadarSummary
    workbench_steps: list[TodoItem]
    launch_options: list[TeacherLaunchOption]
    managed_classrooms: list[TeacherClassroomSummary]
    analytics: "TeacherSessionAnalytics"
    student_roster_scope: str
    student_roster_live: bool
    student_roster: list[TeacherStudentRosterEntry]


class TeacherAttendanceResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    session_status: str
    radar: RadarSummary
    analytics: "TeacherSessionAnalytics"
    student_roster_scope: str
    student_roster_live: bool
    student_roster: list[TeacherStudentRosterEntry]
    attendance_records: list["AttendanceRecordSummary"]
    help_requests: list["TeacherHelpRequestSummary"]


class TeacherSubmissionsResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    assignment_title: str
    session_status: str
    submissions: list["SubmissionQueueItem"]
    analytics: "TeacherSessionAnalytics"


class AttendanceRecordSummary(BaseModel):
    id: int
    student_name: str
    student_username: str
    status: AttendanceStatus
    marked_at: str | None = None
    note: str | None = None
    last_seen_at: str | None = None


class SubmissionQueueItem(BaseModel):
    id: int
    student_name: str
    student_username: str
    title: str
    status: SubmissionStatus
    version: int
    draft_saved_at: str | None = None
    submitted_at: str | None = None
    help_requested: bool = False
    review_decision: ReviewDecision | None = None
    reviewed_at: str | None = None


class TeacherHelpRequestSummary(BaseModel):
    id: int
    student_name: str
    student_username: str
    message: str
    created_at: str
    status: str


class SubmissionReviewSummary(BaseModel):
    id: int
    reviewer_name: str
    decision: ReviewDecision
    feedback: str
    created_at: str


class TeacherSubmissionDetail(BaseModel):
    id: int
    student_name: str
    student_username: str
    title: str
    content: str
    status: SubmissionStatus
    version: int
    draft_saved_at: str | None = None
    submitted_at: str | None = None
    teacher_feedback: str | None = None
    review_decision: ReviewDecision | None = None
    reviewed_at: str | None = None
    help_requested: bool
    help_messages: list[TeacherHelpRequestSummary]
    history: list[SubmissionHistoryEntry]
    reviews: list[SubmissionReviewSummary]


class TeacherDraft(BaseModel):
    id: int
    draft_type: str
    title: str
    content: str
    created_at: str
    updated_at: str | None = None
    status: Literal["draft", "accepted", "rejected"]


class TeacherAnalyticsAttentionStudent(BaseModel):
    student_name: str
    student_username: str
    progress_percent: int
    presence_status: str
    reason: str


class TeacherSessionAnalytics(BaseModel):
    attendance_rate: int
    average_progress: int
    submission_rate: int
    reviewed_rate: int
    present_count: int
    late_count: int
    absent_count: int
    pending_count: int
    draft_count: int
    submitted_count: int
    reviewed_count: int
    approved_count: int
    revision_requested_count: int
    rejected_count: int
    attention_students: list[TeacherAnalyticsAttentionStudent]
    highlights: list[str]


class TeacherReflectionSummary(BaseModel):
    id: int | None = None
    strengths: str = ""
    risks: str = ""
    next_actions: str = ""
    student_support_plan: str = ""
    ai_draft_content: str | None = None
    updated_at: str | None = None


class TeacherConsoleResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    assignment_title: str
    session_status: str
    radar: RadarSummary
    workbench_steps: list[TodoItem]
    lesson_plans: list[TeacherCourseSummary]
    managed_classrooms: list[TeacherClassroomSummary]
    resource_categories: list[ResourceCategorySummary]
    student_roster_scope: str
    student_roster_live: bool
    student_roster: list[TeacherStudentRosterEntry]
    launch_options: list[TeacherLaunchOption]
    resources: list[TeacherResourceSummary]
    attendance_records: list[AttendanceRecordSummary]
    help_requests: list[TeacherHelpRequestSummary]
    submissions: list[SubmissionQueueItem]
    analytics: TeacherSessionAnalytics
    reflection: TeacherReflectionSummary
    ai_drafts: list[TeacherDraft]


class TeacherCopilotResponse(BaseModel):
    session_id: int | None = None
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    session_status: str
    reflection: TeacherReflectionSummary
    analytics: TeacherSessionAnalytics
    ai_drafts: list[TeacherDraft]


class TeacherResourcesResponse(BaseModel):
    school_name: str
    teacher_name: str
    managed_classrooms: list[TeacherClassroomSummary]
    resource_categories: list[ResourceCategorySummary]
    resources: list[TeacherResourceSummary]


class TeacherCourseDetailResponse(BaseModel):
    course: TeacherCourseSummary
    activities: list[CourseActivitySummary]


class TeacherCourseCollectionResponse(BaseModel):
    school_name: str
    teacher_name: str
    managed_classrooms: list[TeacherClassroomSummary]
    launch_options: list[TeacherLaunchOption]
    courses: list[TeacherCourseSummary]
    selected_course: TeacherCourseDetailResponse | None = None


class CreateDraftRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)


class CreateDraftResponse(BaseModel):
    draft: TeacherDraft


class TeacherDraftUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=1000)


class StartSessionRequest(BaseModel):
    classroom_id: int
    course_id: int


class TeacherCourseActivitySaveRequest(BaseModel):
    id: int | None = None
    title: str = Field(min_length=1, max_length=128)
    activity_type: CourseActivityType
    summary: str | None = Field(default=None, max_length=255)
    instructions_html: str = Field(default="", max_length=20000)


class TeacherCourseSaveRequest(BaseModel):
    course_id: int | None = None
    title: str = Field(min_length=1, max_length=128)
    stage_label: str = Field(min_length=1, max_length=64)
    overview: str | None = Field(default=None, max_length=2000)
    assignment_title: str = Field(min_length=1, max_length=128)
    assignment_prompt: str = Field(min_length=1, max_length=5000)
    activities: list[TeacherCourseActivitySaveRequest] = Field(default_factory=list)
    publish_now: bool = False


class AttendanceMarkRequest(BaseModel):
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=255)


class SubmissionReviewRequest(BaseModel):
    decision: ReviewDecision
    feedback: str = Field(min_length=1, max_length=2000)
    resolve_help_requests: bool = True


class TeacherReflectionRequest(BaseModel):
    strengths: str = Field(default="", max_length=2000)
    risks: str = Field(default="", max_length=2000)
    next_actions: str = Field(default="", max_length=2000)
    student_support_plan: str = Field(default="", max_length=2000)


class TeacherReflectionDraftResponse(BaseModel):
    draft: TeacherDraft
    reflection: TeacherReflectionSummary


class TeacherResourceStatusRequest(BaseModel):
    active: bool


class ActivitySubmissionPayload(BaseModel):
    payload: Any


class ResourceCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=1, ge=1, le=999)


class ResourceCategoryStatusRequest(BaseModel):
    active: bool


class BackupCreateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class BackupSnapshotSummary(BaseModel):
    id: int
    school_id: int | None = None
    school_name: str
    actor_display_name: str
    actor_username: str
    actor_role: UserRole
    file_name: str
    file_size: int
    file_size_label: str
    status: BackupSnapshotStatus
    note: str | None = None
    created_at: str
    restored_at: str | None = None


class AdminAuditLogSummary(BaseModel):
    id: int
    actor_display_name: str
    actor_username: str
    actor_role: UserRole
    action: str
    target_type: str
    target_id: str | None = None
    target_label: str
    level: AuditLogLevel
    summary: str
    detail: str | None = None
    created_at: str


class MigrationPreviewRow(BaseModel):
    id: int
    field_name: str
    legacy_value: str
    new_value: str
    status: str
    issue_detail: str | None = None
    resolution_note: str | None = None
    resolved_at: str | None = None
    requires_resolution: bool

    model_config = ConfigDict(from_attributes=True)


class MigrationBatchSummary(BaseModel):
    id: int
    name: str
    status: str
    progress: int
    current_step: str
    error_count: int
    preview_rows: list[MigrationPreviewRow]


class LegacyMappingSummary(BaseModel):
    id: int
    entity_type: str
    legacy_id: str
    new_id: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class MigrationFixRequest(BaseModel):
    new_value: str = Field(min_length=1, max_length=128)
    resolution_note: str = Field(min_length=1, max_length=255)
    status: Literal["mapped", "resolved"] = "resolved"


class GovernanceSchoolSnapshot(BaseModel):
    school: SchoolSummary
    latest_batch_name: str | None = None
    latest_batch_status: str | None = None
    latest_batch_progress: int | None = None
    current_step: str | None = None
    unresolved_preview_count: int = 0
    can_execute_migration: bool = False
    can_rollback_migration: bool = False
    is_current: bool = False


class AcademicTermSummary(BaseModel):
    id: int
    school_year_label: str
    term_name: str
    start_on: str | None = None
    end_on: str | None = None
    is_active: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class AdminClassroomSummary(BaseModel):
    id: int
    name: str
    grade_label: str
    student_count: int


class AdminStudentSummary(BaseModel):
    id: int
    username: str
    display_name: str
    classroom_id: int | None = None
    classroom_name: str | None = None
    active: bool


class AdminTeacherSummary(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    active: bool
    assigned_classroom_ids: list[int] = Field(default_factory=list)
    assigned_classroom_names: list[str] = Field(default_factory=list)


class AdminOverviewResponse(BaseModel):
    school_name: str
    admin_name: str
    active_school_count: int
    current_school: SchoolSummary
    managed_schools: list[SchoolSummary]
    school_snapshots: list[GovernanceSchoolSnapshot]
    active_term: AcademicTermSummary | None = None
    academic_terms: list[AcademicTermSummary]
    classrooms: list[AdminClassroomSummary]
    resource_categories: list[ResourceCategorySummary]
    backup_snapshots: list[BackupSnapshotSummary]
    recent_audit_logs: list[AdminAuditLogSummary]
    teacher_accounts: list[AdminTeacherSummary]
    students: list[AdminStudentSummary]
    active_migration: MigrationBatchSummary
    legacy_mappings: list[LegacyMappingSummary]
    can_execute_migration: bool
    can_rollback_migration: bool
    unresolved_preview_count: int
    guardrails: list[str]


class AcademicTermCreateRequest(BaseModel):
    school_year_label: str = Field(min_length=1, max_length=32)
    term_name: str = Field(min_length=1, max_length=64)
    start_on: str | None = Field(default=None, max_length=10)
    end_on: str | None = Field(default=None, max_length=10)
    activate_now: bool = True


class SchoolSettingsUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    city: str = Field(min_length=1, max_length=64)
    slogan: str = Field(min_length=1, max_length=255)
    theme_style: ThemeStyle


class StudentAssignmentRequest(BaseModel):
    classroom_id: int


class TeacherAccountSaveRequest(BaseModel):
    teacher_id: int | None = None
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    role: Literal["teacher", "school_admin"] = "teacher"
    password: str | None = Field(default=None, min_length=1, max_length=64)
    classroom_ids: list[int] = Field(default_factory=list)


class StudentImportRequest(BaseModel):
    classroom_id: int
    rows_text: str = Field(min_length=1, max_length=20000)
    default_password: str = Field(default="12345", min_length=1, max_length=64)


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=64)


class UserStatusUpdateRequest(BaseModel):
    active: bool


class StudentImportResult(BaseModel):
    imported_count: int
    updated_count: int
    skipped_count: int


class AdminStudentImportResponse(BaseModel):
    overview: AdminOverviewResponse
    result: StudentImportResult


class MessageResponse(BaseModel):
    message: str
    updated_at: datetime | None = None
