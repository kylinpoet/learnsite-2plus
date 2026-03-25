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
    MigrationBatch,
    MigrationPreviewItem,
    MigrationStatus,
    PresenceState,
    PresenceStatus,
    School,
    Submission,
    SubmissionStatus,
    ThemeStyle,
    User,
    UserRole,
)


def seed_demo_data(db: Session) -> None:
    existing_school = db.scalar(select(School).limit(1))
    if existing_school:
        return

    school_a = School(
        code="school-a",
        name="实验学校 A",
        city="深圳",
        slogan="面向信息科技课堂的教学操作系统",
        theme_style=ThemeStyle.WORKSHOP,
    )
    school_b = School(
        code="school-b",
        name="未来学校 B",
        city="杭州",
        slogan="多学校门户的第二接入样板",
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
        assignment_prompt="完成一个包含标题、图片区域和说明文字的信息卡片页面，并保存为课堂草稿。",
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
            task_progress=68,
            help_requested=False,
            last_seen_at=now,
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[1].id,
            status=PresenceStatus.ACTIVE,
            task_progress=100,
            help_requested=False,
            last_seen_at=now - timedelta(seconds=10),
        ),
        PresenceState(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[2].id,
            status=PresenceStatus.IDLE,
            task_progress=42,
            help_requested=True,
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

    db.add_all(
        [
            Submission(
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[0].id,
                title="李同学图表草稿",
                content="我先整理了温度与湿度数据，准备再补一张柱状图说明变化趋势。",
                status=SubmissionStatus.DRAFT,
                version=2,
                draft_saved_at=now - timedelta(minutes=3),
            ),
            Submission(
                school_id=school_a.id,
                session_id=session.id,
                user_id=students[1].id,
                title="王同学图表作品",
                content="我完成了折线图和结论说明，观察到中午之后温度开始快速上升。",
                status=SubmissionStatus.SUBMITTED,
                version=1,
                draft_saved_at=now - timedelta(minutes=7),
                submitted_at=now - timedelta(minutes=4),
            ),
        ]
    )

    db.add(
        HelpRequest(
            school_id=school_a.id,
            session_id=session.id,
            user_id=students[2].id,
            message="老师，我不会完成图表的最后一步。",
            status="open",
        )
    )

    batch = MigrationBatch(
        school_id=school_a.id,
        name="2026 春季旧模板迁移批次",
        status=MigrationStatus.PREVIEWED,
        progress=68,
        current_step="已完成字段预检，等待人工确认执行",
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
            ),
            MigrationPreviewItem(
                batch_id=batch.id,
                field_name="学号映射",
                legacy_value="legacy-001",
                new_value="240101",
                status="mapped",
            ),
            MigrationPreviewItem(
                batch_id=batch.id,
                field_name="缺失教师",
                legacy_value="旧教师 A",
                new_value="未匹配",
                status="warning",
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
