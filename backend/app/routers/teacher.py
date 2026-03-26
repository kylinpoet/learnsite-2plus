from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.auth import Principal, require_roles
from ..core.clock import utc_now
from ..core.database import SessionLocal, get_db
from ..core.resource_storage import (
    resolve_resource_path,
    save_uploaded_interactive_package,
    save_uploaded_resource,
)
from ..models import (
    ActivitySubmission,
    AISuggestionDraft,
    AuditLog,
    AuditLogLevel,
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    CourseActivity,
    CourseActivityType,
    HelpRequest,
    LearningResource,
    PresenceState,
    PresenceStatus,
    ResourceCategory,
    ResourceAudience,
    ReviewDecision,
    SessionReflection,
    Submission,
    SubmissionRevision,
    SubmissionRevisionAction,
    SubmissionReview,
    SubmissionStatus,
    TeacherClassroomAssignment,
    User,
    UserRole,
)
from ..schemas import (
    ActivitySubmissionSummary,
    AttendanceMarkRequest,
    AttendanceRecordSummary,
    CourseActivitySummary,
    CreateDraftRequest,
    CreateDraftResponse,
    MessageResponse,
    RadarSummary,
    TeacherAttendanceResponse,
    TeacherCopilotResponse,
    TeacherCourseCollectionResponse,
    TeacherCourseDetailResponse,
    TeacherCourseSaveRequest,
    TeacherCourseSummary,
    TeacherDashboardResponse,
    StartSessionRequest,
    SubmissionHistoryEntry,
    SubmissionQueueItem,
    SubmissionReviewRequest,
    SubmissionReviewSummary,
    TeacherAnalyticsAttentionStudent,
    TeacherClassroomSummary,
    TeacherConsoleResponse,
    TeacherDraft,
    TeacherDraftUpdateRequest,
    TeacherHelpRequestSummary,
    TeacherLaunchOption,
    ResourceCategorySummary,
    TeacherResourceStatusRequest,
    TeacherResourceSummary,
    TeacherReflectionDraftResponse,
    TeacherReflectionRequest,
    TeacherReflectionSummary,
    TeacherResourcesResponse,
    TeacherSessionAnalytics,
    TeacherStudentRosterEntry,
    TeacherSubmissionsResponse,
    TeacherSubmissionDetail,
    TodoItem,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])

ALLOWED_ROLES = (UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN)
AI_DRAFT_PROVIDER = "learnsite-local-copilot"
AI_DRAFT_MODEL = "learnsite-local-copilot-v1"


def _format_hm(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _format_hms(value: datetime | None) -> str | None:
    return value.strftime("%H:%M:%S") if value else None


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


def _safe_percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


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


def _append_teacher_audit_log(
    db: Session,
    principal: Principal,
    *,
    action: str,
    target_label: str,
    summary: str,
    detail: str | None = None,
    target_id: str | None = None,
    level: AuditLogLevel = AuditLogLevel.INFO,
) -> None:
    db.add(
        AuditLog(
            school_id=principal.school_id,
            actor_user_id=principal.user_id,
            actor_username=principal.username,
            actor_display_name=principal.display_name,
            actor_role=principal.role,
            action=action,
            target_type="ai_draft",
            target_id=target_id,
            target_label=target_label,
            level=level,
            summary=summary,
            detail=detail,
        )
    )


def _build_ai_draft_audit_detail(draft: AISuggestionDraft, extra: str | None = None) -> str:
    parts = [
        f"provider={AI_DRAFT_PROVIDER}",
        f"model={AI_DRAFT_MODEL}",
        f"session_id={draft.session_id}",
        f"draft_type={draft.draft_type}",
    ]
    if extra:
        parts.append(extra)
    return "; ".join(parts)


def _get_accessible_classroom_ids(db: Session, principal: Principal, operator: User) -> list[int]:
    if principal.role != UserRole.TEACHER:
        return list(
            db.scalars(select(Classroom.id).where(Classroom.school_id == principal.school_id).order_by(Classroom.id)).all()
        )

    return list(
        db.scalars(
            select(TeacherClassroomAssignment.classroom_id)
            .where(
                TeacherClassroomAssignment.school_id == principal.school_id,
                TeacherClassroomAssignment.teacher_user_id == operator.id,
            )
            .order_by(TeacherClassroomAssignment.classroom_id)
        ).all()
    )


def _list_managed_classrooms(db: Session, principal: Principal, accessible_classroom_ids: list[int]) -> list[TeacherClassroomSummary]:
    query = select(Classroom).where(Classroom.school_id == principal.school_id)
    if principal.role == UserRole.TEACHER:
        if not accessible_classroom_ids:
            return []
        query = query.where(Classroom.id.in_(accessible_classroom_ids))
    classrooms = db.scalars(query.order_by(Classroom.grade_label, Classroom.name, Classroom.id)).all()
    return [
        TeacherClassroomSummary(
            id=classroom.id,
            name=classroom.name,
            grade_label=classroom.grade_label,
        )
        for classroom in classrooms
    ]


def _find_current_session(
    db: Session,
    principal: Principal,
    operator: User,
) -> tuple[ClassSession, Course, Classroom] | None:
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
        return None

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    return session_obj, course, classroom


def _get_current_session(db: Session, principal: Principal, operator: User) -> tuple[ClassSession, Course, Classroom]:
    current_session = _find_current_session(db, principal, operator)
    if current_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No teaching session found.")
    return current_session


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


def _get_course(db: Session, principal: Principal, course_id: int) -> Course:
    course = db.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.school_id == principal.school_id,
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return course


def _get_course_activity(db: Session, principal: Principal, activity_id: int) -> CourseActivity:
    activity = db.scalar(
        select(CourseActivity).where(
            CourseActivity.id == activity_id,
            CourseActivity.school_id == principal.school_id,
        )
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course activity not found.")
    return activity


def _get_classroom(db: Session, principal: Principal, classroom_id: int) -> Classroom:
    classroom = db.scalar(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.school_id == principal.school_id,
        )
    )
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found.")
    return classroom


def _get_class_session(db: Session, principal: Principal, session_id: int) -> ClassSession:
    session_obj = db.scalar(
        select(ClassSession).where(
            ClassSession.id == session_id,
            ClassSession.school_id == principal.school_id,
        )
    )
    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class session not found.")
    return session_obj


def _default_course_activity_payload(course: Course) -> CourseActivity:
    return CourseActivity(
        school_id=course.school_id,
        course_id=course.id,
        title=course.assignment_title,
        activity_type=CourseActivityType.RICH_TEXT,
        position=1,
        summary="Default activity generated from the assignment prompt.",
        instructions_html=course.assignment_prompt,
    )


def _resequence_course_activities(db: Session, ordered_activities: list[CourseActivity]) -> None:
    if not ordered_activities:
        return

    temporary_base = 1000 + len(ordered_activities)
    for offset, activity in enumerate(ordered_activities, start=1):
        activity.position = temporary_base + offset
    db.flush()

    for position, activity in enumerate(ordered_activities, start=1):
        activity.position = position
    db.flush()


def _sync_course_activities(db: Session, course: Course, payload: TeacherCourseSaveRequest) -> None:
    payload_items = payload.activities or []
    if not payload_items:
        if course.activities:
            _resequence_course_activities(db, sorted(course.activities, key=lambda item: item.position))
            return
        default_activity = _default_course_activity_payload(course)
        default_activity.interactive_launch_key = None
        default_activity.interactive_submission_key = None
        db.add(default_activity)
        db.flush()
        return

    existing_by_id = {activity.id: activity for activity in course.activities}
    requested_existing_ids: set[int] = set()
    ordered_activities: list[CourseActivity] = []
    temporary_base = 1000 + len(existing_by_id) + len(payload_items)

    for offset, activity_payload in enumerate(payload_items, start=1):
        activity = None
        if activity_payload.id is not None:
            if activity_payload.id in requested_existing_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Course activity {activity_payload.id} is duplicated in the payload.",
                )
            activity = existing_by_id.get(activity_payload.id)
            if activity is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Course activity {activity_payload.id} not found for this course.",
                )
            requested_existing_ids.add(activity_payload.id)
        else:
            activity = CourseActivity(
                school_id=course.school_id,
                course_id=course.id,
                activity_type=activity_payload.activity_type,
            )
            db.add(activity)

        activity.title = activity_payload.title.strip()
        activity.activity_type = activity_payload.activity_type
        activity.position = temporary_base + offset
        activity.summary = activity_payload.summary.strip() if activity_payload.summary else None
        activity.instructions_html = activity_payload.instructions_html.strip()

        if activity.activity_type == CourseActivityType.INTERACTIVE_PAGE:
            activity.interactive_launch_key = activity.interactive_launch_key or secrets.token_urlsafe(18)
            activity.interactive_submission_key = activity.interactive_submission_key or secrets.token_urlsafe(24)
        else:
            activity.interactive_storage_key = None
            activity.interactive_entry_file = None
            activity.interactive_asset_name = None
            activity.interactive_launch_key = None
            activity.interactive_submission_key = None

        ordered_activities.append(activity)

    for activity in existing_by_id.values():
        if activity.id not in requested_existing_ids:
            db.delete(activity)

    db.flush()

    for position, activity in enumerate(ordered_activities, start=1):
        activity.position = position

    db.flush()


