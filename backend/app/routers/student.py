from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.clock import utc_now
from ..core.database import get_db
from ..core.resource_storage import resolve_resource_path
from ..models import (
    ActivitySubmission,
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    CourseActivity,
    HelpRequest,
    LearningResource,
    PresenceState,
    PresenceStatus,
    ResourceCategory,
    ResourceAudience,
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
    ActivitySubmissionResponse,
    ActivitySubmissionSummary,
    HeartbeatRequest,
    HelpRequestCreate,
    MessageResponse,
    CourseActivitySummary,
    StudentResourceSummary,
    StudentActivityDetailResponse,
    StudentAssignmentsResponse,
    StudentAttendanceHistoryEntry,
    StudentAttendanceResponse,
    StudentDashboardResponse,
    StudentResourcesResponse,
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


def _format_file_size(file_size: int) -> str:
    if file_size < 1024:
        return f"{file_size} B"
    if file_size < 1024 * 1024:
        return f"{round(file_size / 1024, 1)} KB"
    return f"{round(file_size / (1024 * 1024), 1)} MB"


def _build_public_activity_launch_url(activity: CourseActivity) -> str | None:
    if not activity.interactive_launch_key or not activity.interactive_entry_file:
        return None
    return f"/api/public/activities/{activity.interactive_launch_key}/{activity.interactive_entry_file}"


def _build_public_activity_submission_url(activity: CourseActivity) -> str | None:
    if not activity.interactive_submission_key:
        return None
    return f"/api/public/activities/{activity.interactive_submission_key}/submit"


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


def _find_active_session(
    db: Session,
    school_id: int,
    classroom_id: int | None,
) -> tuple[ClassSession, Course, Classroom] | None:
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
        return None

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom


def _get_active_session(
    db: Session,
    school_id: int,
    classroom_id: int | None,
) -> tuple[ClassSession, Course, Classroom]:
    active_session = _find_active_session(db, school_id, classroom_id)
    if active_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active class session.")
    return active_session


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
            last_seen_at=utc_now(),
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


def _serialize_activity_submission(submission: ActivitySubmission) -> ActivitySubmissionSummary:
    return ActivitySubmissionSummary(
        id=submission.id,
        submitted_by_name=submission.submitted_by_name,
        submitted_at=_format_full(submission.created_at),
        payload_preview=_shorten(submission.payload_json, limit=120),
    )


def _serialize_course_activity(activity: CourseActivity, *, student_id: int | None = None) -> CourseActivitySummary:
    submissions = sorted(activity.submissions, key=lambda item: item.created_at, reverse=True)
    latest_submission = submissions[0] if submissions else None
    if student_id is not None:
        student_submissions = [item for item in submissions if item.submitted_by_user_id == student_id]
        if student_submissions:
            latest_submission = student_submissions[0]
            submissions = student_submissions

    return CourseActivitySummary(
        id=activity.id,
        title=activity.title,
        activity_type=activity.activity_type,
        position=activity.position,
        summary=activity.summary,
        instructions_html=activity.instructions_html or "",
        has_interactive_asset=bool(activity.interactive_storage_key and activity.interactive_entry_file),
        interactive_asset_name=activity.interactive_asset_name,
        interactive_launch_url=_build_public_activity_launch_url(activity),
        interactive_preview_url=_build_public_activity_launch_url(activity),
        interactive_submission_api_url=_build_public_activity_submission_url(activity),
        submission_count=len(submissions),
        last_submitted_at=_format_full(latest_submission.created_at) if latest_submission else None,
        latest_submission=_serialize_activity_submission(latest_submission) if latest_submission else None,
        recent_submissions=[_serialize_activity_submission(item) for item in submissions[:3]],
    )


def _list_course_activities(course: Course, *, student_id: int | None = None) -> list[CourseActivitySummary]:
    activities = sorted(course.activities, key=lambda item: item.position)
    return [_serialize_course_activity(activity, student_id=student_id) for activity in activities]


def _serialize_student_resource(db: Session, resource: LearningResource) -> StudentResourceSummary:
    classroom = db.get(Classroom, resource.classroom_id) if resource.classroom_id else None
    category = db.get(ResourceCategory, resource.category_id) if resource.category_id else None
    return StudentResourceSummary(
        id=resource.id,
        title=resource.title,
        description=resource.description,
        category_id=resource.category_id,
        category_name=category.name if category else None,
        classroom_name=classroom.name if classroom else None,
        original_filename=resource.original_filename,
        file_size=resource.file_size,
        file_size_label=_format_file_size(resource.file_size),
        download_count=resource.download_count,
        uploaded_at=_format_full(resource.created_at),
    )


def _list_student_resources(db: Session, principal: Principal, student: User) -> list[StudentResourceSummary]:
    resources = db.scalars(
        select(LearningResource)
        .where(
            LearningResource.school_id == principal.school_id,
            LearningResource.active.is_(True),
            LearningResource.audience.in_((ResourceAudience.STUDENT, ResourceAudience.ALL)),
        )
        .order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
    ).all()
    return [
        _serialize_student_resource(db, resource)
        for resource in resources
        if resource.classroom_id is None or resource.classroom_id == student.classroom_id
    ]


def _build_idle_home_response(db: Session, principal: Principal, student: User, classroom: Classroom | None) -> StudentHomeResponse:
    return StudentHomeResponse(
        school_name=principal.school_name,
        student_name=student.display_name,
        class_name=classroom.name if classroom else "未分班",
        lesson_title="今日暂无进行中课程",
        lesson_stage="资源中心",
        assignment_title="等待教师开课",
        assignment_prompt="当前没有进行中的课堂任务，你可以先查看老师上传的学习资料并做好下节课准备。",
        session_status="idle",
        progress_percent=0,
        progress_summary="今天暂时没有进行中的课次，保持关注教师通知，也可以先浏览资料中心里的学习资源。",
        saved_at="尚未开始",
        todo_items=[
            TodoItem(title="查看老师共享的学习资料", status="active"),
            TodoItem(title="等待教师开始新的课堂课次", status="pending"),
        ],
        highlights=[
            "当教师开始新课后，这里会自动切换到当前课堂任务页。",
            "资料中心里的资源会按学校和班级自动筛选，只展示与你相关的内容。",
        ],
        help_open=False,
        attendance_status=AttendanceStatus.PENDING,
        submission=_serialize_submission(None),
        submission_history=[],
        resources=_list_student_resources(db, principal, student),
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


def _build_attendance_history(db: Session, student: User) -> list[StudentAttendanceHistoryEntry]:
    records = db.scalars(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.school_id == student.school_id,
            AttendanceRecord.user_id == student.id,
        )
        .order_by(AttendanceRecord.created_at.desc(), AttendanceRecord.id.desc())
    ).all()
    history: list[StudentAttendanceHistoryEntry] = []
    for record in records[:8]:
        session_obj = db.get(ClassSession, record.session_id)
        classroom = db.get(Classroom, session_obj.classroom_id) if session_obj else None
        history.append(
            StudentAttendanceHistoryEntry(
                session_id=record.session_id,
                lesson_title=session_obj.title if session_obj else "Archived lesson",
                class_name=classroom.name if classroom else "Unknown classroom",
                status=record.status,
                marked_at=_format_hm(record.marked_at),
                started_at=_format_full(session_obj.started_at) if session_obj else _format_full(record.created_at),
            )
        )
    return history


def _get_course_activity(
    db: Session,
    principal: Principal,
    activity_id: int,
) -> CourseActivity:
    activity = db.scalar(
        select(CourseActivity).where(
            CourseActivity.id == activity_id,
            CourseActivity.school_id == principal.school_id,
        )
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course activity not found.")
    return activity


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
            created_at=utc_now(),
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
    now = utc_now()
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


def _build_student_home_response(db: Session, principal: Principal, student: User) -> StudentHomeResponse:
    classroom = db.get(Classroom, student.classroom_id) if student.classroom_id else None
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    if active_session is None:
        return _build_idle_home_response(db, principal, student, classroom)

    session_obj, course, classroom = active_session
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
        TodoItem(title="阅读本节任务说明", status="done"),
        TodoItem(title="完成课堂作品草稿", status="done" if submission else "active"),
        TodoItem(
            title="正式提交课堂作品",
            status="done" if submission and submission.status != SubmissionStatus.DRAFT else "pending",
        ),
    ]
    if submission and submission.status == SubmissionStatus.REVIEWED and _can_edit_reviewed_submission(submission):
        todo_items.append(TodoItem(title="根据教师反馈修改后重交", status="active"))

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
            "老师批改后，你可以在同一门户查看反馈和提交历史。",
            "如果卡住了，可以随时举手求助，教师端会实时收到提醒。",
        ],
        help_open=presence.help_requested,
        attendance_status=attendance.status,
        submission=_serialize_submission(submission, reviewer_name),
        submission_history=_build_submission_history(db, submission),
        resources=_list_student_resources(db, principal, student),
    )


