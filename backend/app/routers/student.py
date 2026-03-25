from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import (
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    HelpRequest,
    PresenceState,
    PresenceStatus,
    ReviewDecision,
    Submission,
    SubmissionRevision,
    SubmissionRevisionAction,
    SubmissionReview,
    SubmissionStatus,
    User,
    UserRole,
)
from ..schemas import (
    HeartbeatRequest,
    HelpRequestCreate,
    MessageResponse,
    StudentHomeResponse,
    StudentSubmissionSummary,
    SubmissionActionResponse,
    SubmissionHistoryEntry,
    SubmissionUpsertRequest,
    TodoItem,
)

router = APIRouter(prefix="/student", tags=["student"])


def _format_hm(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _format_full(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _shorten(text: str, *, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}…"


def _get_student(db: Session, principal: Principal) -> User:
    student = db.scalar(
        select(User).where(
            User.id == principal.user_id,
            User.school_id == principal.school_id,
            User.role == UserRole.STUDENT,
        )
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return student


def _get_active_session(
    db: Session,
    school_id: int,
    classroom_id: int | None,
) -> tuple[ClassSession, Course, Classroom]:
    session_obj = db.scalar(
        select(ClassSession)
        .where(
            ClassSession.school_id == school_id,
            ClassSession.classroom_id == classroom_id,
            ClassSession.status == "active",
        )
        .order_by(ClassSession.started_at.desc())
    )
    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active class session.")

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom


def _get_or_create_presence(db: Session, principal: Principal, session_id: int, user_id: int) -> PresenceState:
    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == session_id,
            PresenceState.user_id == user_id,
        )
    )
    if presence is None:
        presence = PresenceState(
            school_id=principal.school_id,
            session_id=session_id,
            user_id=user_id,
            status=PresenceStatus.NOT_STARTED,
            task_progress=0,
            help_requested=False,
            last_seen_at=datetime.utcnow(),
        )
        db.add(presence)
        db.flush()
    return presence


def _get_or_create_attendance(
    db: Session,
    principal: Principal,
    session_id: int,
    user_id: int,
) -> AttendanceRecord:
    attendance = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.user_id == user_id,
        )
    )
    if attendance is None:
        attendance = AttendanceRecord(
            school_id=principal.school_id,
            session_id=session_id,
            user_id=user_id,
            status=AttendanceStatus.PENDING,
        )
        db.add(attendance)
        db.flush()
    return attendance


def _can_edit_reviewed_submission(submission: Submission) -> bool:
    return submission.review_decision in {ReviewDecision.REVISION_REQUESTED, ReviewDecision.REJECTED}


def _serialize_submission(submission: Submission | None, reviewer_name: str | None = None) -> StudentSubmissionSummary:
    if submission is None:
        return StudentSubmissionSummary(
            title="",
            content="",
            status=SubmissionStatus.DRAFT,
            version=1,
            can_edit=True,
        )

    can_edit = True
    if submission.status == SubmissionStatus.SUBMITTED:
        can_edit = False
    elif submission.status == SubmissionStatus.REVIEWED:
        can_edit = _can_edit_reviewed_submission(submission)

    return StudentSubmissionSummary(
        id=submission.id,
        title=submission.title,
        content=submission.content,
        status=submission.status,
        version=submission.version,
        draft_saved_at=_format_hm(submission.draft_saved_at),
        submitted_at=_format_hm(submission.submitted_at),
        teacher_feedback=submission.teacher_feedback,
        review_decision=submission.review_decision,
        reviewed_at=_format_hm(submission.reviewed_at),
        reviewed_by=reviewer_name,
        can_edit=can_edit,
    )


