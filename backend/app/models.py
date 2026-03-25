from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


class ThemeStyle(str, Enum):
    WORKSHOP = "workshop"
    MATERIAL = "material"
    NATURAL = "natural"


class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    SCHOOL_ADMIN = "school_admin"
    PLATFORM_ADMIN = "platform_admin"


class PresenceStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    NOT_STARTED = "not_started"
    OFFLINE = "offline"


class MigrationStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PREVIEWED = "previewed"
    EXECUTING = "executing"
    PARTIALLY_FAILED = "partially_failed"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class TodoStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"


class AttendanceStatus(str, Enum):
    PENDING = "pending"
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    EXCUSED = "excused"


class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"


class SubmissionRevisionAction(str, Enum):
    DRAFT_SAVED = "draft_saved"
    SUBMITTED = "submitted"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    city: Mapped[str] = mapped_column(String(64))
    slogan: Mapped[str] = mapped_column(String(255))
    theme_style: Mapped[ThemeStyle] = mapped_column(SqlEnum(ThemeStyle), default=ThemeStyle.WORKSHOP)

    users: Mapped[list["User"]] = relationship(back_populates="school")
    classrooms: Mapped[list["Classroom"]] = relationship(back_populates="school")


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    grade_label: Mapped[str] = mapped_column(String(32))

    school: Mapped[School] = relationship(back_populates="classrooms")
    students: Mapped[list["User"]] = relationship(back_populates="classroom")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("school_id", "username", name="uq_users_school_username"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    classroom_id: Mapped[int | None] = mapped_column(ForeignKey("classrooms.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), index=True)
    active: Mapped[bool] = mapped_column(default=True)

    school: Mapped[School] = relationship(back_populates="users")
    classroom: Mapped[Classroom | None] = relationship(back_populates="students")


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    stage_label: Mapped[str] = mapped_column(String(64))
    assignment_title: Mapped[str] = mapped_column(String(128))
    assignment_prompt: Mapped[str] = mapped_column(Text)


class ClassSession(Base, TimestampMixin):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(128))
    stage: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    expected_students: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AttendanceRecord(Base, TimestampMixin):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_attendance_session_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        SqlEnum(AttendanceStatus),
        default=AttendanceStatus.PENDING,
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PresenceState(Base, TimestampMixin):
    __tablename__ = "presence_states"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_presence_session_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[PresenceStatus] = mapped_column(SqlEnum(PresenceStatus), default=PresenceStatus.NOT_STARTED)
    task_progress: Mapped[int] = mapped_column(Integer, default=0)
    help_requested: Mapped[bool] = mapped_column(default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_submission_session_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[SubmissionStatus] = mapped_column(SqlEnum(SubmissionStatus), default=SubmissionStatus.DRAFT)
    version: Mapped[int] = mapped_column(Integer, default=1)
    draft_saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_decision: Mapped[ReviewDecision | None] = mapped_column(SqlEnum(ReviewDecision), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    revisions: Mapped[list["SubmissionRevision"]] = relationship(back_populates="submission")
    reviews: Mapped[list["SubmissionReview"]] = relationship(back_populates="submission")


class SubmissionRevision(Base):
    __tablename__ = "submission_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    action: Mapped[SubmissionRevisionAction] = mapped_column(SqlEnum(SubmissionRevisionAction))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="revisions")


class SubmissionReview(Base, TimestampMixin):
    __tablename__ = "submission_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(SqlEnum(ReviewDecision))
    feedback: Mapped[str] = mapped_column(Text)
    ai_draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="reviews")


class HelpRequest(Base, TimestampMixin):
    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="open")


class MigrationBatch(Base, TimestampMixin):
    __tablename__ = "migration_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[MigrationStatus] = mapped_column(SqlEnum(MigrationStatus), default=MigrationStatus.DRAFT)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(128))
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    preview_rows: Mapped[list["MigrationPreviewItem"]] = relationship(back_populates="batch")
    legacy_mappings: Mapped[list["LegacyIdMapping"]] = relationship(back_populates="batch")


class MigrationPreviewItem(Base):
    __tablename__ = "migration_preview_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("migration_batches.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(64))
    legacy_value: Mapped[str] = mapped_column(String(128))
    new_value: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    issue_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch: Mapped[MigrationBatch] = relationship(back_populates="preview_rows")


class LegacyIdMapping(Base, TimestampMixin):
    __tablename__ = "legacy_id_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("migration_batches.id"), index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    legacy_id: Mapped[str] = mapped_column(String(128))
    new_id: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    batch: Mapped[MigrationBatch] = relationship(back_populates="legacy_mappings")


class AISuggestionDraft(Base, TimestampMixin):
    __tablename__ = "ai_suggestion_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), index=True)
    draft_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="draft")