def _build_student_dashboard_response(db: Session, principal: Principal, student: User) -> StudentDashboardResponse:
    home = _build_student_home_response(db, principal, student)
    return StudentDashboardResponse(
        school_name=home.school_name,
        student_name=home.student_name,
        class_name=home.class_name,
        lesson_title=home.lesson_title,
        lesson_stage=home.lesson_stage,
        session_status=home.session_status,
        progress_percent=home.progress_percent,
        progress_summary=home.progress_summary,
        todo_items=home.todo_items,
        highlights=home.highlights,
        help_open=home.help_open,
        attendance_status=home.attendance_status,
    )


def _build_student_attendance_response(db: Session, principal: Principal, student: User) -> StudentAttendanceResponse:
    classroom = db.get(Classroom, student.classroom_id) if student.classroom_id else None
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    history = _build_attendance_history(db, student)
    if active_session is None:
        return StudentAttendanceResponse(
            session_id=None,
            school_name=principal.school_name,
            student_name=student.display_name,
            class_name=classroom.name if classroom else "未分班",
            lesson_title="当前暂无进行中的课堂",
            session_status="idle",
            attendance_status=AttendanceStatus.PENDING,
            checked_in_at=None,
            last_seen_at=None,
            can_check_in=False,
            help_open=False,
            attendance_history=history,
        )

    session_obj, course, classroom = active_session
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)
    attendance = _get_or_create_attendance(db, principal, session_obj.id, student.id)
    return StudentAttendanceResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        student_name=student.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        session_status=session_obj.status,
        attendance_status=attendance.status,
        checked_in_at=_format_hm(attendance.marked_at),
        last_seen_at=_format_full(presence.last_seen_at),
        can_check_in=attendance.status == AttendanceStatus.PENDING,
        help_open=presence.help_requested,
        attendance_history=history,
    )