def _build_submission_history(db: Session, submission: Submission | None) -> list[SubmissionHistoryEntry]:
    if submission is None:
        return []

    student = db.get(User, submission.user_id)
    student_name = student.display_name if student else "学生"
    rows: list[tuple[datetime, SubmissionHistoryEntry]] = []

    revisions = db.scalars(
        select(SubmissionRevision)
        .where(SubmissionRevision.submission_id == submission.id)
        .order_by(SubmissionRevision.created_at.desc(), SubmissionRevision.id.desc())
    ).all()
    for revision in revisions:
        if revision.action == SubmissionRevisionAction.SUBMITTED:
            summary = f"正式提交了第 v{revision.version} 版作品"
            entry_type = "submitted"
        else:
            summary = f"保存了第 v{revision.version} 版草稿"
            entry_type = "draft_saved"
        rows.append(
            (
                revision.created_at,
                SubmissionHistoryEntry(
                    id=revision.id,
                    entry_type=entry_type,
                    summary=summary,
                    actor_name=student_name,
                    occurred_at=_format_full(revision.created_at),
                    version=revision.version,
                ),
            )
        )

    reviews = db.scalars(
        select(SubmissionReview)
        .where(SubmissionReview.submission_id == submission.id)
        .order_by(SubmissionReview.created_at.desc(), SubmissionReview.id.desc())
    ).all()
    for review in reviews:
        reviewer = db.get(User, review.reviewer_user_id)
        reviewer_name = reviewer.display_name if reviewer else "教师"
        rows.append(
            (
                review.created_at,
                SubmissionHistoryEntry(
                    id=review.id,
                    entry_type="reviewed",
                    summary=_shorten(review.feedback),
                    actor_name=reviewer_name,
                    occurred_at=_format_full(review.created_at),
                    decision=review.decision,
                ),
            )
        )

    rows.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in rows]


def _record_submission_revision(
    db: Session,
    submission: Submission,
    *,
    action: SubmissionRevisionAction,
) -> None:
    db.add(
        SubmissionRevision(
            submission_id=submission.id,
            school_id=submission.school_id,
            session_id=submission.session_id,
            user_id=submission.user_id,
            version=submission.version,
            title=submission.title,
            content=submission.content,
            action=action,
            created_at=datetime.utcnow(),
        )
    )


def _upsert_submission(
    db: Session,
    principal: Principal,
    session_id: int,
    user_id: int,
    payload: SubmissionUpsertRequest,
    *,
    final_submit: bool,
) -> tuple[Submission, PresenceState]:
    submission = db.scalar(
        select(Submission).where(
            Submission.session_id == session_id,
            Submission.user_id == user_id,
        )
    )
    now = datetime.utcnow()
    presence = _get_or_create_presence(db, principal, session_id, user_id)

    if submission is None:
        submission = Submission(
            school_id=principal.school_id,
            session_id=session_id,
            user_id=user_id,
            title=payload.title,
            content=payload.content,
            status=SubmissionStatus.SUBMITTED if final_submit else SubmissionStatus.DRAFT,
            version=1,
            draft_saved_at=now,
            submitted_at=now if final_submit else None,
        )
        db.add(submission)
        db.flush()
    else:
        if submission.status == SubmissionStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Submission already submitted and is waiting for teacher review.",
            )
        if submission.status == SubmissionStatus.REVIEWED and not _can_edit_reviewed_submission(submission):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reviewed submission cannot be edited.",
            )

        submission.title = payload.title
        submission.content = payload.content
        submission.version += 1
        submission.draft_saved_at = now
        submission.submitted_at = now if final_submit else None
        submission.status = SubmissionStatus.SUBMITTED if final_submit else SubmissionStatus.DRAFT
        submission.teacher_feedback = None
        submission.review_decision = None
        submission.reviewed_by_user_id = None
        submission.reviewed_at = None
        db.flush()

    _record_submission_revision(
        db,
        submission,
        action=SubmissionRevisionAction.SUBMITTED if final_submit else SubmissionRevisionAction.DRAFT_SAVED,
    )

    presence.status = PresenceStatus.ACTIVE
    presence.task_progress = 100 if final_submit else max(presence.task_progress, 82)
    presence.last_seen_at = now
    if final_submit:
        presence.help_requested = False
    db.flush()
    return submission, presence


