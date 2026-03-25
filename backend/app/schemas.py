from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ThemeStyle, UserRole


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


class StudentHomeResponse(BaseModel):
    school_name: str
    student_name: str
    class_name: str
    lesson_title: str
    lesson_stage: str
    progress_percent: int
    progress_summary: str
    saved_at: str
    todo_items: list[TodoItem]
    highlights: list[str]
    help_open: bool


class HeartbeatRequest(BaseModel):
    task_progress: int = Field(default=72, ge=0, le=100)


class HelpRequestCreate(BaseModel):
    message: str


class RadarSummary(BaseModel):
    online: int
    expected: int
    absent: int
    idle: int
    not_started: int
    help_requests: int


class TeacherDraft(BaseModel):
    id: int
    draft_type: str
    title: str
    content: str
    created_at: str
    status: str


class TeacherConsoleResponse(BaseModel):
    school_name: str
    teacher_name: str
    class_name: str
    lesson_title: str
    session_status: str
    radar: RadarSummary
    workbench_steps: list[TodoItem]
    ai_drafts: list[TeacherDraft]


class CreateDraftRequest(BaseModel):
    goal: str


class CreateDraftResponse(BaseModel):
    draft: TeacherDraft


class MigrationPreviewRow(BaseModel):
    field_name: str
    legacy_value: str
    new_value: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class MigrationBatchSummary(BaseModel):
    name: str
    status: str
    progress: int
    current_step: str
    error_count: int
    preview_rows: list[MigrationPreviewRow]


class AdminOverviewResponse(BaseModel):
    school_name: str
    admin_name: str
    active_school_count: int
    managed_schools: list[SchoolSummary]
    active_migration: MigrationBatchSummary
    guardrails: list[str]


class MessageResponse(BaseModel):
    message: str
    updated_at: datetime | None = None