def _build_student_assignments_response(db: Session, principal: Principal, student: User) -> StudentAssignmentsResponse:
    home = _build_student_home_response(db, principal, student)
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    activities: list[CourseActivitySummary] = []
    session_id: int | None = None
    if active_session is not None:
        session_obj, course, _ = active_session
        session_id = session_obj.id
        activities = _list_course_activities(course, student_id=student.id)

    return StudentAssignmentsResponse(
        session_id=session_id,
        school_name=home.school_name,
        student_name=home.student_name,
        class_name=home.class_name,
        lesson_title=home.lesson_title,
        lesson_stage=home.lesson_stage,
        assignment_title=home.assignment_title,
        assignment_prompt=home.assignment_prompt,
        session_status=home.session_status,
        submission=home.submission,
        submission_history=home.submission_history,
        activities=activities,
    )


def _build_student_activity_detail_response(
    db: Session,
    principal: Principal,
    student: User,
    activity: CourseActivity,
) -> StudentActivityDetailResponse:
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    if active_session is None or active_session[1].id != activity.course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity is not available in the current context.")

    session_obj, course, classroom = active_session
    return StudentActivityDetailResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        student_name=student.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        session_status=session_obj.status,
        activity=_serialize_course_activity(activity, student_id=student.id),
    )


@router.get("/home", response_model=StudentHomeResponse)
def student_home(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentHomeResponse:
    student = _get_student(db, principal)
    return _build_student_home_response(db, principal, student)
    classroom = db.get(Classroom, student.classroom_id) if student.classroom_id else None
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    if active_session is None:
        return _build_idle_home_response(db, principal, student, classroom)

    session_obj, course, classroom = active_session
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
        resources=_list_student_resources(db, principal, student),
    )


