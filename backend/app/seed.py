from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.auth import hash_password, verify_password
from .core.clock import utc_now
from .core.resource_storage import ensure_seed_resource_file
from .models import (
    AcademicTerm,
    ActivitySubmission,
    AISuggestionDraft,
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    CourseActivity,
    CourseActivityType,
    HelpRequest,
    LegacyIdMapping,
    LearningResource,
    MigrationBatch,
    MigrationPreviewItem,
    MigrationStatus,
    PresenceState,
    PresenceStatus,
    ResourceCategory,
    ResourceAudience,
    ReviewDecision,
    SessionReflection,
    School,
    Submission,
    SubmissionRevision,
    SubmissionRevisionAction,
    SubmissionReview,
    SubmissionStatus,
    TeacherClassroomAssignment,
    ThemeStyle,
    User,
    UserRole,
)


def _ensure_terms(
    db: Session,
    *,
    school_id: int,
    terms: list[tuple[str, str, date | None, date | None, bool, int]],
) -> bool:
    changed = False
    for school_year_label, term_name, start_on, end_on, is_active, sort_order in terms:
        existing = db.scalar(
            select(AcademicTerm).where(
                AcademicTerm.school_id == school_id,
                AcademicTerm.school_year_label == school_year_label,
                AcademicTerm.term_name == term_name,
            )
        )
        if existing is not None:
            continue
        if is_active:
            active_terms = db.scalars(
                select(AcademicTerm).where(AcademicTerm.school_id == school_id, AcademicTerm.is_active.is_(True))
            ).all()
            for term in active_terms:
                term.is_active = False
        db.add(
            AcademicTerm(
                school_id=school_id,
                school_year_label=school_year_label,
                term_name=term_name,
                start_on=start_on,
                end_on=end_on,
                is_active=is_active,
                sort_order=sort_order,
            )
        )
        changed = True
    return changed


def _ensure_session_reflection(
    db: Session,
    *,
    school_id: int,
    session_id: int,
    teacher_id: int,
    strengths: str,
    risks: str,
    next_actions: str,
    student_support_plan: str,
    ai_draft_content: str | None = None,
) -> bool:
    reflection = db.scalar(
        select(SessionReflection).where(
            SessionReflection.session_id == session_id,
            SessionReflection.teacher_id == teacher_id,
        )
    )
    if reflection is not None:
        return False

    db.add(
        SessionReflection(
            school_id=school_id,
            session_id=session_id,
            teacher_id=teacher_id,
            strengths=strengths,
            risks=risks,
            next_actions=next_actions,
            student_support_plan=student_support_plan,
            ai_draft_content=ai_draft_content,
        )
    )
    return True


def _ensure_teacher_classroom_assignments(
    db: Session,
    *,
    school_id: int,
    teacher_id: int,
    classroom_ids: list[int],
) -> bool:
    existing_rows = db.scalars(
        select(TeacherClassroomAssignment).where(
            TeacherClassroomAssignment.school_id == school_id,
            TeacherClassroomAssignment.teacher_user_id == teacher_id,
        )
    ).all()
    existing_ids = {row.classroom_id for row in existing_rows}
    target_ids = set(classroom_ids)
    changed = False

    for row in existing_rows:
        if row.classroom_id not in target_ids:
            db.delete(row)
            changed = True

    for classroom_id in target_ids - existing_ids:
        db.add(
            TeacherClassroomAssignment(
                school_id=school_id,
                teacher_user_id=teacher_id,
                classroom_id=classroom_id,
            )
        )
        changed = True

    return changed


def _ensure_learning_resource(
    db: Session,
    *,
    school: School,
    uploader: User,
    category_id: int | None,
    title: str,
    audience: ResourceAudience,
    original_filename: str,
    file_body: str,
    description: str | None = None,
    classroom_id: int | None = None,
) -> bool:
    existing = db.scalar(
        select(LearningResource).where(
            LearningResource.school_id == school.id,
            LearningResource.title == title,
            LearningResource.original_filename == original_filename,
        )
    )
    if existing is not None:
        changed = False
        if category_id is not None and existing.category_id != category_id:
            existing.category_id = category_id
            changed = True
        if description is not None and existing.description != description:
            existing.description = description
            changed = True
        if existing.audience != audience:
            existing.audience = audience
            changed = True
        if existing.classroom_id != classroom_id:
            existing.classroom_id = classroom_id
            changed = True
        if not existing.active:
            existing.active = True
            changed = True
        return changed

    storage_key, file_size = ensure_seed_resource_file(school.code, original_filename, file_body)
    db.add(
        LearningResource(
            school_id=school.id,
            classroom_id=classroom_id,
            category_id=category_id,
            uploader_user_id=uploader.id,
            title=title,
            description=description,
            audience=audience,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type="text/plain; charset=utf-8",
            file_size=file_size,
            active=True,
        )
    )
    return True


def _ensure_resource_categories(
    db: Session,
    *,
    school_id: int,
    categories: list[tuple[str, str | None, int, bool]],
) -> dict[str, ResourceCategory]:
    category_map: dict[str, ResourceCategory] = {}
    for name, description, sort_order, active in categories:
        existing = db.scalar(
            select(ResourceCategory).where(
                ResourceCategory.school_id == school_id,
                ResourceCategory.name == name,
            )
        )
        if existing is None:
            existing = ResourceCategory(
                school_id=school_id,
                name=name,
                description=description,
                sort_order=sort_order,
                active=active,
            )
            db.add(existing)
            db.flush()
        else:
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.sort_order != sort_order:
                existing.sort_order = sort_order
                changed = True
            if existing.active != active:
                existing.active = active
                changed = True
            if changed:
                db.flush()
        category_map[name] = existing
    return category_map


