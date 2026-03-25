from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.database import SessionLocal, get_db
from ..models import (
    AISuggestionDraft,
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    PresenceState,
    PresenceStatus,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from ..schemas import (
    AttendanceMarkRequest,
    AttendanceRecordSummary,
    CreateDraftRequest,
    CreateDraftResponse,
    MessageResponse,
    RadarSummary,
    StartSessionRequest,
    SubmissionQueueItem,
    TeacherConsoleResponse,
    TeacherDraft,
    TeacherLaunchOption,
    TodoItem,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])

ALLOWED_ROLES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)


def _resolve_operator(db: Session, principal: Principal) -> User:
    operator = db.scalar(
        select(User).where(
            User.id == principal.user_id,
            User.school_id == principal.school_id,
        )
    )
    if operator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found.")
    return operator


def _get_current_session(db: Session, principal: Principal, operator: User) -> tuple[ClassSession, Course, Classroom]:
    query = select(ClassSession).where(
        ClassSession.school_id == principal.school_id,
        ClassSession.status == "active",
    )
    if principal.role == UserRole.TEACHER:
        query = query.where(ClassSession.teacher_id == operator.id)

    session_obj = db.scalar(query.order_by(ClassSession.started_at.desc()))
    if session_obj is None:
        fallback_query = select(ClassSession).where(ClassSession.school_id == principal.school_id)
        if principal.role == UserRole.TEACHER:
            fallback_query = fallback_query.where(ClassSession.teacher_id == operator.id)
        session_obj = db.scalar(fallback_query.order_by(ClassSession.started_at.desc()))

    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No teaching session found.")

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom


def _build_radar_summary(db: Session, session_obj: ClassSession) -> RadarSummary:
    rows = db.scalars(select(PresenceState).where(PresenceState.session_id == session_obj.id)).all()
    now = datetime.utcnow()
    absent = 0
    idle = 0
    not_started = 0
    help_requests = 0

    for row in rows:
        age = now - row.last_seen_at
        if age > timedelta(seconds=45) or row.status == PresenceStatus.OFFLINE:
            absent += 1
        elif age > timedelta(seconds=25) or row.status == PresenceStatus.IDLE:
            idle += 1
        if row.status == PresenceStatus.NOT_STARTED:
            not_started += 1
        if row.help_requested:
            help_requests += 1

    online = max(session_obj.expected_students - absent, 0)
    return RadarSummary(
        online=online,
        expected=session_obj.expected_students,
        absent=absent,
        idle=idle,
        not_started=not_started,
        help_requests=help_requests,
    )


def _serialize_draft(draft: AISuggestionDraft) -> TeacherDraft:
    return TeacherDraft(
        id=draft.id,
        draft_type=draft.draft_type,
        title=draft.title,
        content=draft.content,
        created_at=draft.created_at.strftime("%Y-%m-%d %H:%M"),
        status=draft.status,
    )


def _list_launch_options(db: Session, school_id: int) -> list[TeacherLaunchOption]:
    classrooms = db.scalars(select(Classroom).where(Classroom.school_id == school_id).order_by(Classroom.id)).all()
    courses = db.scalars(select(Course).where(Course.school_id == school_id).order_by(Course.id)).all()
    options: list[TeacherLaunchOption] = []
    for classroom in classrooms:
        for course in courses:
            options.append(
                TeacherLaunchOption(
                    classroom_id=classroom.id,
                    classroom_name=classroom.name,
                    course_id=course.id,
                    course_title=course.title,
                    stage_label=course.stage_label,
                )
            )
    return options


def _serialize_attendance(db: Session, session_obj: ClassSession) -> list[AttendanceRecordSummary]:
    records = db.scalars(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_obj.id).order_by(AttendanceRecord.id)
    ).all()
    presence_rows = db.scalars(select(PresenceState).where(PresenceState.session_id == session_obj.id)).all()
    presence_map = {row.user_id: row for row in presence_rows}

    results: list[AttendanceRecordSummary] = []
    for record in records:
        student = db.get(User, record.user_id)
        presence = presence_map.get(record.user_id)
        if student is None:
            continue
        results.append(
            AttendanceRecordSummary(
                id=record.id,
                student_name=student.display_name,
                student_username=student.username,
                status=record.status,
                marked_at=record.marked_at.strftime("%H:%M") if record.marked_at else None,
                note=record.note,
                last_seen_at=presence.last_seen_at.strftime("%H:%M:%S") if presence else None,
            )
        )
    return results


def _serialize_submissions(db: Session, session_obj: ClassSession) -> list[SubmissionQueueItem]:
    submissions = db.scalars(
        select(Submission).where(Submission.session_id == session_obj.id).order_by(Submission.updated_at.desc())
    ).all()
    results: list[SubmissionQueueItem] = []
    for submission in submissions:
        student = db.get(User, submission.user_id)
        if student is None:
            continue
        results.append(
            SubmissionQueueItem(
                id=submission.id,
                student_name=student.display_name,
                student_username=student.username,
                title=submission.title,
                status=submission.status,
                version=submission.version,
                draft_saved_at=submission.draft_saved_at.strftime("%H:%M") if submission.draft_saved_at else None,
                submitted_at=submission.submitted_at.strftime("%H:%M") if submission.submitted_at else None,
            )
        )
    return results


