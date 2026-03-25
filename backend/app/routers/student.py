from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import get_db
from ..models import ClassSession, Classroom, Course, HelpRequest, PresenceState, PresenceStatus, User, UserRole
from ..schemas import HeartbeatRequest, HelpRequestCreate, MessageResponse, StudentHomeResponse, TodoItem

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


def _get_active_session(db: Session, school_id: int, classroom_id: int | None) -> tuple[ClassSession, Course, Classroom]:
    session_obj = db.scalar(
        select(ClassSession)
        .where(ClassSession.school_id == school_id, ClassSession.classroom_id == classroom_id)
        .order_by(ClassSession.started_at.desc())
    )
    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active class session.")
    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom


@router.get("/home", response_model=StudentHomeResponse)
def student_home(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentHomeResponse:
    student = _get_student(db, principal)
    session_obj, course, classroom = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == session_obj.id,
            PresenceState.user_id == student.id,
        )
    )
    if presence is None:
        presence = PresenceState(
            school_id=principal.school_id,
            session_id=session_obj.id,
            user_id=student.id,
            status=PresenceStatus.NOT_STARTED,
            task_progress=0,
            help_requested=False,
            last_seen_at=datetime.utcnow(),
        )
        db.add(presence)
        db.commit()
        db.refresh(presence)

    todo_items = [
        TodoItem(title="阅读导学说明", status="done"),
        TodoItem(title="完成数据采集", status="active"),
        TodoItem(title="上传图表作品", status="pending"),
    ]
    return StudentHomeResponse(
        school_name=principal.school_name,
        student_name=student.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        lesson_stage=session_obj.stage,
        progress_percent=presence.task_progress,
        progress_summary="先完成数据采集，再上传图表作品，教师端会实时看到你的进度变化。",
        saved_at=presence.updated_at.strftime("%H:%M"),
        todo_items=todo_items,
        highlights=[
            "本节课作品先保存为草稿，再确认正式提交。",
            "如果卡住，可以直接向教师端发起求助。",
            "平台会自动维持课堂心跳，让教师看到你的在线状态。",
        ],
        help_open=presence.help_requested,
    )


@router.post("/heartbeat", response_model=MessageResponse)
def heartbeat(
    payload: HeartbeatRequest,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == session_obj.id,
            PresenceState.user_id == student.id,
        )
    )
    if presence is None:
        presence = PresenceState(
            school_id=principal.school_id,
            session_id=session_obj.id,
            user_id=student.id,
            status=PresenceStatus.ACTIVE,
            task_progress=payload.task_progress,
            help_requested=False,
            last_seen_at=datetime.utcnow(),
        )
        db.add(presence)
    else:
        presence.status = PresenceStatus.ACTIVE
        presence.last_seen_at = datetime.utcnow()
        presence.task_progress = max(presence.task_progress, payload.task_progress)
    db.commit()
    db.refresh(presence)
    return MessageResponse(message="Heartbeat accepted.", updated_at=presence.last_seen_at)


@router.post("/help-requests", response_model=MessageResponse)
def create_help_request(
    payload: HelpRequestCreate,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == session_obj.id,
            PresenceState.user_id == student.id,
        )
    )
    if presence is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Presence state missing.")

    presence.help_requested = True
    presence.last_seen_at = datetime.utcnow()
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
    return MessageResponse(message="Help request created.", updated_at=presence.last_seen_at)