def _ensure_teacher_session_access(db: Session, principal: Principal, operator: User, session_id: int) -> None:
    if principal.role != UserRole.TEACHER:
        return
    owned_session = db.scalar(
        select(ClassSession.id).where(
            ClassSession.id == session_id,
            ClassSession.school_id == principal.school_id,
            ClassSession.teacher_id == operator.id,
        )
    )
    if owned_session is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current teacher cannot access another classroom session.",
        )


def _ensure_teacher_submission_access(db: Session, principal: Principal, operator: User, submission: Submission) -> None:
    _ensure_teacher_session_access(db, principal, operator, submission.session_id)


def _get_ai_draft(
    db: Session,
    principal: Principal,
    operator: User,
    draft_id: int,
) -> AISuggestionDraft:
    draft = db.scalar(
        select(AISuggestionDraft).where(
            AISuggestionDraft.id == draft_id,
            AISuggestionDraft.school_id == principal.school_id,
            AISuggestionDraft.teacher_id == operator.id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI draft not found.")
    _ensure_teacher_session_access(db, principal, operator, draft.session_id)
    return draft


def _ensure_draft_editable(draft: AISuggestionDraft) -> None:
    if draft.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only drafts in draft status can still be changed.",
        )


def _normalize_teacher_draft_update(payload: TeacherDraftUpdateRequest) -> tuple[str, str]:
    title = payload.title.strip()
    content = payload.content.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Draft title is required.")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Draft content is required.")
    return title, content


def _build_radar_summary(db: Session, session_obj: ClassSession) -> RadarSummary:
    rows = db.scalars(select(PresenceState).where(PresenceState.session_id == session_obj.id)).all()
    now = utc_now()
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
        updated_at=_format_full(draft.updated_at) if draft.updated_at else None,
        status=draft.status,
    )


def _serialize_course(course: Course) -> TeacherCourseSummary:
    return TeacherCourseSummary(
        id=course.id,
        title=course.title,
        stage_label=course.stage_label,
        overview=course.overview,
        assignment_title=course.assignment_title,
        assignment_prompt=course.assignment_prompt,
        activity_count=len(course.activities),
        is_published=course.is_published,
        published_at=_format_full(course.published_at) if course.published_at else None,
    )


def _serialize_activity_submission(submission: ActivitySubmission) -> ActivitySubmissionSummary:
    return ActivitySubmissionSummary(
        id=submission.id,
        submitted_by_name=submission.submitted_by_name,
        submitted_at=_format_full(submission.created_at),
        payload_preview=_shorten(submission.payload_json, limit=140),
    )


def _serialize_course_activity(activity: CourseActivity) -> CourseActivitySummary:
    recent_submissions = sorted(activity.submissions, key=lambda item: item.created_at, reverse=True)
    latest_submission = recent_submissions[0] if recent_submissions else None

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
        submission_count=len(recent_submissions),
        last_submitted_at=_format_full(latest_submission.created_at) if latest_submission else None,
        latest_submission=_serialize_activity_submission(latest_submission) if latest_submission else None,
        recent_submissions=[_serialize_activity_submission(item) for item in recent_submissions[:5]],
    )


def _serialize_course_detail(course: Course) -> TeacherCourseDetailResponse:
    activities = sorted(course.activities, key=lambda item: item.position)
    return TeacherCourseDetailResponse(
        course=_serialize_course(course),
        activities=[_serialize_course_activity(activity) for activity in activities],
    )


def _serialize_reflection(reflection: SessionReflection | None) -> TeacherReflectionSummary:
    if reflection is None:
        return TeacherReflectionSummary()
    return TeacherReflectionSummary(
        id=reflection.id,
        strengths=reflection.strengths,
        risks=reflection.risks,
        next_actions=reflection.next_actions,
        student_support_plan=reflection.student_support_plan,
        ai_draft_content=reflection.ai_draft_content,
        updated_at=_format_full(reflection.updated_at),
    )


