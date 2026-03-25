from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AttendanceStatus,
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
    status: str


class TeacherConsoleResponse(BaseModel):
    session_id: int
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    assignment_title: str
    session_status: str
    radar: RadarSummary
    workbench_steps: list[TodoItem]
    launch_options: list[TeacherLaunchOption]
    attendance_records: list[AttendanceRecordSummary]
    help_requests: list[TeacherHelpRequestSummary]
    submissions: list[SubmissionQueueItem]
    ai_drafts: list[TeacherDraft]


class CreateDraftRequest(BaseModel):
    goal: str


class CreateDraftResponse(BaseModel):
    draft: TeacherDraft


class StartSessionRequest(BaseModel):
    classroom_id: int
    course_id: int


class AttendanceMarkRequest(BaseModel):
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=255)


class SubmissionReviewRequest(BaseModel):
    decision: ReviewDecision
    feedback: str = Field(min_length=1, max_length=2000)
    resolve_help_requests: bool = True


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


class AdminOverviewResponse(BaseModel):
    school_name: str
    admin_name: str
    active_school_count: int
    current_school: SchoolSummary
    managed_schools: list[SchoolSummary]
    school_snapshots: list[GovernanceSchoolSnapshot]
    active_migration: MigrationBatchSummary
    legacy_mappings: list[LegacyMappingSummary]
    can_execute_migration: bool
    can_rollback_migration: bool
    unresolved_preview_count: int
    guardrails: list[str]


class MessageResponse(BaseModel):
    message: str
    updated_at: datetime | None = None