@router.get("/home", response_model=StudentHomeResponse)
def student_home(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentHomeResponse:
    student = _get_student(db, principal)
    session_obj, course, classroom = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)
    attendance = _get_or_create_attendance(db, principal, session_obj.id, student.id)
    submission = db.scalar(
        select(Submission).where(
            Submission.session_id == session_obj.id,
            Submission.user_id == student.id,
        )
    )

    reviewer_name = None
    if submission and submission.reviewed_by_user_id:
        reviewer = db.get(User, submission.reviewed_by_user_id)
        reviewer_name = reviewer.display_name if reviewer else None

    saved_label = "尚未保存"
    if submission and submission.draft_saved_at:
        saved_label = _format_hm(submission.draft_saved_at) or saved_label

    todo_items = [
        TodoItem(title="阅读老师给出的任务说明", status="done"),
        TodoItem(title="完成课堂作品草稿", status="done" if submission else "active"),
        TodoItem(
            title="正式提交课堂作品",
            status="done" if submission and submission.status != SubmissionStatus.DRAFT else "pending",
        ),
    ]
    if submission and submission.status == SubmissionStatus.REVIEWED and _can_edit_reviewed_submission(submission):
        todo_items.append(TodoItem(title="根据教师反馈修改后再次提交", status="active"))

    return StudentHomeResponse(
        school_name=principal.school_name,
        student_name=student.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        lesson_stage=session_obj.stage,
        assignment_title=course.assignment_title,
        assignment_prompt=course.assignment_prompt,
        session_status=session_obj.status,
        progress_percent=presence.task_progress,
        progress_summary="先整理课堂观察、图表或结论，再保存草稿；确认无误后正式提交给老师。",
        saved_at=saved_label,
        todo_items=todo_items,
        highlights=[
            "支持先保存草稿，再正式提交，避免课堂中途丢失内容。",
            "老师批改后，你可以在同一页面看到反馈和提交历史。",
            "如果卡住了，随时可以举手求助，教师端会实时收到提醒。",
        ],
        help_open=presence.help_requested,
        attendance_status=attendance.status,
        submission=_serialize_submission(submission, reviewer_name),
        submission_history=_build_submission_history(db, submission),
    )


@router.post("/heartbeat", response_model=MessageResponse)
def heartbeat(
    payload: HeartbeatRequest,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)
    attendance = _get_or_create_attendance(db, principal, session_obj.id, student.id)

    now = datetime.utcnow()
    presence.status = PresenceStatus.ACTIVE
    presence.last_seen_at = now
    presence.task_progress = max(presence.task_progress, payload.task_progress)
    if attendance.status == AttendanceStatus.PENDING:
        attendance.status = AttendanceStatus.PRESENT
        attendance.marked_at = now

    db.commit()
    return MessageResponse(message="Heartbeat accepted.", updated_at=now)


@router.post("/help-requests", response_model=MessageResponse)
def create_help_request(
    payload: HelpRequestCreate,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)

    now = datetime.utcnow()
    presence.help_requested = True
    presence.last_seen_at = now
    db.add(
        HelpRequest(
            school_id=principal.school_id,
            session_id=session_obj.id,
            user_id=student.id,
            message=payload.message,
            status="open",
        )
    )
    db.commit()
    return MessageResponse(message="Help request created.", updated_at=now)


@router.post("/submission/draft", response_model=SubmissionActionResponse)
def save_submission_draft(
    payload: SubmissionUpsertRequest,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> SubmissionActionResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    submission, _ = _upsert_submission(
        db,
        principal,
        session_obj.id,
        student.id,
        payload,
        final_submit=False,
    )
    db.commit()
    db.refresh(submission)
    reviewer_name = None
    updated_at = submission.draft_saved_at or datetime.utcnow()
    return SubmissionActionResponse(
        message="Draft saved.",
        submission=_serialize_submission(submission, reviewer_name),
        updated_at=updated_at,
    )


@router.post("/submission/submit", response_model=SubmissionActionResponse)
def submit_assignment(
    payload: SubmissionUpsertRequest,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> SubmissionActionResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    submission, _ = _upsert_submission(
        db,
        principal,
        session_obj.id,
        student.id,
        payload,
        final_submit=True,
    )
    db.commit()
    db.refresh(submission)
    reviewer_name = None
    updated_at = submission.submitted_at or datetime.utcnow()
    return SubmissionActionResponse(
        message="Submission completed.",
        submission=_serialize_submission(submission, reviewer_name),
        updated_at=updated_at,
    )