def _ensure_course_activity(
    db: Session,
    *,
    course: Course,
    position: int,
    title: str,
    activity_type: CourseActivityType,
    instructions_html: str,
    summary: str | None = None,
) -> bool:
    existing = db.scalar(
        select(CourseActivity).where(
            CourseActivity.course_id == course.id,
            CourseActivity.position == position,
        )
    )
    if existing is None:
        existing = CourseActivity(
            school_id=course.school_id,
            course_id=course.id,
            position=position,
            title=title,
            activity_type=activity_type,
            instructions_html=instructions_html,
            summary=summary,
        )
        db.add(existing)
        db.flush()
        return True

    changed = False
    if existing.title != title:
        existing.title = title
        changed = True
    if existing.activity_type != activity_type:
        existing.activity_type = activity_type
        changed = True
    if existing.instructions_html != instructions_html:
        existing.instructions_html = instructions_html
        changed = True
    if existing.summary != summary:
        existing.summary = summary
        changed = True
    if changed:
        db.flush()
    return changed


def _ensure_demo_user(
    db: Session,
    *,
    school_id: int,
    username: str,
    display_name: str,
    password: str,
    role: UserRole,
    classroom_id: int | None = None,
    active: bool = True,
) -> tuple[User, bool]:
    user = next(
        (
            pending_user
            for pending_user in db.new
            if isinstance(pending_user, User)
            and pending_user.school_id == school_id
            and pending_user.username == username
        ),
        None,
    )
    if user is None:
        user = db.scalar(
            select(User).where(
                User.school_id == school_id,
                User.username == username,
            )
        )
    if user is None:
        user = User(
            school_id=school_id,
            classroom_id=classroom_id,
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role=role,
            active=active,
        )
        db.add(user)
        db.flush()
        return user, True

    changed = False
    if user.classroom_id != classroom_id:
        user.classroom_id = classroom_id
        changed = True
    if user.display_name != display_name:
        user.display_name = display_name
        changed = True
    if user.role != role:
        user.role = role
        changed = True
    if user.active != active:
        user.active = active
        changed = True
    if not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
        changed = True

    if changed:
        db.flush()
    return user, changed