def _get_session_reflection(db: Session, session_id: int, teacher_id: int) -> SessionReflection | None:
    return db.scalar(
        select(SessionReflection).where(
            SessionReflection.session_id == session_id,
            SessionReflection.teacher_id == teacher_id,
        )
    )


def _list_launch_options(db: Session, school_id: int, accessible_classroom_ids: list[int]) -> list[TeacherLaunchOption]:
    if not accessible_classroom_ids:
        return []
    classrooms = db.scalars(
        select(Classroom)
        .where(
            Classroom.school_id == school_id,
            Classroom.id.in_(accessible_classroom_ids),
        )
        .order_by(Classroom.id)
    ).all()
    courses = db.scalars(
        select(Course).where(Course.school_id == school_id, Course.is_published.is_(True)).order_by(Course.id)
    ).all()
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


def _list_courses(db: Session, school_id: int) -> list[TeacherCourseSummary]:
    courses = db.scalars(select(Course).where(Course.school_id == school_id).order_by(Course.updated_at.desc())).all()
    return [_serialize_course(course) for course in courses]


def _serialize_resource_category(category: ResourceCategory) -> ResourceCategorySummary:
    return ResourceCategorySummary(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        active=category.active,
    )


def _list_resource_categories(db: Session, school_id: int, *, active_only: bool = False) -> list[ResourceCategorySummary]:
    query = select(ResourceCategory).where(ResourceCategory.school_id == school_id)
    if active_only:
        query = query.where(ResourceCategory.active.is_(True))
    categories = db.scalars(query.order_by(ResourceCategory.sort_order, ResourceCategory.id)).all()
    return [_serialize_resource_category(category) for category in categories]


def _get_resource_category(
    db: Session,
    principal: Principal,
    category_id: int,
    *,
    active_only: bool = False,
) -> ResourceCategory:
    query = select(ResourceCategory).where(
        ResourceCategory.id == category_id,
        ResourceCategory.school_id == principal.school_id,
    )
    if active_only:
        query = query.where(ResourceCategory.active.is_(True))
    category = db.scalar(query)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource category not found.")
    return category


def _get_default_resource_category_id(db: Session, principal: Principal) -> int | None:
    category = db.scalar(
        select(ResourceCategory)
        .where(
            ResourceCategory.school_id == principal.school_id,
            ResourceCategory.active.is_(True),
        )
        .order_by(ResourceCategory.sort_order, ResourceCategory.id)
    )
    return category.id if category is not None else None


def _get_resource(db: Session, principal: Principal, resource_id: int) -> LearningResource:
    resource = db.scalar(
        select(LearningResource).where(
            LearningResource.id == resource_id,
            LearningResource.school_id == principal.school_id,
        )
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    return resource


def _can_access_resource(
    principal: Principal,
    operator: User,
    resource: LearningResource,
    accessible_classroom_ids: list[int],
) -> bool:
    if principal.role != UserRole.TEACHER:
        return True
    if resource.uploader_user_id == operator.id:
        return True
    if resource.classroom_id is None:
        return True
    return resource.classroom_id in accessible_classroom_ids


def _can_manage_resource(principal: Principal, operator: User, resource: LearningResource) -> bool:
    if principal.role != UserRole.TEACHER:
        return True
    return resource.uploader_user_id == operator.id


def _serialize_teacher_resource(
    db: Session,
    principal: Principal,
    operator: User,
    resource: LearningResource,
) -> TeacherResourceSummary:
    classroom = db.get(Classroom, resource.classroom_id) if resource.classroom_id else None
    category = db.get(ResourceCategory, resource.category_id) if resource.category_id else None
    uploader = db.get(User, resource.uploader_user_id)
    return TeacherResourceSummary(
        id=resource.id,
        title=resource.title,
        description=resource.description,
        audience=resource.audience,
        category_id=resource.category_id,
        category_name=category.name if category else None,
        classroom_id=resource.classroom_id,
        classroom_name=classroom.name if classroom else None,
        original_filename=resource.original_filename,
        file_size=resource.file_size,
        file_size_label=_format_file_size(resource.file_size),
        download_count=resource.download_count,
        uploaded_by_name=uploader.display_name if uploader else "教师",
        uploaded_at=_format_full(resource.created_at),
        active=resource.active,
        can_manage=_can_manage_resource(principal, operator, resource),
    )


def _list_teacher_resources(
    db: Session,
    principal: Principal,
    operator: User,
    accessible_classroom_ids: list[int],
) -> list[TeacherResourceSummary]:
    resources = db.scalars(
        select(LearningResource)
        .where(LearningResource.school_id == principal.school_id)
        .order_by(LearningResource.active.desc(), LearningResource.created_at.desc(), LearningResource.id.desc())
    ).all()
    return [
        _serialize_teacher_resource(db, principal, operator, resource)
        for resource in resources
        if _can_access_resource(principal, operator, resource, accessible_classroom_ids)
    ]


def _build_student_roster(
    db: Session,
    principal: Principal,
    accessible_classroom_ids: list[int],
    session_obj: ClassSession | None,
) -> tuple[str, bool, list[TeacherStudentRosterEntry]]:
    if session_obj is not None:
        target_classroom_ids = [session_obj.classroom_id]
        current_classroom = db.get(Classroom, session_obj.classroom_id)
        scope = f"{current_classroom.name if current_classroom else '当前班级'} · 课堂花名册"
        live = True
        attendance_map = {
            row.user_id: row
            for row in db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id == session_obj.id)).all()
        }
        presence_map = {
            row.user_id: row
            for row in db.scalars(select(PresenceState).where(PresenceState.session_id == session_obj.id)).all()
        }
        submission_map = {
            row.user_id: row
            for row in db.scalars(select(Submission).where(Submission.session_id == session_obj.id)).all()
        }
    else:
        live = False
        if principal.role == UserRole.TEACHER:
            target_classroom_ids = accessible_classroom_ids
            scope = "已分配班级学生名册"
        else:
            target_classroom_ids = list(
                db.scalars(select(Classroom.id).where(Classroom.school_id == principal.school_id).order_by(Classroom.id)).all()
            )
            scope = "全校学生名册"
        attendance_map: dict[int, AttendanceRecord] = {}
        presence_map: dict[int, PresenceState] = {}
        submission_map: dict[int, Submission] = {}

    if not target_classroom_ids:
        fallback_scope = "暂无已分配班级" if principal.role == UserRole.TEACHER else scope
        return fallback_scope, live, []

    classroom_map = {
        classroom.id: classroom
        for classroom in db.scalars(
            select(Classroom)
            .where(Classroom.school_id == principal.school_id, Classroom.id.in_(target_classroom_ids))
            .order_by(Classroom.grade_label, Classroom.name, Classroom.id)
        ).all()
    }
    students = db.scalars(
        select(User)
        .where(
            User.school_id == principal.school_id,
            User.role == UserRole.STUDENT,
            User.active.is_(True),
            User.classroom_id.in_(target_classroom_ids),
        )
        .order_by(User.classroom_id, User.username, User.id)
    ).all()

    rows: list[tuple[int, str, TeacherStudentRosterEntry]] = []
    for student in students:
        attendance = attendance_map.get(student.id)
        presence = presence_map.get(student.id)
        submission = submission_map.get(student.id)

        priority = 0
        attention_reason: str | None = None
        if live:
            if presence and presence.help_requested:
                priority = 100
                attention_reason = "学生正在举手求助，建议优先响应。"
            elif attendance and attendance.status in {AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED}:
                priority = 90
                attention_reason = "学生尚未完成到课确认，需要核对课堂进入情况。"
            elif presence and presence.status == PresenceStatus.OFFLINE:
                priority = 80
                attention_reason = "学生心跳已超时，可能离线或设备异常。"
            elif presence and presence.status == PresenceStatus.NOT_STARTED:
                priority = 70
                attention_reason = "学生还没有进入课堂任务，建议提醒开始。"
            elif presence and presence.status == PresenceStatus.IDLE:
                priority = 60
                attention_reason = "学生当前进度停滞，建议巡看是否卡住。"
            elif submission and submission.status == SubmissionStatus.SUBMITTED:
                priority = 50
                attention_reason = "作品已提交，正在等待教师批改。"

        classroom = classroom_map.get(student.classroom_id)
        rows.append(
            (
                priority,
                student.username,
                TeacherStudentRosterEntry(
                    student_id=student.id,
                    student_name=student.display_name,
                    student_username=student.username,
                    classroom_name=classroom.name if classroom else "未分班",
                    attendance_status=attendance.status if attendance else None,
                    presence_status=presence.status.value if presence else None,
                    progress_percent=presence.task_progress if presence else 0,
                    help_requested=presence.help_requested if presence else False,
                    submission_id=submission.id if submission else None,
                    submission_status=submission.status if submission else None,
                    review_decision=submission.review_decision if submission else None,
                    last_seen_at=_format_hms(presence.last_seen_at) if presence else None,
                    attention_reason=attention_reason,
                ),
            )
        )

    rows.sort(key=lambda item: (-item[0], item[2].classroom_name, item[1]))
    return scope, live, [item[2] for item in rows]


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


