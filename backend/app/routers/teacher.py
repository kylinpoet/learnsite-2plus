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
from ..models import AISuggestionDraft, ClassSession, Classroom, Course, PresenceState, PresenceStatus, User, UserRole
from ..schemas import CreateDraftRequest, CreateDraftResponse, RadarSummary, TeacherConsoleResponse, TeacherDraft, TodoItem

router = APIRouter(prefix="/teacher", tags=["teacher"])


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


def _get_current_session(db: Session, principal: Principal) -> tuple[ClassSession, Course, Classroom, User]:
    operator = _resolve_operator(db, principal)

    query = select(ClassSession).where(ClassSession.school_id == principal.school_id)
    if principal.role == UserRole.TEACHER:
        query = query.where(ClassSession.teacher_id == operator.id)

    session_obj = db.scalar(query.order_by(ClassSession.started_at.desc()))
    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active teaching session.")

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom, operator


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


@router.get("/console", response_model=TeacherConsoleResponse)
def teacher_console(
    principal: Principal = Depends(
        require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TeacherConsoleResponse:
    session_obj, course, classroom, operator = _get_current_session(db, principal)
    radar = _build_radar_summary(db, session_obj)
    drafts = db.scalars(
        select(AISuggestionDraft)
        .where(AISuggestionDraft.teacher_id == operator.id, AISuggestionDraft.session_id == session_obj.id)
        .order_by(AISuggestionDraft.created_at.desc())
    ).all()

    return TeacherConsoleResponse(
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        session_status=session_obj.status,
        radar=radar,
        workbench_steps=[
            TodoItem(title="步骤 1 · 导学说明", status="done"),
            TodoItem(title="步骤 2 · 数据采集", status="active"),
            TodoItem(title="步骤 3 · 作品提交", status="pending"),
        ],
        ai_drafts=[_serialize_draft(draft) for draft in drafts],
    )


@router.get("/radar/stream")
async def radar_stream(
    principal: Principal = Depends(
        require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)
    )
) -> StreamingResponse:
    async def event_generator():
        while True:
            with SessionLocal() as db:
                session_obj, _, _, _ = _get_current_session(db, principal)
                radar = _build_radar_summary(db, session_obj)
            yield f"data: {json.dumps(radar.model_dump())}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/ai/drafts", response_model=CreateDraftResponse)
def create_ai_draft(
    payload: CreateDraftRequest,
    principal: Principal = Depends(
        require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)
    ),
    db: Session = Depends(get_db),
) -> CreateDraftResponse:
    session_obj, course, classroom, operator = _get_current_session(db, principal)
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
