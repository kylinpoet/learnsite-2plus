from __future__ import annotations

from sqlalchemy import select

from app.core.auth import hash_password, verify_password
from app.models import AttendanceRecord, HelpRequest, PresenceState, Submission, SubmissionRevision, User
from app.seed import seed_demo_data


def test_seed_reconciles_default_student_demo_account(client, login, db_session):
    student = db_session.scalar(select(User).where(User.username == "240101"))
    assert student is not None
    student.password_hash = hash_password("mismatch-password")
    db_session.commit()

    seed_demo_data(db_session)
    db_session.refresh(student)

    assert verify_password("12345", student.password_hash) is True

    headers, session_payload = login(
        role="student",
        school_code="school-a",
        username="240101",
        password="12345",
    )
    assert headers["Authorization"].startswith("Bearer ")
    assert session_payload["session"]["username"] == "240101"
    assert session_payload["redirect_path"] == "/student/home"


def test_student_can_complete_learning_flow(client, login, db_session):
    headers, session_payload = login(
        role="student",
        school_code="school-a",
        username="240104",
        password="12345",
    )

    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "240104"
    assert session_payload["redirect_path"] == "/student/home"

    initial_home = client.get("/api/student/home", headers=headers)
    assert initial_home.status_code == 200
    initial_payload = initial_home.json()
    assert initial_payload["student_name"]
    assert initial_payload["submission"]["status"] == "draft"
    assert initial_payload["attendance_status"] == "pending"

    heartbeat_response = client.post(
        "/api/student/heartbeat",
        headers=headers,
        json={"task_progress": 45},
    )
    assert heartbeat_response.status_code == 200

    help_response = client.post(
        "/api/student/help-requests",
        headers=headers,
        json={"message": "老师，我想确认图表的结论怎么写。"},
    )
    assert help_response.status_code == 200

    draft_response = client.post(
        "/api/student/submission/draft",
        headers=headers,
        json={
            "title": "240104 课堂图表草稿",
            "content": "先整理采集数据，再补充折线图和结论说明。",
        },
    )
    assert draft_response.status_code == 200
    draft_payload = draft_response.json()
    assert draft_payload["submission"]["status"] == "draft"
    assert draft_payload["submission"]["version"] == 1
    assert draft_payload["submission"]["can_edit"] is True

    submit_response = client.post(
        "/api/student/submission/submit",
        headers=headers,
        json={
            "title": "240104 课堂图表终稿",
            "content": "我补充了折线图，并写出午后温度快速上升的观察结论。",
        },
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["submission"]["status"] == "submitted"
    assert submit_payload["submission"]["version"] == 2
    assert submit_payload["submission"]["can_edit"] is False

    final_home = client.get("/api/student/home", headers=headers)
    assert final_home.status_code == 200
    final_payload = final_home.json()
    assert final_payload["attendance_status"] == "present"
    assert final_payload["help_open"] is False
    assert final_payload["progress_percent"] == 100
    assert final_payload["submission"]["status"] == "submitted"
    assert len(final_payload["submission_history"]) >= 2

    student = db_session.scalar(select(User).where(User.username == "240104"))
    assert student is not None

    attendance = db_session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.user_id == student.id)
    )
    assert attendance is not None
    assert attendance.status.value == "present"

    presence = db_session.scalar(
        select(PresenceState).where(PresenceState.user_id == student.id)
    )
    assert presence is not None
    assert presence.task_progress == 100
    assert presence.help_requested is False

    help_requests = db_session.scalars(
        select(HelpRequest).where(HelpRequest.user_id == student.id)
    ).all()
    assert len(help_requests) == 1
    assert help_requests[0].message.startswith("老师")

    submission = db_session.scalar(
        select(Submission).where(Submission.user_id == student.id)
    )
    assert submission is not None
    assert submission.status.value == "submitted"
    assert submission.version == 2

    revisions = db_session.scalars(
        select(SubmissionRevision)
        .where(SubmissionRevision.submission_id == submission.id)
        .order_by(SubmissionRevision.id)
    ).all()
    assert len(revisions) == 2
    assert [revision.action.value for revision in revisions] == ["draft_saved", "submitted"]