def _build_session_analytics(db: Session, session_obj: ClassSession) -> TeacherSessionAnalytics:
    attendance_records = db.scalars(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_obj.id).order_by(AttendanceRecord.id)
    ).all()
    presence_rows = db.scalars(
        select(PresenceState).where(PresenceState.session_id == session_obj.id).order_by(PresenceState.id)
    ).all()
    submissions = db.scalars(
        select(Submission).where(Submission.session_id == session_obj.id).order_by(Submission.id)
    ).all()
    students = db.scalars(
        select(User).where(
            User.school_id == session_obj.school_id,
            User.classroom_id == session_obj.classroom_id,
            User.role == UserRole.STUDENT,
            User.active.is_(True),
        )
    ).all()

    expected = session_obj.expected_students or len(students)
    attendance_map = {record.user_id: record for record in attendance_records}
    presence_map = {row.user_id: row for row in presence_rows}
    submission_map = {submission.user_id: submission for submission in submissions}

    present_count = sum(1 for record in attendance_records if record.status == AttendanceStatus.PRESENT)
    late_count = sum(1 for record in attendance_records if record.status == AttendanceStatus.LATE)
    absent_count = sum(1 for record in attendance_records if record.status in {AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED})
    pending_count = sum(1 for record in attendance_records if record.status == AttendanceStatus.PENDING)

    draft_count = sum(1 for submission in submissions if submission.status == SubmissionStatus.DRAFT)
    submitted_count = sum(1 for submission in submissions if submission.status == SubmissionStatus.SUBMITTED)
    reviewed_count = sum(1 for submission in submissions if submission.status == SubmissionStatus.REVIEWED)
    approved_count = sum(1 for submission in submissions if submission.review_decision == ReviewDecision.APPROVED)
    revision_requested_count = sum(
        1 for submission in submissions if submission.review_decision == ReviewDecision.REVISION_REQUESTED
    )
    rejected_count = sum(1 for submission in submissions if submission.review_decision == ReviewDecision.REJECTED)

    average_progress = round(sum(row.task_progress for row in presence_rows) / len(presence_rows)) if presence_rows else 0
    help_request_count = sum(1 for row in presence_rows if row.help_requested)
    not_started_count = sum(1 for row in presence_rows if row.status == PresenceStatus.NOT_STARTED)
    stalled_count = sum(1 for row in presence_rows if row.status in {PresenceStatus.IDLE, PresenceStatus.OFFLINE})

    attention_candidates: list[tuple[int, TeacherAnalyticsAttentionStudent]] = []
    for student in students:
        attendance = attendance_map.get(student.id)
        presence = presence_map.get(student.id)
        submission = submission_map.get(student.id)

        priority = 0
        reason = ""
        progress_percent = presence.task_progress if presence else 0
        presence_status = presence.status.value if presence else PresenceStatus.NOT_STARTED.value

        if presence and presence.help_requested:
            priority = 90
            reason = "学生正在举手求助，建议优先回应。"
        elif attendance and attendance.status in {AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED}:
            priority = 80
            reason = "学生未正常到课，需要确认课堂进入情况。"
        elif presence and presence.status == PresenceStatus.OFFLINE:
            priority = 75
            reason = "学生长时间离线，可能存在网络或设备问题。"
        elif presence and presence.status == PresenceStatus.NOT_STARTED:
            priority = 70
            reason = "学生尚未进入任务，建议提醒开始作品。"
        elif presence and presence.status == PresenceStatus.IDLE:
            priority = 65
            reason = "学生进度停滞，可能卡在某个操作步骤。"
        elif submission and submission.status == SubmissionStatus.DRAFT and progress_percent < 60:
            priority = 55
            reason = "作品仍为草稿且进度偏慢，需要过程性支持。"
        elif submission and submission.status == SubmissionStatus.SUBMITTED:
            priority = 45
            reason = "学生作品已提交，等待教师批改反馈。"

        if priority > 0:
            attention_candidates.append(
                (
                    priority,
                    TeacherAnalyticsAttentionStudent(
                        student_name=student.display_name,
                        student_username=student.username,
                        progress_percent=progress_percent,
                        presence_status=presence_status,
                        reason=reason,
                    ),
                )
            )

    attention_candidates.sort(key=lambda item: (-item[0], item[1].student_username))
    attention_students = [item[1] for item in attention_candidates[:5]]

    submitted_or_reviewed = submitted_count + reviewed_count
    attendance_rate = _safe_percent(present_count + late_count, expected)
    submission_rate = _safe_percent(submitted_or_reviewed, expected)
    reviewed_rate = _safe_percent(reviewed_count, submitted_or_reviewed) if submitted_or_reviewed else 0

    highlights = [
        f"出勤率 {attendance_rate}% ，已到课 {present_count + late_count}/{expected} 人。",
        f"课堂平均进度 {average_progress}% ，当前有 {help_request_count} 人求助，{stalled_count + not_started_count} 人需要额外关注。",
        f"作品已提交 {submitted_or_reviewed}/{expected} 份，已发布反馈 {reviewed_count} 份。",
    ]
    if revision_requested_count > 0:
        highlights.append(f"已有 {revision_requested_count} 份作品进入“修改后重交”，需要后续追踪。")

    return TeacherSessionAnalytics(
        attendance_rate=attendance_rate,
        average_progress=average_progress,
        submission_rate=submission_rate,
        reviewed_rate=reviewed_rate,
        present_count=present_count,
        late_count=late_count,
        absent_count=absent_count,
        pending_count=pending_count,
        draft_count=draft_count,
        submitted_count=submitted_count,
        reviewed_count=reviewed_count,
        approved_count=approved_count,
        revision_requested_count=revision_requested_count,
        rejected_count=rejected_count,
        attention_students=attention_students,
        highlights=highlights,
    )


