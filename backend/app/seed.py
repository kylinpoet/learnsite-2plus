from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.auth import hash_password
from .models import (
    AISuggestionDraft,
    AttendanceRecord,
    AttendanceStatus,
    ClassSession,
    Classroom,
    Course,
    HelpRequest,
    LegacyIdMapping,
    MigrationBatch,
    MigrationPreviewItem,
    MigrationStatus,
    PresenceState,
    PresenceStatus,
    ReviewDecision,
    School,
    Submission,
    SubmissionRevision,
    SubmissionRevisionAction,
    SubmissionReview,
    SubmissionStatus,
    ThemeStyle,
    User,
    UserRole,
)


def _ensure_multi_school_demo_data(db: Session) -> None:
    changed = False

    school_a = db.scalar(select(School).where(School.code == "school-a"))
    if school_a is None:
        return

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
    if teacher_b is None:
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

        course_robot = Course(
            school_id=school_b.id,
            title="智能硬件与传感器",
            stage_label="第 1 课 · 环境监测仪表板",
            assignment_title="传感器课堂记录卡",
            assignment_prompt="整理本节课的温湿度采集结果，用 1 张图表和 2 条结论说明你的观察。",
        )
        course_data = Course(
            school_id=school_b.id,
            title="数据表达与可视化",
            stage_label="第 2 课 · 班级数据小报",
            assignment_title="班级数据小报草稿",
            assignment_prompt="把课堂调查结果整理成小报，包含标题、图表、说明文字和一个结论。",
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
            started_at=datetime.utcnow() - timedelta(minutes=12),
        )
        db.add(session_b)
        db.flush()

        now = datetime.utcnow()
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
        changed = True

    if changed:
        db.commit()


def seed_demo_data(db: Session) -> None:
    existing_school = db.scalar(select(School).limit(1))
    if existing_school:
        _ensure_multi_school_demo_data(db)
        return

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

    course_ai = Course(
        school_id=school_a.id,
        title="人工智能技术基础",
        stage_label="第 3 课 · 数据采集与图表作品",
        assignment_title="课堂图表作品提交",
        assignment_prompt="请根据课堂采集到的数据，整理一份图表作品，并说明你从数据中观察到的规律。",
    )
    course_web = Course(
        school_id=school_a.id,
        title="网页设计入门",
        stage_label="第 2 课 · 信息卡片页面排版",
        assignment_title="信息卡片页面草稿",
        assignment_prompt="完成一个包含标题、图片区和说明文字的信息卡片页面，并保存为课堂草稿。",
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
        started_at=datetime.utcnow() - timedelta(minutes=18),
    )
    db.add(session)
    db.flush()

    now = datetime.utcnow()
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

    db.commit()
    _ensure_multi_school_demo_data(db)