def _build_console_response(db: Session, principal: Principal, operator: User) -> TeacherConsoleResponse:
    session_obj, course, classroom = _get_current_session(db, principal, operator)
    drafts = db.scalars(
        select(AISuggestionDraft)
        .where(AISuggestionDraft.teacher_id == operator.id, AISuggestionDraft.session_id == session_obj.id)
        .order_by(AISuggestionDraft.created_at.desc())
    ).all()

    submission_items = _serialize_submissions(db, session_obj)
    submitted_count = sum(item.status != SubmissionStatus.DRAFT for item in submission_items)
    workbench_steps = [
        TodoItem(title="步骤 1 · 开课并确认课堂上下文", status="done" if session_obj.status == "active" else "pending"),
        TodoItem(
            title="步骤 2 · 完成签到与到课确认",
            status="done" if all(record.status != AttendanceStatus.PENDING for record in db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id == session_obj.id)).all()) else "active",
        ),
        TodoItem(
            title=f"步骤 3 · 收集作品提交（已收 {submitted_count} 份）",
            status="active" if submitted_count < session_obj.expected_students else "done",
        ),
    ]

    return TeacherConsoleResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        assignment_title=course.assignment_title,
        session_status=session_obj.status,
        radar=_build_radar_summary(db, session_obj),
        workbench_steps=workbench_steps,
        launch_options=_list_launch_options(db, principal.school_id),
        attendance_records=_serialize_attendance(db, session_obj),
        submissions=submission_items,
        ai_drafts=[_serialize_draft(draft) for draft in drafts],
    )


@router.get("/console", response_model=TeacherConsoleResponse)
def teacher_console(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherConsoleResponse:
    operator = _resolve_operator(db, principal)
    return _build_console_response(db, principal, operator)


@router.post("/session/start", response_model=TeacherConsoleResponse)
def start_session(
    payload: StartSessionRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherConsoleResponse:
    operator = _resolve_operator(db, principal)
    classroom = db.scalar(
        select(Classroom).where(Classroom.id == payload.classroom_id, Classroom.school_id == principal.school_id)
    )
    course = db.scalar(
        select(Course).where(Course.id == payload.course_id, Course.school_id == principal.school_id)
    )
    if classroom is None or course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom or course not found.")

    active_sessions = db.scalars(
        select(ClassSession).where(
            ClassSession.school_id == principal.school_id,
            ClassSession.classroom_id == classroom.id,
            ClassSession.status == "active",
        )
    ).all()
    for active_session in active_sessions:
        active_session.status = "completed"

    students = db.scalars(
        select(User).where(
            User.school_id == principal.school_id,
            User.classroom_id == classroom.id,
            User.role == UserRole.STUDENT,
            User.active.is_(True),
        )
    ).all()
    session_obj = ClassSession(
        school_id=principal.school_id,
        classroom_id=classroom.id,
        course_id=course.id,
        teacher_id=operator.id,
        title=course.title,
        stage=course.stage_label,
        status="active",
        expected_students=len(students),
        started_at=datetime.utcnow(),
    )
    db.add(session_obj)
    db.flush()

    for student in students:
        db.add(
            AttendanceRecord(
                school_id=principal.school_id,
                session_id=session_obj.id,
                user_id=student.id,
                status=AttendanceStatus.PENDING,
            )
        )
        db.add(
            PresenceState(
                school_id=principal.school_id,
                session_id=session_obj.id,
                user_id=student.id,
                status=PresenceStatus.NOT_STARTED,
                task_progress=0,
                help_requested=False,
                last_seen_at=datetime.utcnow(),
            )
        )

    db.commit()
    return _build_console_response(db, principal, operator)


@router.post("/attendance/{attendance_id}/mark", response_model=MessageResponse)
def mark_attendance(
    attendance_id: int,
    payload: AttendanceMarkRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    operator = _resolve_operator(db, principal)
    attendance = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.id == attendance_id,
            AttendanceRecord.school_id == principal.school_id,
        )
    )
    if attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found.")

    now = datetime.utcnow()
    attendance.status = payload.status
    attendance.note = payload.note
    attendance.marked_at = now
    attendance.marked_by_user_id = operator.id

    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == attendance.session_id,
            PresenceState.user_id == attendance.user_id,
        )
    )
    if presence:
        if payload.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
            presence.status = PresenceStatus.ACTIVE
            presence.last_seen_at = now
        elif payload.status in (AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED):
            presence.status = PresenceStatus.OFFLINE

    db.commit()
    return MessageResponse(message="Attendance updated.", updated_at=now)


@router.get("/radar/stream")
async def radar_stream(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
) -> StreamingResponse:
    async def event_generator():
        while True:
            with SessionLocal() as db:
                operator = _resolve_operator(db, principal)
                session_obj, _, _ = _get_current_session(db, principal, operator)
                radar = _build_radar_summary(db, session_obj)
            yield f"data: {json.dumps(radar.model_dump())}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/ai/drafts", response_model=CreateDraftResponse)
def create_ai_draft(
    payload: CreateDraftRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> CreateDraftResponse:
    operator = _resolve_operator(db, principal)
    session_obj, course, classroom = _get_current_session(db, principal, operator)
    draft = AISuggestionDraft(
        school_id=principal.school_id,
        teacher_id=operator.id,
        session_id=session_obj.id,
        draft_type="AI 草稿",
        title=f"{course.title} · {classroom.name} · AI 副驾建议",
        content=(
            f"目标：{payload.goal}。建议先用 8 分钟让学生完成采集，再给 5 分钟做同伴互查，"
            "最后用 3 分钟集中展示常见错误。此结果仍为草稿，需教师确认后使用。"
        ),
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return CreateDraftResponse(draft=_serialize_draft(draft))