def _build_reflection_draft_fields(
    course: Course,
    classroom: Classroom,
    analytics: TeacherSessionAnalytics,
) -> tuple[str, str, str, str, str]:
    strengths = (
        f"《{course.title}》在 {classroom.name} 的课堂推进总体稳定，出勤率达到 {analytics.attendance_rate}% ，"
        f"班级平均任务进度为 {analytics.average_progress}% 。课堂中已有 {analytics.reviewed_count} 份作品完成反馈，"
        "说明学生已逐步进入“完成任务并接受修正”的节奏。"
    )

    risks = (
        f"当前仍有 {analytics.pending_count + analytics.absent_count} 名学生未稳定完成到课确认，"
        f"{analytics.draft_count} 份作品仍停留在草稿态，另有 {analytics.revision_requested_count} 份作品需要修改后重交。"
        "后续要重点盯住进度停滞、未进入任务和持续求助的学生。"
    )

    next_actions = (
        "下一课前先复盘本节课中最容易卡住的操作步骤，补一轮 3 分钟的集中演示；"
        "课堂中把“开始任务、提交作品、查看反馈”三个关键节点明确写到投屏提示里；"
        "课后优先处理已提交未反馈和需要重交的作品。"
    )

    student_support_plan = (
        "对当前进度明显偏慢或多次求助的学生安排近距离巡看；"
        "对已进入修改后重交状态的学生给出更具体的补改要求；"
        "对已经高质量完成作品的学生，下一节课可引导其承担同伴示范角色。"
    )

    draft_content = "\n".join(
        [
            f"课堂亮点：{strengths}",
            f"课堂风险：{risks}",
            f"下一步动作：{next_actions}",
            f"学生支持计划：{student_support_plan}",
        ]
    )
    return strengths, risks, next_actions, student_support_plan, draft_content


def _empty_analytics() -> TeacherSessionAnalytics:
    return TeacherSessionAnalytics(
        attendance_rate=0,
        average_progress=0,
        submission_rate=0,
        reviewed_rate=0,
        present_count=0,
        late_count=0,
        absent_count=0,
        pending_count=0,
        draft_count=0,
        submitted_count=0,
        reviewed_count=0,
        approved_count=0,
        revision_requested_count=0,
        rejected_count=0,
        attention_students=[],
        highlights=[
            "当前还没有进行中的课堂，先选择班级与已发布学案开始一节新课。",
            "如果你是新加入教师，请先在治理面板确认已分配可授课班级。",
        ],
    )


def _build_idle_console_response(
    db: Session,
    principal: Principal,
    operator: User,
    accessible_classroom_ids: list[int],
) -> TeacherConsoleResponse:
    managed_classrooms = _list_managed_classrooms(db, principal, accessible_classroom_ids)
    student_roster_scope, student_roster_live, student_roster = _build_student_roster(
        db,
        principal,
        accessible_classroom_ids,
        None,
    )
    launch_options = _list_launch_options(db, principal.school_id, accessible_classroom_ids)
    resources = _list_teacher_resources(db, principal, operator, accessible_classroom_ids)
    steps = [
        TodoItem(
            title="确认当前教师已分配可授课班级",
            status="done" if accessible_classroom_ids else "active",
        ),
        TodoItem(
            title="选择班级与已发布学案并开始新课次",
            status="active" if launch_options else "pending",
        ),
        TodoItem(title="开课后再进入签到、雷达与批改工作流", status="pending"),
    ]
    return TeacherConsoleResponse(
        session_id=None,
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name="待开课",
        lesson_title="请选择班级与学案",
        assignment_title="尚未开始课程",
        session_status="idle",
        radar=RadarSummary(online=0, expected=0, absent=0, idle=0, not_started=0, help_requests=0),
        workbench_steps=steps,
        lesson_plans=_list_courses(db, principal.school_id),
        managed_classrooms=managed_classrooms,
        resource_categories=_list_resource_categories(db, principal.school_id, active_only=False),
        student_roster_scope=student_roster_scope,
        student_roster_live=student_roster_live,
        student_roster=student_roster,
        launch_options=launch_options,
        resources=resources,
        attendance_records=[],
        help_requests=[],
        submissions=[],
        analytics=_empty_analytics(),
        reflection=TeacherReflectionSummary(),
        ai_drafts=[],
    )