def _ensure_multi_school_demo_data(db: Session) -> None:
    changed = False
    default_resource_categories = [
        ("课堂模板", "适合学生直接下载并在课堂中填写的任务模板。", 1, True),
        ("讲义课件", "用于课堂讲解、投屏展示或课后回看的讲义与课件。", 2, True),
        ("示例作品", "供学生参考的优秀样例、范文或演示结果。", 3, True),
        ("自主学习", "适合学生课前预习或课后拓展阅读的资料。", 4, True),
        ("教师备课", "教师内部可见的备课材料、清单与讲解脚本。", 5, True),
    ]

    school_a = db.scalar(select(School).where(School.code == "school-a"))
    if school_a is None:
        return
    school_a_resource_categories = _ensure_resource_categories(
        db,
        school_id=school_a.id,
        categories=default_resource_categories,
    )

    class_a1 = db.scalar(
        select(Classroom).where(
            Classroom.school_id == school_a.id,
            Classroom.name == "八年级 1 班",
        )
    )
    if class_a1 is None:
        class_a1 = Classroom(school_id=school_a.id, name="八年级 1 班", grade_label="八年级")
        db.add(class_a1)
        db.flush()
        changed = True

    class_a2 = db.scalar(
        select(Classroom).where(
            Classroom.school_id == school_a.id,
            Classroom.name == "八年级 2 班",
        )
    )
    if class_a2 is None:
        class_a2 = Classroom(school_id=school_a.id, name="八年级 2 班", grade_label="八年级")
        db.add(class_a2)
        db.flush()
        changed = True

    teacher_a, teacher_a_changed = _ensure_demo_user(
        db,
        school_id=school_a.id,
        username="kylin",
        display_name="Kylin 老师",
        password="222221",
        role=UserRole.TEACHER,
    )
    changed = teacher_a_changed or changed
    _, admin_a_changed = _ensure_demo_user(
        db,
        school_id=school_a.id,
        username="admin",
        display_name="学校管理员",
        password="222221",
        role=UserRole.SCHOOL_ADMIN,
    )
    changed = admin_a_changed or changed

    for username, display_name in [
        ("240101", "李同学"),
        ("240102", "王同学"),
        ("240103", "张同学"),
        ("240104", "陈同学"),
        ("240105", "赵同学"),
    ]:
        _, student_changed = _ensure_demo_user(
            db,
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username=username,
            display_name=display_name,
            password="12345",
            role=UserRole.STUDENT,
        )
        changed = student_changed or changed

    session_a = None
    if teacher_a is not None:
        session_a = db.scalar(
            select(ClassSession)
            .where(
                ClassSession.school_id == school_a.id,
                ClassSession.teacher_id == teacher_a.id,
            )
            .order_by(ClassSession.started_at.desc())
        )
    if teacher_a is not None and session_a is not None:
        changed = (
            _ensure_session_reflection(
                db,
                school_id=school_a.id,
                session_id=session_a.id,
                teacher_id=teacher_a.id,
                strengths="课堂节奏总体平稳，绝大多数学生已经进入图表作品任务，课堂主线清晰。",
                risks="仍有学生停留在草稿或未开始状态，个别学生因为网络与结论表达问题需要额外支持。",
                next_actions="下一节课先集中示范如何写出更完整的数据结论，再针对重交作品做小范围讲评。",
                student_support_plan="对求助学生和重交学生优先巡看，对已经完成较好的学生安排示范分享。",
                ai_draft_content="课堂亮点：任务目标清晰，学生已进入图表作品主线。\n课堂风险：仍有未开始和离线学生，需要补做过程支持。\n下一步动作：先补一轮结论示范，再追踪重交作品。\n学生支持计划：优先响应求助学生，并安排优秀作品示范。",
            )
            or changed
        )
    class_a1 = db.scalar(
        select(Classroom).where(
            Classroom.school_id == school_a.id,
            Classroom.name == "八年级 1 班",
        )
    )
    if teacher_a is not None and class_a1 is not None:
        changed = (
            _ensure_teacher_classroom_assignments(
                db,
                school_id=school_a.id,
                teacher_id=teacher_a.id,
                classroom_ids=[class_a1.id],
            )
            or changed
        )
        changed = (
            _ensure_learning_resource(
                db,
                school=school_a,
                uploader=teacher_a,
                category_id=school_a_resource_categories["课堂模板"].id,
                classroom_id=class_a1.id,
                title="数据采集观察模板",
                description="给八年级 1 班学生的课堂观察模板，帮助整理图表和结论。",
                audience=ResourceAudience.STUDENT,
                original_filename="data-observation-template.txt",
                file_body="1. 记录课堂采集到的数据\\n2. 描述图表中的变化趋势\\n3. 写出至少两条结论\\n",
            )
            or changed
        )

    changed = (
        _ensure_terms(
            db,
            school_id=school_a.id,
            terms=[
                ("2025-2026", "2025 秋季学期", date(2025, 9, 1), date(2026, 1, 20), False, 1),
                ("2025-2026", "2026 春季学期", date(2026, 2, 18), date(2026, 7, 10), True, 2),
            ],
        )
        or changed
    )

    platform_admin = db.scalar(
        select(User).where(
            User.school_id == school_a.id,
            User.username == "platform",
        )
    )
    if platform_admin is None:
        db.add(
            User(
                school_id=school_a.id,
                username="platform",
                display_name="平台管理员",
                password_hash=hash_password("222221"),
                role=UserRole.PLATFORM_ADMIN,
            )
        )
        changed = True
    _, platform_admin_changed = _ensure_demo_user(
        db,
        school_id=school_a.id,
        username="platform",
        display_name="平台管理员",
        password="222221",
        role=UserRole.PLATFORM_ADMIN,
    )
    changed = platform_admin_changed or changed

    school_b = db.scalar(select(School).where(School.code == "school-b"))
    if school_b is None:
        school_b = School(
            code="school-b",
            name="未来学校 B",
            city="杭州",
            slogan="多学校门户接入的第二套演示样板",
            theme_style=ThemeStyle.NATURAL,
        )
        db.add(school_b)
        db.flush()
        changed = True
    school_b_resource_categories = _ensure_resource_categories(
        db,
        school_id=school_b.id,
        categories=default_resource_categories,
    )

    changed = (
        _ensure_terms(
            db,
            school_id=school_b.id,
            terms=[
                ("2025-2026", "2025 秋季学期", date(2025, 9, 1), date(2026, 1, 18), False, 1),
                ("2025-2026", "2026 春季学期", date(2026, 2, 20), date(2026, 7, 12), True, 2),
            ],
        )
        or changed
    )

    class_b1 = db.scalar(
        select(Classroom).where(
            Classroom.school_id == school_b.id,
            Classroom.name == "七年级 2 班",
        )
    )
    if class_b1 is None:
        class_b1 = Classroom(school_id=school_b.id, name="七年级 2 班", grade_label="七年级")
        db.add(class_b1)
        db.flush()
        changed = True

    teacher_b = db.scalar(
        select(User).where(
            User.school_id == school_b.id,
            User.username == "linhua",
        )
    )
    created_school_b_demo = False
    if teacher_b is None:
        created_school_b_demo = True
        teacher_b = User(
            school_id=school_b.id,
            username="linhua",
            display_name="林华老师",
            password_hash=hash_password("222221"),
            role=UserRole.TEACHER,
        )
        admin_b = User(
            school_id=school_b.id,
            username="adminb",
            display_name="未来学校管理员",
            password_hash=hash_password("222221"),
            role=UserRole.SCHOOL_ADMIN,
        )
        students_b = [
            User(
                school_id=school_b.id,
                classroom_id=class_b1.id,
                username="250201",
                display_name="周同学",
                password_hash=hash_password("12345"),
                role=UserRole.STUDENT,
            ),
            User(
                school_id=school_b.id,
                classroom_id=class_b1.id,
                username="250202",
                display_name="吴同学",
                password_hash=hash_password("12345"),
                role=UserRole.STUDENT,
            ),
            User(
                school_id=school_b.id,
                classroom_id=class_b1.id,
                username="250203",
                display_name="郑同学",
                password_hash=hash_password("12345"),
                role=UserRole.STUDENT,
            ),
        ]
        db.add_all([teacher_b, admin_b, *students_b])
        db.flush()
        _ensure_teacher_classroom_assignments(
            db,
            school_id=school_b.id,
            teacher_id=teacher_b.id,
            classroom_ids=[class_b1.id],
        )

        course_robot = Course(
            school_id=school_b.id,
            title="智能硬件与传感器",
            stage_label="第 1 课 · 环境监测仪表板",
            overview="围绕传感器采集、图表整理和异常值讨论组织一节智能硬件入门课。",
            assignment_title="传感器课堂记录卡",
            assignment_prompt="整理本节课的温湿度采集结果，用 1 张图表和 2 条结论说明你的观察。",
            is_published=True,
            published_at=utc_now() - timedelta(days=7),
        )
        course_data = Course(
            school_id=school_b.id,
            title="数据表达与可视化",
            stage_label="第 2 课 · 班级数据小报",
            overview="用班级真实调查数据练习数据表达、信息排版和结论输出。",
            assignment_title="班级数据小报草稿",
            assignment_prompt="把课堂调查结果整理成小报，包含标题、图表、说明文字和一个结论。",
            is_published=True,
            published_at=utc_now() - timedelta(days=5),
        )
        db.add_all([course_robot, course_data])
        db.flush()

        session_b = ClassSession(
            school_id=school_b.id,
            classroom_id=class_b1.id,
            course_id=course_robot.id,
            teacher_id=teacher_b.id,
            title=course_robot.title,
            stage=course_robot.stage_label,
            status="active",
            expected_students=len(students_b),
            started_at=utc_now() - timedelta(minutes=12),
        )
        db.add(session_b)
        db.flush()

        now = utc_now()
        db.add_all(
            [
                PresenceState(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[0].id,
                    status=PresenceStatus.ACTIVE,
                    task_progress=92,
                    help_requested=False,
                    last_seen_at=now - timedelta(seconds=6),
                ),
                PresenceState(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[1].id,
                    status=PresenceStatus.ACTIVE,
                    task_progress=67,
                    help_requested=True,
                    last_seen_at=now - timedelta(seconds=10),
                ),
                PresenceState(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[2].id,
                    status=PresenceStatus.IDLE,
                    task_progress=28,
                    help_requested=False,
                    last_seen_at=now - timedelta(seconds=32),
                ),
            ]
        )
        db.add_all(
            [
                AttendanceRecord(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[0].id,
                    status=AttendanceStatus.PRESENT,
                    marked_by_user_id=teacher_b.id,
                    marked_at=now - timedelta(minutes=10),
                ),
                AttendanceRecord(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[1].id,
                    status=AttendanceStatus.PRESENT,
                    marked_by_user_id=teacher_b.id,
                    marked_at=now - timedelta(minutes=9),
                ),
                AttendanceRecord(
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[2].id,
                    status=AttendanceStatus.LATE,
                    note="调试传感器后进入课堂",
                    marked_by_user_id=teacher_b.id,
                    marked_at=now - timedelta(minutes=6),
                ),
            ]
        )

        reviewed_submission_b = Submission(
            school_id=school_b.id,
            session_id=session_b.id,
            user_id=students_b[0].id,
            title="周同学环境监测记录卡",
            content="我用折线图整理了温湿度变化，发现课前和课后的湿度波动最明显。",
            status=SubmissionStatus.REVIEWED,
            version=1,
            draft_saved_at=now - timedelta(minutes=8),
            submitted_at=now - timedelta(minutes=7),
            teacher_feedback="图表选择正确，建议把结论中的‘为什么’写得更完整。",
            review_decision=ReviewDecision.APPROVED,
            reviewed_by_user_id=teacher_b.id,
            reviewed_at=now - timedelta(minutes=3),
        )
        pending_submission_b = Submission(
            school_id=school_b.id,
            session_id=session_b.id,
            user_id=students_b[1].id,
            title="吴同学环境监测记录卡",
            content="我记录了三个时间点的温湿度，但还不确定第二条结论是否足够清楚。",
            status=SubmissionStatus.SUBMITTED,
            version=1,
            draft_saved_at=now - timedelta(minutes=5),
            submitted_at=now - timedelta(minutes=4),
        )
        draft_submission_b = Submission(
            school_id=school_b.id,
            session_id=session_b.id,
            user_id=students_b[2].id,
            title="郑同学环境监测草稿",
            content="我已经整理好数据，准备再补一张柱状图比较三个时段。",
            status=SubmissionStatus.DRAFT,
            version=1,
            draft_saved_at=now - timedelta(minutes=2),
        )
        db.add_all([reviewed_submission_b, pending_submission_b, draft_submission_b])
        db.flush()

        db.add_all(
            [
                SubmissionRevision(
                    submission_id=reviewed_submission_b.id,
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[0].id,
                    version=1,
                    title=reviewed_submission_b.title,
                    content=reviewed_submission_b.content,
                    action=SubmissionRevisionAction.SUBMITTED,
                    created_at=now - timedelta(minutes=7),
                ),
                SubmissionRevision(
                    submission_id=pending_submission_b.id,
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[1].id,
                    version=1,
                    title=pending_submission_b.title,
                    content=pending_submission_b.content,
                    action=SubmissionRevisionAction.SUBMITTED,
                    created_at=now - timedelta(minutes=4),
                ),
                SubmissionRevision(
                    submission_id=draft_submission_b.id,
                    school_id=school_b.id,
                    session_id=session_b.id,
                    user_id=students_b[2].id,
                    version=1,
                    title=draft_submission_b.title,
                    content=draft_submission_b.content,
                    action=SubmissionRevisionAction.DRAFT_SAVED,
                    created_at=now - timedelta(minutes=2),
                ),
            ]
        )

        db.add(
            SubmissionReview(
                submission_id=reviewed_submission_b.id,
                school_id=school_b.id,
                session_id=session_b.id,
                reviewer_user_id=teacher_b.id,
                decision=ReviewDecision.APPROVED,
                feedback=reviewed_submission_b.teacher_feedback or "",
                ai_draft_content="优点：图表选择准确。建议：补充结论背后的采集依据，让表达更完整。",
                created_at=now - timedelta(minutes=3),
                updated_at=now - timedelta(minutes=3),
            )
        )

        db.add(
            HelpRequest(
                school_id=school_b.id,
                session_id=session_b.id,
                user_id=students_b[1].id,
                message="老师，我的第二条结论是不是要再补原因说明？",
                status="open",
            )
        )

        batch_b = MigrationBatch(
            school_id=school_b.id,
            name="2026 春季第二校导入批次",
            status=MigrationStatus.COMPLETED,
            progress=100,
            current_step="第二所学校基础数据已导入完成，等待抽样核验。",
            error_count=0,
        )
        db.add(batch_b)
        db.flush()

        db.add_all(
            [
                MigrationPreviewItem(
                    batch_id=batch_b.id,
                    field_name="班级",
                    legacy_value="7.2",
                    new_value="七年级 2 班",
                    status="mapped",
                    issue_detail="旧系统班级编码已映射到第二校新班级。",
                    resolution_note="沿用七年级 2 班作为目标班级。",
                ),
                MigrationPreviewItem(
                    batch_id=batch_b.id,
                    field_name="教师账号",
                    legacy_value="old-linhua",
                    new_value="linhua",
                    status="resolved",
                    issue_detail="旧教师账号已手动映射到新平台教师账号。",
                    resolution_note="确认由林华老师承接原课堂数据。",
                    resolved_by_user_id=admin_b.id,
                    resolved_at=now - timedelta(minutes=20),
                ),
            ]
        )
        db.add_all(
            [
                LegacyIdMapping(
                    batch_id=batch_b.id,
                    school_id=school_b.id,
                    entity_type="classroom",
                    legacy_id="7.2",
                    new_id="七年级 2 班",
                    active=True,
                ),
                LegacyIdMapping(
                    batch_id=batch_b.id,
                    school_id=school_b.id,
                    entity_type="teacher",
                    legacy_id="old-linhua",
                    new_id="linhua",
                    active=True,
                ),
            ]
        )

        db.add(
            AISuggestionDraft(
                school_id=school_b.id,
                teacher_id=teacher_b.id,
                session_id=session_b.id,
                draft_type="活动建议",
                title="第二校传感器课堂建议",
                content="建议先让学生分组校准传感器，再对比三次采集结果，最后集中讨论异常值出现的原因。",
                status="draft",
            )
        )
        changed = (
            _ensure_session_reflection(
                db,
                school_id=school_b.id,
                session_id=session_b.id,
                teacher_id=teacher_b.id,
                strengths="本节课学生已经完成传感器数据采集与第一轮表达，整体参与度较高。",
                risks="仍有学生在图表结论表达上不够完整，且有 1 名学生在课堂中途持续求助。",
                next_actions="下节课先补 3 分钟结论写法示范，再安排小组互查异常值。",
                student_support_plan="优先跟进求助学生和进度停滞学生，对完成较好的学生引导其做同伴示范。",
                ai_draft_content="课堂亮点：学生已能完成基础数据采集与图表整理。\n课堂风险：结论表达仍不稳定，存在持续求助学生。\n下一步动作：补示范、做互查、再收一次改进版作品。\n学生支持计划：优先照看求助和停滞学生。",
            )
            or changed
        )
        changed = True

    teacher_b, teacher_b_changed = _ensure_demo_user(
        db,
        school_id=school_b.id,
        username="linhua",
        display_name="林华老师",
        password="222221",
        role=UserRole.TEACHER,
    )
    changed = teacher_b_changed or changed
    _, admin_b_changed = _ensure_demo_user(
        db,
        school_id=school_b.id,
        username="adminb",
        display_name="未来学校管理员",
        password="222221",
        role=UserRole.SCHOOL_ADMIN,
    )
    changed = admin_b_changed or changed
    for username, display_name in [
        ("250201", "周同学"),
        ("250202", "吴同学"),
        ("250203", "郑同学"),
    ]:
        _, student_b_changed = _ensure_demo_user(
            db,
            school_id=school_b.id,
            classroom_id=class_b1.id,
            username=username,
            display_name=display_name,
            password="12345",
            role=UserRole.STUDENT,
        )
        changed = student_b_changed or changed

    if teacher_b is not None and not created_school_b_demo:
        changed = (
            _ensure_teacher_classroom_assignments(
                db,
                school_id=school_b.id,
                teacher_id=teacher_b.id,
                classroom_ids=[class_b1.id],
            )
            or changed
        )
        changed = (
            _ensure_learning_resource(
                db,
                school=school_b,
                uploader=teacher_b,
                category_id=school_b_resource_categories["自主学习"].id,
                classroom_id=class_b1.id,
                title="传感器课堂记录卡示例",
                description="给七年级 2 班学生的传感器记录卡示例，便于课前预习。",
                audience=ResourceAudience.STUDENT,
                original_filename="sensor-demo-note.txt",
                file_body="温度：\\n湿度：\\n图表草图：\\n结论：\\n",
            )
            or changed
        )
        session_b_existing = db.scalar(
            select(ClassSession)
            .where(
                ClassSession.school_id == school_b.id,
                ClassSession.teacher_id == teacher_b.id,
            )
            .order_by(ClassSession.started_at.desc())
        )
        if session_b_existing is not None:
            changed = (
                _ensure_session_reflection(
                    db,
                    school_id=school_b.id,
                    session_id=session_b_existing.id,
                    teacher_id=teacher_b.id,
                    strengths="本节课学生已经完成基础采集与第一轮图表整理，课堂参与度整体较高。",
                    risks="部分学生仍在结论表达环节停滞，持续求助学生需要优先跟进。",
                    next_actions="下节课先补结论写法示范，再安排同伴互查和二次提交。",
                    student_support_plan="优先巡看求助和停滞学生，对完成较好的学生安排示范分享。",
                    ai_draft_content="课堂亮点：学生已能完成基础采集与图表整理。\n课堂风险：结论表达还不稳定，存在持续求助学生。\n下一步动作：补示范、做互查、再收一次改进版作品。\n学生支持计划：优先照看求助和停滞学生。",
                )
                or changed
            )

    for course in db.scalars(select(Course).where(Course.school_id == school_a.id)).all():
        if course.title == "浜哄伐鏅鸿兘鎶€鏈熀纭€":
            changed = (
                _ensure_course_activity(
                    db,
                    course=course,
                    position=1,
                    title="课堂热身与观察说明",
                    activity_type=CourseActivityType.RICH_TEXT,
                    summary="先读任务背景，再进入数据观察。",
                    instructions_html="<p>先阅读任务背景，明确本节课的观察目标和数据采集方式。</p>",
                )
                or changed
            )
            changed = (
                _ensure_course_activity(
                    db,
                    course=course,
                    position=2,
                    title="图表整理与结论撰写",
                    activity_type=CourseActivityType.RICH_TEXT,
                    summary="将数据整理成图表，并完成书面结论。",
                    instructions_html="<p>把采集结果整理为图表，并写出至少两条基于数据的结论。</p>",
                )
                or changed
            )
        elif course.title == "缃戦〉璁捐鍏ラ棬":
            changed = (
                _ensure_course_activity(
                    db,
                    course=course,
                    position=1,
                    title="信息卡片结构设计",
                    activity_type=CourseActivityType.RICH_TEXT,
                    summary="先梳理页面信息层级。",
                    instructions_html="<p>确定标题、主图、描述和行动按钮的层级，再开始布局。</p>",
                )
                or changed
            )
            changed = (
                _ensure_course_activity(
                    db,
                    course=course,
                    position=2,
                    title="交互网页任务",
                    activity_type=CourseActivityType.INTERACTIVE_PAGE,
                    summary="教师可上传 HTML/ZIP 作为交互网页任务。",
                    instructions_html="<p>上传交互网页后，学生可以在作业详情页直接打开并提交 JSON 数据。</p>",
                )
                or changed
            )

    if changed:
        db.commit()