@router.get("/dashboard", response_model=StudentDashboardResponse)
def student_dashboard(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentDashboardResponse:
    student = _get_student(db, principal)
    return _build_student_dashboard_response(db, principal, student)


@router.get("/attendance", response_model=StudentAttendanceResponse)
def student_attendance(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentAttendanceResponse:
    student = _get_student(db, principal)
    return _build_student_attendance_response(db, principal, student)


@router.post("/attendance/check-in", response_model=MessageResponse)
def student_check_in(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    student = _get_student(db, principal)
    session_obj, _, _ = _get_active_session(db, principal.school_id, student.classroom_id)
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)
    attendance = _get_or_create_attendance(db, principal, session_obj.id, student.id)

    now = utc_now()
    presence.status = PresenceStatus.ACTIVE
    presence.last_seen_at = now
    presence.task_progress = max(presence.task_progress, 10)
    attendance.status = AttendanceStatus.PRESENT
    attendance.marked_at = now
    db.commit()
    return MessageResponse(message="Check-in completed.", updated_at=now)


@router.get("/assignments", response_model=StudentAssignmentsResponse)
def student_assignments(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentAssignmentsResponse:
    student = _get_student(db, principal)
    return _build_student_assignments_response(db, principal, student)


@router.get("/activities/{activity_id}", response_model=StudentActivityDetailResponse)
def student_activity_detail(
    activity_id: int,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentActivityDetailResponse:
    student = _get_student(db, principal)
    activity = _get_course_activity(db, principal, activity_id)
    return _build_student_activity_detail_response(db, principal, student, activity)


@router.post("/activities/{activity_id}/submissions", response_model=ActivitySubmissionResponse)
def student_activity_submission(
    activity_id: int,
    payload: Any = Body(default={}),
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> ActivitySubmissionResponse:
    student = _get_student(db, principal)
    activity = _get_course_activity(db, principal, activity_id)
    active_session = _find_active_session(db, principal.school_id, student.classroom_id)
    if active_session is None or active_session[1].id != activity.course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive activity is not active for the current student.")

    session_obj, _, _ = active_session
    presence = _get_or_create_presence(db, principal, session_obj.id, student.id)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    now = utc_now()
    submission = ActivitySubmission(
        school_id=principal.school_id,
        course_id=activity.course_id,
        activity_id=activity.id,
        session_id=session_obj.id,
        submitted_by_user_id=student.id,
        submitted_by_name=student.display_name,
        payload_json=payload_json,
        created_at=now,
        updated_at=now,
    )
    db.add(submission)

    presence.status = PresenceStatus.ACTIVE
    presence.last_seen_at = now
    presence.task_progress = max(presence.task_progress, 96)
    db.commit()
    db.refresh(submission)
    return ActivitySubmissionResponse(
        message="Interactive activity submission received.",
        submission=_serialize_activity_submission(submission),
        updated_at=now,
    )


@router.get("/resources", response_model=StudentResourcesResponse)
def student_resources(
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> StudentResourcesResponse:
    student = _get_student(db, principal)
    return StudentResourcesResponse(
        school_name=principal.school_name,
        student_name=student.display_name,
        resources=_list_student_resources(db, principal, student),
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

    now = utc_now()
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

    now = utc_now()
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
    updated_at = submission.draft_saved_at or utc_now()
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
    updated_at = submission.submitted_at or utc_now()
    return SubmissionActionResponse(
        message="Submission completed.",
        submission=_serialize_submission(submission, reviewer_name),
        updated_at=updated_at,
    )


@router.get("/resources/{resource_id}/download")
def download_student_resource(
    resource_id: int,
    principal: Principal = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> FileResponse:
    student = _get_student(db, principal)
    resource = db.scalar(
        select(LearningResource).where(
            LearningResource.id == resource_id,
            LearningResource.school_id == principal.school_id,
            LearningResource.active.is_(True),
            LearningResource.audience.in_((ResourceAudience.STUDENT, ResourceAudience.ALL)),
        )
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    if resource.classroom_id is not None and resource.classroom_id != student.classroom_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current student cannot access this resource.")

    file_path = resolve_resource_path(resource.storage_key)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored resource file is missing.")

    resource.download_count += 1
    db.commit()
    return FileResponse(
        path=file_path,
        filename=resource.original_filename,
        media_type=resource.content_type or "application/octet-stream",
    )