def _build_console_response(db: Session, principal: Principal, operator: User) -> TeacherConsoleResponse:
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    managed_classrooms = _list_managed_classrooms(db, principal, accessible_classroom_ids)
    current_session = _find_current_session(db, principal, operator)
    if current_session is None:
        return _build_idle_console_response(db, principal, operator, accessible_classroom_ids)

    session_obj, course, classroom = current_session
    drafts = db.scalars(
        select(AISuggestionDraft)
        .where(AISuggestionDraft.teacher_id == operator.id, AISuggestionDraft.session_id == session_obj.id)
        .order_by(AISuggestionDraft.created_at.desc())
    ).all()

    submission_items = _serialize_submissions(db, session_obj)
    help_requests = _serialize_help_requests(db, session_obj)
    analytics = _build_session_analytics(db, session_obj)
    reflection = _serialize_reflection(_get_session_reflection(db, session_obj.id, operator.id))
    student_roster_scope, student_roster_live, student_roster = _build_student_roster(
        db,
        principal,
        accessible_classroom_ids,
        session_obj,
    )
    resources = _list_teacher_resources(db, principal, operator, accessible_classroom_ids)
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
        lesson_plans=_list_courses(db, principal.school_id),
        managed_classrooms=managed_classrooms,
        resource_categories=_list_resource_categories(db, principal.school_id, active_only=False),
        student_roster_scope=student_roster_scope,
        student_roster_live=student_roster_live,
        student_roster=student_roster,
        launch_options=_list_launch_options(db, principal.school_id, accessible_classroom_ids),
        resources=resources,
        attendance_records=_serialize_attendance(db, session_obj),
        help_requests=help_requests,
        submissions=submission_items,
        analytics=analytics,
        reflection=reflection,
        ai_drafts=[_serialize_draft(draft) for draft in drafts],
    )


def _build_dashboard_response(db: Session, principal: Principal, operator: User) -> TeacherDashboardResponse:
    console = _build_console_response(db, principal, operator)
    return TeacherDashboardResponse(
        session_id=console.session_id,
        school_name=console.school_name,
        teacher_name=console.teacher_name,
        class_name=console.class_name,
        lesson_title=console.lesson_title,
        assignment_title=console.assignment_title,
        session_status=console.session_status,
        radar=console.radar,
        workbench_steps=console.workbench_steps,
        launch_options=console.launch_options,
        managed_classrooms=console.managed_classrooms,
        analytics=console.analytics,
        student_roster_scope=console.student_roster_scope,
        student_roster_live=console.student_roster_live,
        student_roster=console.student_roster,
    )


def _build_attendance_response_from_session(
    db: Session,
    principal: Principal,
    operator: User,
    session_obj: ClassSession | None,
) -> TeacherAttendanceResponse:
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    if session_obj is None:
        return TeacherAttendanceResponse(
            session_id=None,
            school_name=principal.school_name,
            teacher_name=operator.display_name,
            class_name="Awaiting session",
            lesson_title="No active course",
            session_status="idle",
            radar=RadarSummary(online=0, expected=0, absent=0, idle=0, not_started=0, help_requests=0),
            analytics=_empty_analytics(),
            student_roster_scope="No live roster",
            student_roster_live=False,
            student_roster=[],
            attendance_records=[],
            help_requests=[],
        )

    course = db.get(Course, session_obj.course_id)
    classroom = db.get(Classroom, session_obj.classroom_id)
    if course is None or classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teaching context is incomplete.")
    student_roster_scope, student_roster_live, student_roster = _build_student_roster(
        db,
        principal,
        accessible_classroom_ids,
        session_obj,
    )
    return TeacherAttendanceResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        session_status=session_obj.status,
        radar=_build_radar_summary(db, session_obj),
        analytics=_build_session_analytics(db, session_obj),
        student_roster_scope=student_roster_scope,
        student_roster_live=student_roster_live,
        student_roster=student_roster,
        attendance_records=_serialize_attendance(db, session_obj),
        help_requests=_serialize_help_requests(db, session_obj),
    )


def _build_submissions_response(db: Session, principal: Principal, operator: User) -> TeacherSubmissionsResponse:
    current_session = _find_current_session(db, principal, operator)
    if current_session is None:
        return TeacherSubmissionsResponse(
            session_id=None,
            school_name=principal.school_name,
            teacher_name=operator.display_name,
            class_name="Awaiting session",
            lesson_title="No active course",
            assignment_title="No active assignment",
            session_status="idle",
            submissions=[],
            analytics=_empty_analytics(),
        )

    session_obj, course, classroom = current_session
    return TeacherSubmissionsResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        assignment_title=course.assignment_title,
        session_status=session_obj.status,
        submissions=_serialize_submissions(db, session_obj),
        analytics=_build_session_analytics(db, session_obj),
    )


def _build_copilot_response(db: Session, principal: Principal, operator: User) -> TeacherCopilotResponse:
    current_session = _find_current_session(db, principal, operator)
    if current_session is None:
        return TeacherCopilotResponse(
            session_id=None,
            school_name=principal.school_name,
            teacher_name=operator.display_name,
            class_name="Awaiting session",
            lesson_title="No active course",
            session_status="idle",
            reflection=TeacherReflectionSummary(),
            analytics=_empty_analytics(),
            ai_drafts=[],
        )

    session_obj, course, classroom = current_session
    drafts = db.scalars(
        select(AISuggestionDraft)
        .where(AISuggestionDraft.teacher_id == operator.id, AISuggestionDraft.session_id == session_obj.id)
        .order_by(AISuggestionDraft.created_at.desc())
    ).all()
    return TeacherCopilotResponse(
        session_id=session_obj.id,
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        class_name=classroom.name,
        lesson_title=course.title,
        session_status=session_obj.status,
        reflection=_serialize_reflection(_get_session_reflection(db, session_obj.id, operator.id)),
        analytics=_build_session_analytics(db, session_obj),
        ai_drafts=[_serialize_draft(draft) for draft in drafts],
    )


def _build_resources_response(db: Session, principal: Principal, operator: User) -> TeacherResourcesResponse:
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    return TeacherResourcesResponse(
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        managed_classrooms=_list_managed_classrooms(db, principal, accessible_classroom_ids),
        resource_categories=_list_resource_categories(db, principal.school_id, active_only=False),
        resources=_list_teacher_resources(db, principal, operator, accessible_classroom_ids),
    )