def seed_demo_data(db: Session) -> None:
    existing_school = db.scalar(select(School).limit(1))
    if existing_school:
        _ensure_multi_school_demo_data(db)
        return

    default_resource_categories = [
        ("课堂模板", "适合学生直接下载并在课堂中填写的任务模板。", 1, True),
        ("讲义课件", "用于课堂讲解、投屏展示或课后回看的讲义与课件。", 2, True),
        ("示例作品", "供学生参考的优秀样例、范文或演示结果。", 3, True),
        ("自主学习", "适合学生课前预习或课后拓展阅读的资料。", 4, True),
        ("教师备课", "教师内部可见的备课材料、清单与讲解脚本。", 5, True),
    ]

    school_a = School(
        code="school-a",
        name="实验学校 A",
        city="深圳",
        slogan="面向信息科技课堂的教学门户平台",
        theme_style=ThemeStyle.WORKSHOP,
    )
    school_b = School(
        code="school-b",
        name="未来学校 B",
        city="杭州",
        slogan="多学校门户接入的第二套演示样板",
        theme_style=ThemeStyle.NATURAL,
    )
    db.add_all([school_a, school_b])
    db.flush()

    class_a1 = Classroom(school_id=school_a.id, name="八年级 1 班", grade_label="八年级")
    class_a2 = Classroom(school_id=school_a.id, name="八年级 2 班", grade_label="八年级")
    class_b1 = Classroom(school_id=school_b.id, name="七年级 2 班", grade_label="七年级")
    db.add_all([class_a1, class_a2, class_b1])
    db.flush()

    _ensure_terms(
        db,
        school_id=school_a.id,
        terms=[
            ("2025-2026", "2025 秋季学期", date(2025, 9, 1), date(2026, 1, 20), False, 1),
            ("2025-2026", "2026 春季学期", date(2026, 2, 18), date(2026, 7, 10), True, 2),
        ],
    )
    _ensure_terms(
        db,
        school_id=school_b.id,
        terms=[
            ("2025-2026", "2025 秋季学期", date(2025, 9, 1), date(2026, 1, 18), False, 1),
            ("2025-2026", "2026 春季学期", date(2026, 2, 20), date(2026, 7, 12), True, 2),
        ],
    )

    teacher = User(
        school_id=school_a.id,
        username="kylin",
        display_name="Kylin 老师",
        password_hash=hash_password("222221"),
        role=UserRole.TEACHER,
    )
    admin = User(
        school_id=school_a.id,
        username="admin",
        display_name="学校管理员",
        password_hash=hash_password("222221"),
        role=UserRole.SCHOOL_ADMIN,
    )
    students = [
        User(
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username="240101",
            display_name="李同学",
            password_hash=hash_password("12345"),
            role=UserRole.STUDENT,
        ),
        User(
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username="240102",
            display_name="王同学",
            password_hash=hash_password("12345"),
            role=UserRole.STUDENT,
        ),
        User(
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username="240103",
            display_name="张同学",
            password_hash=hash_password("12345"),
            role=UserRole.STUDENT,
        ),
        User(
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username="240104",
            display_name="陈同学",
            password_hash=hash_password("12345"),
            role=UserRole.STUDENT,
        ),
        User(
            school_id=school_a.id,
            classroom_id=class_a1.id,
            username="240105",
            display_name="赵同学",
            password_hash=hash_password("12345"),
            role=UserRole.STUDENT,
        ),
    ]

    db.add_all([teacher, admin, *students])
    db.flush()
    school_a_resource_categories = _ensure_resource_categories(
        db,
        school_id=school_a.id,
        categories=default_resource_categories,
    )
    _ensure_teacher_classroom_assignments(
        db,
        school_id=school_a.id,
        teacher_id=teacher.id,
        classroom_ids=[class_a1.id],
    )
    _ensure_learning_resource(
        db,
        school=school_a,
        uploader=teacher,
        category_id=school_a_resource_categories["课堂模板"].id,
        classroom_id=class_a1.id,
        title="数据采集观察模板",
        description="给八年级 1 班学生的课堂观察模板，帮助整理图表和结论。",
        audience=ResourceAudience.STUDENT,
        original_filename="data-observation-template.txt",
        file_body="1. 记录课堂采集到的数据\n2. 描述图表中的变化趋势\n3. 写出至少两条结论\n",
    )

    course_ai = Course(
        school_id=school_a.id,
        title="人工智能技术基础",
        stage_label="第 3 课 · 数据采集与图表作品",
        overview="通过课堂数据采集和图表整理，训练学生的数据观察与结论表达能力。",
        assignment_title="课堂图表作品提交",
        assignment_prompt="请根据课堂采集到的数据，整理一份图表作品，并说明你从数据中观察到的规律。",
        is_published=True,
        published_at=utc_now() - timedelta(days=10),
    )
    course_web = Course(
        school_id=school_a.id,
        title="网页设计入门",
        stage_label="第 2 课 · 信息卡片页面排版",
        overview="围绕页面信息层级、图片区和说明文案布局，完成一张课堂信息卡片。",
        assignment_title="信息卡片页面草稿",
        assignment_prompt="完成一个包含标题、图片区和说明文字的信息卡片页面，并保存为课堂草稿。",
        is_published=True,
        published_at=utc_now() - timedelta(days=8),
    )
    db.add_all([course_ai, course_web])
    db.flush()

    session = ClassSession(
        school_id=school_a.id,
        classroom_id=class_a1.id,
        course_id=course_ai.id,
        teacher_id=teacher.id,
        title=course_ai.title,
        stage=course_ai.stage_label,
        status="active",
        expected_students=len(students),
        started_at=utc_now() - timedelta(minutes=18),
    )
    db.add(session)
    db.flush()

    now = utc_now()
    presence_rows = [
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[0].id,
            status=PresenceStatus.ACTIVE,
            task_progress=88,
            help_requested=False,
            last_seen_at=now,
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[1].id,
            status=PresenceStatus.ACTIVE,
            task_progress=100,
            help_requested=True,
            last_seen_at=now - timedelta(seconds=10),
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[2].id,
            status=PresenceStatus.IDLE,
            task_progress=42,
            help_requested=False,
            last_seen_at=now - timedelta(seconds=36),
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[3].id,
            status=PresenceStatus.NOT_STARTED,
            task_progress=0,
            help_requested=False,
            last_seen_at=now - timedelta(seconds=18),
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[4].id,
            status=PresenceStatus.OFFLINE,
            task_progress=0,
            help_requested=False,
            last_seen_at=now - timedelta(minutes=2),
        ),
    ]
    db.add_all(presence_rows)

    attendance_rows = [
        AttendanceRecord(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[0].id,
            status=AttendanceStatus.PRESENT,
            marked_by_user_id=teacher.id,
            marked_at=now - timedelta(minutes=15),
        ),
        AttendanceRecord(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[1].id,
            status=AttendanceStatus.PRESENT,
            marked_by_user_id=teacher.id,
            marked_at=now - timedelta(minutes=14),
        ),
        AttendanceRecord(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[2].id,
            status=AttendanceStatus.LATE,
            note="迟到后已进入课堂",
            marked_by_user_id=teacher.id,
            marked_at=now - timedelta(minutes=8),
        ),
        AttendanceRecord(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[3].id,
            status=AttendanceStatus.PENDING,
        ),
        AttendanceRecord(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[4].id,
            status=AttendanceStatus.ABSENT,
            note="机房网络异常",
            marked_by_user_id=teacher.id,
            marked_at=now - timedelta(minutes=6),
        ),
    ]
    db.add_all(attendance_rows)

    reviewed_submission = Submission(
        school_id=school_a.id,
        session_id=session.id,
        user_id=students[0].id,
        title="李同学图表作品",
        content="我整理了温度与湿度数据，补充了折线图，并写出了温度在中午后快速上升的原因。",
        status=SubmissionStatus.REVIEWED,
        version=2,
        draft_saved_at=now - timedelta(minutes=7),
        submitted_at=now - timedelta(minutes=6),
        teacher_feedback="图表主体已经完成，但结论还可以更具体。请再补 1 条数据观察和 1 条课堂结论后重新提交。",
        review_decision=ReviewDecision.REVISION_REQUESTED,
        reviewed_by_user_id=teacher.id,
        reviewed_at=now - timedelta(minutes=3),
    )
    pending_review_submission = Submission(
        school_id=school_a.id,
        session_id=session.id,
        user_id=students[1].id,
        title="王同学图表作品",
        content="我完成了折线图和结论说明，观察到中午之后温度开始快速上升，但不确定结论是否写完整。",
        status=SubmissionStatus.SUBMITTED,
        version=1,
        draft_saved_at=now - timedelta(minutes=5),
        submitted_at=now - timedelta(minutes=4),
    )
    draft_submission = Submission(
        school_id=school_a.id,
        session_id=session.id,
        user_id=students[2].id,
        title="张同学图表草稿",
        content="我先整理了采集表格，准备再补一张柱状图说明变化趋势。",
        status=SubmissionStatus.DRAFT,
        version=1,
        draft_saved_at=now - timedelta(minutes=2),
    )
    db.add_all([reviewed_submission, pending_review_submission, draft_submission])
    db.flush()

    db.add_all(
        [
            SubmissionRevision(
                submission_id=reviewed_submission.id,
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[0].id,
                version=1,
                title="李同学图表作品",
                content="我先把温度和湿度表格整理好了，正在补充图表说明。",
                action=SubmissionRevisionAction.DRAFT_SAVED,
                created_at=now - timedelta(minutes=12),
            ),
            SubmissionRevision(
                submission_id=reviewed_submission.id,
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[0].id,
                version=2,
                title="李同学图表作品",
                content=reviewed_submission.content,
                action=SubmissionRevisionAction.SUBMITTED,
                created_at=now - timedelta(minutes=6),
            ),
            SubmissionRevision(
                submission_id=pending_review_submission.id,
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[1].id,
                version=1,
                title="王同学图表作品",
                content=pending_review_submission.content,
                action=SubmissionRevisionAction.SUBMITTED,
                created_at=now - timedelta(minutes=4),
            ),
            SubmissionRevision(
                submission_id=draft_submission.id,
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[2].id,
                version=1,
                title="张同学图表草稿",
                content=draft_submission.content,
                action=SubmissionRevisionAction.DRAFT_SAVED,
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )

    db.add(
        SubmissionReview(
            submission_id=reviewed_submission.id,
            school_id=school_a.id,
            session_id=session.id,
            reviewer_user_id=teacher.id,
            decision=ReviewDecision.REVISION_REQUESTED,
            feedback=reviewed_submission.teacher_feedback or "",
            ai_draft_content="优点：图表主体完整。建议：把结论写得更具体，补充数据依据后再提交。",
            created_at=now - timedelta(minutes=3),
            updated_at=now - timedelta(minutes=3),
        )
    )

    db.add(
        HelpRequest(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[1].id,
            message="老师，我的图表结论不确定是不是写完整了，能帮我看一下吗？",
            status="open",
        )
    )

    batch = MigrationBatch(
        school_id=school_a.id,
        name="2026 春季旧模板迁移批次",
        status=MigrationStatus.PREVIEWED,
        progress=68,
        current_step="已完成字段预检，等待人工修复预览问题后执行。",
        error_count=1,
    )
    db.add(batch)
    db.flush()

    db.add_all(
        [
            MigrationPreviewItem(
                batch_id=batch.id,
                field_name="班级",
                legacy_value="8.1",
                new_value="八年级 1 班",
                status="mapped",
                issue_detail="旧系统班级编码已成功映射到新班级名称。",
            ),
            MigrationPreviewItem(
                batch_id=batch.id,
                field_name="学号映射",
                legacy_value="legacy-001",
                new_value="240101",
                status="mapped",
                issue_detail="旧学号与新学号已建立一对一映射。",
            ),
            MigrationPreviewItem(
                batch_id=batch.id,
                field_name="缺失教师",
                legacy_value="旧教师 A",
                new_value="未匹配",
                status="warning",
                issue_detail="旧模板中的授课教师名称无法自动匹配，请手工指定新系统教师账号。",
            ),
        ]
    )

    db.add(
        AISuggestionDraft(
            school_id=school_a.id,
            teacher_id=teacher.id,
            session_id=session.id,
            draft_type="活动建议",
            title="数据采集课堂活动建议",
            content="建议把全班分成采集组、整理组、展示组，先完成 8 分钟采集，再集中展示结果差异。",
            status="draft",
        )
    )
    _ensure_session_reflection(
        db,
        school_id=school_a.id,
        session_id=session.id,
        teacher_id=teacher.id,
        strengths="课堂主线清楚，大部分学生已经进入图表整理与结论表达阶段。",
        risks="仍有学生未开始或处于离线状态，部分作品结论表达还不够具体。",
        next_actions="下一次上课先做结论示范，再快速回看常见错误，最后安排作品二次提交。",
        student_support_plan="优先处理正在求助和需要修改后重交的学生，对完成较好的学生安排示范分享。",
        ai_draft_content="课堂亮点：学生已进入图表任务主线，作品开始成形。\n课堂风险：仍有停滞和离线学生，部分结论表达偏弱。\n下一步动作：先做结论示范，再组织重交与讲评。\n学生支持计划：优先跟进求助和重交学生。",
    )

    db.commit()
    _ensure_multi_school_demo_data(db)
