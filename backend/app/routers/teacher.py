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
    AttendanceMarkRequest,
    AttendanceRecordSummary,
    CreateDraftRequest,
    CreateDraftResponse,
    MessageResponse,
    RadarSummary,
    StartSessionRequest,
    SubmissionHistoryEntry,
    SubmissionQueueItem,
    SubmissionReviewRequest,
    SubmissionReviewSummary,
    TeacherConsoleResponse,
    TeacherDraft,
    TeacherHelpRequestSummary,
    TeacherLaunchOption,
    TeacherSubmissionDetail,
    TodoItem,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])

ALLOWED_ROLES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)


def _format_hm(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _format_hms(value: datetime | None) -> str | None:
    return value.strftime("%H:%M:%S") if value else None


def _format_full(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _shorten(text: str, *, limit: int = 96) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}…"


def _decision_label(decision: ReviewDecision) -> str:
    labels = {
        ReviewDecision.APPROVED: "已通过",
        ReviewDecision.REVISION_REQUESTED: "需要修改后重交",
        ReviewDecision.REJECTED: "暂不通过",
    }
    return labels[decision]


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


def _get_submission(
    db: Session,
    principal: Principal,
    submission_id: int,
) -> Submission:
    submission = db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.school_id == principal.school_id,
        )
    )
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    return submission


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
        created_at=_format_full(draft.created_at),
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
                marked_at=_format_hm(record.marked_at),
                note=record.note,
                last_seen_at=_format_hms(presence.last_seen_at) if presence else None,
            )
        )
    return results


def _serialize_help_requests(db: Session, session_obj: ClassSession) -> list[TeacherHelpRequestSummary]:
    help_requests = db.scalars(
        select(HelpRequest)
        .where(HelpRequest.session_id == session_obj.id)
        .order_by(HelpRequest.status.asc(), HelpRequest.created_at.desc())
    ).all()
    results: list[TeacherHelpRequestSummary] = []
    for request in help_requests:
        student = db.get(User, request.user_id)
        if student is None:
            continue
        results.append(
            TeacherHelpRequestSummary(
                id=request.id,
                student_name=student.display_name,
                student_username=student.username,
                message=request.message,
                created_at=_format_full(request.created_at),
                status=request.status,
            )
        )
    return results


def _serialize_submissions(db: Session, session_obj: ClassSession) -> list[SubmissionQueueItem]:
    submissions = db.scalars(
        select(Submission).where(Submission.session_id == session_obj.id).order_by(Submission.updated_at.desc())
    ).all()
    presence_rows = db.scalars(select(PresenceState).where(PresenceState.session_id == session_obj.id)).all()
    presence_map = {row.user_id: row for row in presence_rows}

    results: list[SubmissionQueueItem] = []
    for submission in submissions:
        student = db.get(User, submission.user_id)
        presence = presence_map.get(submission.user_id)
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
                draft_saved_at=_format_hm(submission.draft_saved_at),
                submitted_at=_format_hm(submission.submitted_at),
                help_requested=presence.help_requested if presence else False,
                review_decision=submission.review_decision,
                reviewed_at=_format_hm(submission.reviewed_at),
            )
        )
    return results


def _build_submission_history(db: Session, submission: Submission) -> list[SubmissionHistoryEntry]:
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


def _serialize_review(db: Session, review: SubmissionReview) -> SubmissionReviewSummary:
    reviewer = db.get(User, review.reviewer_user_id)
    return SubmissionReviewSummary(
        id=review.id,
        reviewer_name=reviewer.display_name if reviewer else "教师",
        decision=review.decision,
        feedback=review.feedback,
        created_at=_format_full(review.created_at),
    )


def _serialize_submission_detail(db: Session, submission: Submission) -> TeacherSubmissionDetail:
    student = db.get(User, submission.user_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == submission.session_id,
            PresenceState.user_id == submission.user_id,
        )
    )
    help_messages = db.scalars(
        select(HelpRequest)
        .where(
            HelpRequest.session_id == submission.session_id,
            HelpRequest.user_id == submission.user_id,
        )
        .order_by(HelpRequest.created_at.desc())
    ).all()
    reviews = db.scalars(
        select(SubmissionReview)
        .where(SubmissionReview.submission_id == submission.id)
        .order_by(SubmissionReview.created_at.desc(), SubmissionReview.id.desc())
    ).all()

    return TeacherSubmissionDetail(
        id=submission.id,
        student_name=student.display_name,
        student_username=student.username,
        title=submission.title,
        content=submission.content,
        status=submission.status,
        version=submission.version,
        draft_saved_at=_format_hm(submission.draft_saved_at),
        submitted_at=_format_hm(submission.submitted_at),
        teacher_feedback=submission.teacher_feedback,
        review_decision=submission.review_decision,
        reviewed_at=_format_hm(submission.reviewed_at),
        help_requested=presence.help_requested if presence else False,
        help_messages=[
            TeacherHelpRequestSummary(
                id=item.id,
                student_name=student.display_name,
                student_username=student.username,
                message=item.message,
                created_at=_format_full(item.created_at),
                status=item.status,
            )
            for item in help_messages
        ],
        history=_build_submission_history(db, submission),
        reviews=[_serialize_review(db, review) for review in reviews],
    )