def _build_course_collection_response(
    db: Session,
    principal: Principal,
    operator: User,
    *,
    selected_course_id: int | None = None,
) -> TeacherCourseCollectionResponse:
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    courses = db.scalars(select(Course).where(Course.school_id == principal.school_id).order_by(Course.updated_at.desc())).all()
    selected_course = None
    if selected_course_id is not None:
        selected_course_model = _get_course(db, principal, selected_course_id)
        selected_course = _serialize_course_detail(selected_course_model)
    elif courses:
        selected_course = _serialize_course_detail(courses[0])

    return TeacherCourseCollectionResponse(
        school_name=principal.school_name,
        teacher_name=operator.display_name,
        managed_classrooms=_list_managed_classrooms(db, principal, accessible_classroom_ids),
        launch_options=_list_launch_options(db, principal.school_id, accessible_classroom_ids),
        courses=[_serialize_course(course) for course in courses],
        selected_course=selected_course,
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


@router.get("/dashboard", response_model=TeacherDashboardResponse)
def teacher_dashboard(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherDashboardResponse:
    operator = _resolve_operator(db, principal)
    return _build_dashboard_response(db, principal, operator)


@router.get("/attendance", response_model=TeacherAttendanceResponse)
def teacher_attendance_overview(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherAttendanceResponse:
    operator = _resolve_operator(db, principal)
    current_session = _find_current_session(db, principal, operator)
    session_obj = current_session[0] if current_session else None
    return _build_attendance_response_from_session(db, principal, operator, session_obj)


@router.get("/attendance/sessions/{session_id}", response_model=TeacherAttendanceResponse)
def teacher_attendance_session_detail(
    session_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherAttendanceResponse:
    operator = _resolve_operator(db, principal)
    session_obj = _get_class_session(db, principal, session_id)
    _ensure_teacher_session_access(db, principal, operator, session_obj.id)
    return _build_attendance_response_from_session(db, principal, operator, session_obj)


@router.get("/submissions", response_model=TeacherSubmissionsResponse)
def teacher_submissions_overview(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherSubmissionsResponse:
    operator = _resolve_operator(db, principal)
    return _build_submissions_response(db, principal, operator)


@router.get("/courses", response_model=TeacherCourseCollectionResponse)
def teacher_courses(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCourseCollectionResponse:
    operator = _resolve_operator(db, principal)
    return _build_course_collection_response(db, principal, operator)


@router.get("/courses/{course_id}", response_model=TeacherCourseDetailResponse)
def teacher_course_detail(
    course_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCourseDetailResponse:
    _resolve_operator(db, principal)
    course = _get_course(db, principal, course_id)
    return _serialize_course_detail(course)


@router.get("/copilot", response_model=TeacherCopilotResponse)
def teacher_copilot(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCopilotResponse:
    operator = _resolve_operator(db, principal)
    return _build_copilot_response(db, principal, operator)


@router.get("/resources/overview", response_model=TeacherResourcesResponse)
def teacher_resources_overview(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherResourcesResponse:
    operator = _resolve_operator(db, principal)
    return _build_resources_response(db, principal, operator)


@router.get("/submissions/{submission_id}", response_model=TeacherSubmissionDetail)
def teacher_submission_detail(
    submission_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherSubmissionDetail:
    operator = _resolve_operator(db, principal)
    submission = _get_submission(db, principal, submission_id)
    _ensure_teacher_submission_access(db, principal, operator, submission)
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
    _ensure_teacher_submission_access(db, principal, operator, submission)
    if submission.status == SubmissionStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft submission cannot be reviewed yet.")

    now = utc_now()
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
    _ensure_teacher_submission_access(db, principal, operator, submission)
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
    db.flush()
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_created",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Created AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(
            draft,
            f"submission_id={submission.id}; student_username={student.username}",
        ),
    )
    db.commit()
    db.refresh(draft)
    return CreateDraftResponse(draft=_serialize_draft(draft))


@router.post("/courses", response_model=TeacherCourseSummary)
def save_course(
    payload: TeacherCourseSaveRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCourseSummary:
    _resolve_operator(db, principal)
    if payload.course_id is not None:
        course = _get_course(db, principal, payload.course_id)
    else:
        course = Course(
            school_id=principal.school_id,
            title=payload.title.strip(),
            stage_label=payload.stage_label.strip(),
            assignment_title=payload.assignment_title.strip(),
            assignment_prompt=payload.assignment_prompt.strip(),
            overview=payload.overview.strip() if payload.overview else None,
            is_published=False,
        )
        db.add(course)
        db.flush()

    course.title = payload.title.strip()
    course.stage_label = payload.stage_label.strip()
    course.overview = payload.overview.strip() if payload.overview else None
    course.assignment_title = payload.assignment_title.strip()
    course.assignment_prompt = payload.assignment_prompt.strip()
    _sync_course_activities(db, course, payload)
    if payload.publish_now:
        course.is_published = True
        course.published_at = utc_now()

    db.commit()
    db.refresh(course)
    return _serialize_course(course)


@router.post("/courses/{course_id}/publish", response_model=TeacherCourseSummary)
def publish_course(
    course_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCourseSummary:
    _resolve_operator(db, principal)
    course = _get_course(db, principal, course_id)
    course.is_published = True
    course.published_at = utc_now()
    db.commit()
    db.refresh(course)
    return _serialize_course(course)


@router.post("/courses/{course_id}/unpublish", response_model=TeacherCourseSummary)
def unpublish_course(
    course_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherCourseSummary:
    _resolve_operator(db, principal)
    course = _get_course(db, principal, course_id)
    course.is_published = False
    db.commit()
    db.refresh(course)
    return _serialize_course(course)


@router.post("/activities/{activity_id}/interactive-upload", response_model=CourseActivitySummary)
async def upload_interactive_activity_asset(
    activity_id: int,
    upload: UploadFile = File(...),
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> CourseActivitySummary:
    _resolve_operator(db, principal)
    activity = _get_course_activity(db, principal, activity_id)
    if activity.activity_type != CourseActivityType.INTERACTIVE_PAGE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only interactive page activities can accept HTML or ZIP uploads.",
        )
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload file is required.")

    try:
        storage_key, entry_file, asset_name, _ = await save_uploaded_interactive_package(upload, principal.school_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    activity.interactive_storage_key = storage_key
    activity.interactive_entry_file = entry_file
    activity.interactive_asset_name = asset_name
    activity.interactive_launch_key = activity.interactive_launch_key or secrets.token_urlsafe(18)
    activity.interactive_submission_key = activity.interactive_submission_key or secrets.token_urlsafe(24)
    db.commit()
    db.refresh(activity)
    return _serialize_course_activity(activity)


@router.post("/resources", response_model=TeacherResourceSummary)
async def upload_resource(
    title: str = Form(...),
    audience: ResourceAudience = Form(...),
    description: str | None = Form(default=None),
    category_id: int | None = Form(default=None),
    classroom_id: int | None = Form(default=None),
    upload: UploadFile = File(...),
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherResourceSummary:
    operator = _resolve_operator(db, principal)
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)

    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Resource title is required.")
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload file is required.")

    resolved_category_id = category_id
    if resolved_category_id is None:
        resolved_category_id = _get_default_resource_category_id(db, principal)
    if resolved_category_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active resource category is available for this school.",
        )
    _get_resource_category(db, principal, resolved_category_id, active_only=True)

    if principal.role == UserRole.TEACHER:
        if classroom_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Teachers must select one assigned classroom for resource publishing.",
            )
        if classroom_id not in accessible_classroom_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current teacher cannot publish resources to the selected classroom.",
            )
    elif classroom_id is not None:
        _get_classroom(db, principal, classroom_id)

    storage_key, file_size = await save_uploaded_resource(upload, principal.school_code)
    resource = LearningResource(
        school_id=principal.school_id,
        classroom_id=classroom_id,
        category_id=resolved_category_id,
        uploader_user_id=operator.id,
        title=normalized_title,
        description=description.strip() if description and description.strip() else None,
        audience=audience,
        original_filename=upload.filename,
        storage_key=storage_key,
        content_type=upload.content_type,
        file_size=file_size,
        active=True,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return _serialize_teacher_resource(db, principal, operator, resource)


@router.post("/resources/{resource_id}/status", response_model=TeacherResourceSummary)
def update_resource_status(
    resource_id: int,
    payload: TeacherResourceStatusRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherResourceSummary:
    operator = _resolve_operator(db, principal)
    resource = _get_resource(db, principal, resource_id)
    if not _can_manage_resource(principal, operator, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current session cannot manage this resource.")
    resource.active = payload.active
    db.commit()
    db.refresh(resource)
    return _serialize_teacher_resource(db, principal, operator, resource)


@router.get("/resources/{resource_id}/download")
def download_teacher_resource(
    resource_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> FileResponse:
    operator = _resolve_operator(db, principal)
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    resource = _get_resource(db, principal, resource_id)
    if not _can_access_resource(principal, operator, resource, accessible_classroom_ids):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current session cannot access this resource.")

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


@router.post("/reflection", response_model=TeacherReflectionSummary)
def save_reflection(
    payload: TeacherReflectionRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherReflectionSummary:
    operator = _resolve_operator(db, principal)
    session_obj, _, _ = _get_current_session(db, principal, operator)
    reflection = _get_session_reflection(db, session_obj.id, operator.id)
    if reflection is None:
        reflection = SessionReflection(
            school_id=principal.school_id,
            session_id=session_obj.id,
            teacher_id=operator.id,
        )
        db.add(reflection)

    reflection.strengths = payload.strengths.strip()
    reflection.risks = payload.risks.strip()
    reflection.next_actions = payload.next_actions.strip()
    reflection.student_support_plan = payload.student_support_plan.strip()

    db.commit()
    db.refresh(reflection)
    return _serialize_reflection(reflection)


@router.post("/reflection/draft", response_model=TeacherReflectionDraftResponse)
def create_reflection_draft(
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherReflectionDraftResponse:
    operator = _resolve_operator(db, principal)
    session_obj, course, classroom = _get_current_session(db, principal, operator)
    analytics = _build_session_analytics(db, session_obj)
    strengths, risks, next_actions, student_support_plan, draft_content = _build_reflection_draft_fields(
        course,
        classroom,
        analytics,
    )
    draft = AISuggestionDraft(
        school_id=principal.school_id,
        teacher_id=operator.id,
        session_id=session_obj.id,
        draft_type="教学反思草稿",
        title=f"{course.title} · {classroom.name} · 教学反思",
        content=draft_content,
        status="draft",
    )
    db.add(draft)
    db.flush()
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_created",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Created AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(
            draft,
            f"course_id={course.id}; classroom_id={classroom.id}",
        ),
    )
    db.commit()
    db.refresh(draft)
    return TeacherReflectionDraftResponse(
        draft=_serialize_draft(draft),
        reflection=TeacherReflectionSummary(
            strengths=strengths,
            risks=risks,
            next_actions=next_actions,
            student_support_plan=student_support_plan,
            ai_draft_content=draft_content,
        ),
    )


@router.post("/session/start", response_model=TeacherConsoleResponse)
def start_session(
    payload: StartSessionRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherConsoleResponse:
    operator = _resolve_operator(db, principal)
    accessible_classroom_ids = _get_accessible_classroom_ids(db, principal, operator)
    classroom = db.scalar(
        select(Classroom).where(Classroom.id == payload.classroom_id, Classroom.school_id == principal.school_id)
    )
    course = db.scalar(
        select(Course).where(Course.id == payload.course_id, Course.school_id == principal.school_id)
    )
    if classroom is None or course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom or course not found.")
    if principal.role == UserRole.TEACHER and classroom.id not in accessible_classroom_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current teacher is not assigned to the selected classroom.",
        )

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
        started_at=utc_now(),
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
                last_seen_at=utc_now(),
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
    _ensure_teacher_session_access(db, principal, operator, attendance.session_id)

    now = utc_now()
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
    db.flush()
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_created",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Created AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(
            draft,
            f"goal={_shorten(payload.goal.strip(), limit=120)}; course_id={course.id}; classroom_id={classroom.id}",
        ),
    )
    db.commit()
    db.refresh(draft)
    return CreateDraftResponse(draft=_serialize_draft(draft))


@router.post("/ai/drafts/{draft_id}/save", response_model=TeacherDraft)
def save_ai_draft(
    draft_id: int,
    payload: TeacherDraftUpdateRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherDraft:
    operator = _resolve_operator(db, principal)
    draft = _get_ai_draft(db, principal, operator, draft_id)
    _ensure_draft_editable(draft)
    title, content = _normalize_teacher_draft_update(payload)
    draft.title = title
    draft.content = content
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_updated",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Updated AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(draft, "status=draft"),
    )
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.post("/ai/drafts/{draft_id}/accept", response_model=TeacherDraft)
def accept_ai_draft(
    draft_id: int,
    payload: TeacherDraftUpdateRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherDraft:
    operator = _resolve_operator(db, principal)
    draft = _get_ai_draft(db, principal, operator, draft_id)
    _ensure_draft_editable(draft)
    title, content = _normalize_teacher_draft_update(payload)
    draft.title = title
    draft.content = content
    draft.status = "accepted"
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_accepted",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Accepted AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(draft, "status=accepted"),
    )
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)


@router.post("/ai/drafts/{draft_id}/reject", response_model=TeacherDraft)
def reject_ai_draft(
    draft_id: int,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
) -> TeacherDraft:
    operator = _resolve_operator(db, principal)
    draft = _get_ai_draft(db, principal, operator, draft_id)
    _ensure_draft_editable(draft)
    draft.status = "rejected"
    _append_teacher_audit_log(
        db,
        principal,
        action="teacher_ai_draft_rejected",
        target_label=draft.title,
        target_id=str(draft.id),
        summary=f"Rejected AI draft: {draft.title}",
        detail=_build_ai_draft_audit_detail(draft, "status=rejected"),
        level=AuditLogLevel.WARNING,
    )
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft)
