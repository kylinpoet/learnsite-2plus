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
    Submission,
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
    SubmissionUpsertRequest,
    TodoItem,
)

router = APIRouter(prefix="/student", tags=["student"])


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


def _serialize_submission(submission: Submission | None) -> StudentSubmissionSummary:
    if submission is None:
        return StudentSubmissionSummary(
            title="",
            content="",
            status=SubmissionStatus.DRAFT,
            version=1,
            can_edit=True,
        )

    return StudentSubmissionSummary(
        id=submission.id,
        title=submission.title,
        content=submission.content,
        status=submission.status,
        version=submission.version,
        draft_saved_at=submission.draft_saved_at.strftime("%H:%M") if submission.draft_saved_at else None,
        submitted_at=submission.submitted_at.strftime("%H:%M") if submission.submitted_at else None,
        can_edit=submission.status != SubmissionStatus.SUBMITTED,
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
    else:
        if submission.status == SubmissionStatus.SUBMITTED and not final_submit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Submission already submitted and cannot be edited.",
            )
        submission.title = payload.title
        submission.content = payload.content
        submission.version += 1
        submission.draft_saved_at = now
        if final_submit:
            submission.status = SubmissionStatus.SUBMITTED
            submission.submitted_at = now

    presence.status = PresenceStatus.ACTIVE
    presence.task_progress = 100 if final_submit else max(presence.task_progress, 82)
    presence.last_seen_at = now
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

    saved_label = "尚未保存"
    if submission and submission.draft_saved_at:
        saved_label = submission.draft_saved_at.strftime("%H:%M")

    todo_items = [
        TodoItem(title="阅读导学说明", status="done"),
        TodoItem(title="完成课堂作品草稿", status="active"),
        TodoItem(
            title="正式提交课堂作品",
            status="done" if submission and submission.status == SubmissionStatus.SUBMITTED else "pending",
        ),
    ]
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
        progress_summary="先整理课堂数据和结论，再保存草稿，确认无误后正式提交给老师。",
        saved_at=saved_label,
        todo_items=todo_items,
        highlights=[
            "支持先保存草稿，再正式提交，不会因为误操作丢失内容。",
            "教师端会实时看到你的提交状态和课堂在线状态。",
            "如果卡住，可以随时向老师发起求助。",
        ],
        help_open=presence.help_requested,
        attendance_status=attendance.status,
        submission=_serialize_submission(submission),
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
    updated_at = submission.draft_saved_at or datetime.utcnow()
    return SubmissionActionResponse(
        message="Draft saved.",
        submission=_serialize_submission(submission),
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
    updated_at = submission.submitted_at or datetime.utcnow()
    return SubmissionActionResponse(
        message="Submission completed.",
        submission=_serialize_submission(submission),
        updated_at=updated_at,
    )