def _build_console_response(db: Session, principal: Principal, operator: User) -> TeacherConsoleResponse:
    session_obj, course, classroom = _get_current_session(db, principal, operator)
    drafts = db.scalars(
        select(AISuggestionDraft)
        .where(AISuggestionDraft.teacher_id == operator.id, AISuggestionDraft.session_id == session_obj.id)
        .order_by(AISuggestionDraft.created_at.desc())
    ).all()

    submission_items = _serialize_submissions(db, session_obj)
    help_requests = _serialize_help_requests(db, session_obj)
    review_ready_count = sum(item.status != SubmissionStatus.DRAFT for item in submission_items)
    workbench_steps = [
        TodoItem(title="开课并确认课堂上下文", status="done" if session_obj.status == "active" else "pending"),
        TodoItem(
            title="完成签到与在线状态核验",
            status=(
                "done"
                if all(
                    record.status != AttendanceStatus.PENDING
                    for record in db.scalars(
                        select(AttendanceRecord).where(AttendanceRecord.session_id == session_obj.id)
                    ).all()
                )
                else "active"
            ),
        ),
        TodoItem(
            title=f"处理提交与批改任务（当前 {review_ready_count} 份）",
            status="done" if review_ready_count >= session_obj.expected_students and review_ready_count > 0 else "active",
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
        help_requests=help_requests,
        submissions=submission_items,
        ai_drafts=[_serialize_draft(draft) for draft in drafts],
    )


def _resolve_help_requests(db: Session, submission: Submission) -> None:
    help_requests = db.scalars(
        select(HelpRequest).where(
            HelpRequest.session_id == submission.session_id,
            HelpRequest.user_id == submission.user_id,
            HelpRequest.status == "open",
        )
    ).all()
    for request in help_requests:
        request.status = "closed"

    presence = db.scalar(
        select(PresenceState).where(
            PresenceState.session_id == submission.session_id,
            PresenceState.user_id == submission.user_id,
        )
    )
    if presence is not None:
        presence.help_requested = False


@router.get("/console", response_model=TeacherConsoleResponse)
def teacher_console(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherConsoleResponse:
    operator = _resolve_operator(db, principal)
    return _build_console_response(db, principal, operator)


@router.get("/submissions/{submission_id}", response_model=TeacherSubmissionDetail)
def teacher_submission_detail(
    submission_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherSubmissionDetail:
    _resolve_operator(db, principal)
    submission = _get_submission(db, principal, submission_id)
    return _serialize_submission_detail(db, submission)


@router.post("/submissions/{submission_id}/review", response_model=TeacherSubmissionDetail)
def review_submission(
    submission_id: int,
    payload: SubmissionReviewRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherSubmissionDetail:
    operator = _resolve_operator(db, principal)
    submission = _get_submission(db, principal, submission_id)
    if submission.status == SubmissionStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft submission cannot be reviewed yet.")

    now = datetime.utcnow()
    submission.status = SubmissionStatus.REVIEWED
    submission.teacher_feedback = payload.feedback
    submission.review_decision = payload.decision
    submission.reviewed_at = now
    submission.reviewed_by_user_id = operator.id
    db.add(
        SubmissionReview(
            submission_id=submission.id,
            school_id=submission.school_id,
            session_id=submission.session_id,
            reviewer_user_id=operator.id,
            decision=payload.decision,
            feedback=payload.feedback,
        )
    )
    if payload.resolve_help_requests:
        _resolve_help_requests(db, submission)

    db.commit()
    db.refresh(submission)
    return _serialize_submission_detail(db, submission)


@router.post("/submissions/{submission_id}/feedback-draft", response_model=CreateDraftResponse)
def create_feedback_draft(
    submission_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> CreateDraftResponse:
    operator = _resolve_operator(db, principal)
    submission = _get_submission(db, principal, submission_id)
    if submission.status == SubmissionStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft submission cannot generate feedback.")

    student = db.get(User, submission.user_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    latest_help = db.scalar(
        select(HelpRequest)
        .where(
            HelpRequest.session_id == submission.session_id,
            HelpRequest.user_id == submission.user_id,
        )
        .order_by(HelpRequest.created_at.desc())
    )
    help_hint = f"学生求助：{latest_help.message}" if latest_help else "当前没有新的求助记录。"
    draft_content = (
        f"优点：{student.display_name} 已经完成《{submission.title}》的主体表达，内容结构基本完整。\n"
        f"建议：重点补强图表结论的依据，并把“为什么得出这个判断”写得更具体。\n"
        f"下一步：先补 1 条数据观察，再补 1 条课堂结论后重新提交。\n"
        f"{help_hint}"
    )
    draft = AISuggestionDraft(
        school_id=principal.school_id,
        teacher_id=operator.id,
        session_id=submission.session_id,
        draft_type="作业反馈草稿",
        title=f"{student.display_name} · {submission.title} · 批改建议",
        content=draft_content,
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return CreateDraftResponse(draft=_serialize_draft(draft))


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
        draft_type="课堂建议草稿",
        title=f"{course.title} · {classroom.name} · AI 副驾建议",
        content=(
            f"目标：{payload.goal}。建议先用 8 分钟做采集，再用 5 分钟做同伴互查，"
            "最后用 3 分钟集中展示典型问题。此输出仍为草稿，需教师确认后再使用。"
        ),
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return CreateDraftResponse(draft=_serialize_draft(draft))
