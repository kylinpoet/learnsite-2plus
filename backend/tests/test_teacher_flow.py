from __future__ import annotations


def test_teacher_can_start_class_and_review_submission(client, login):
    teacher_headers, teacher_session = login(
        role="teacher",
        school_code="school-a",
        username="kylin",
        password="222221",
    )
    assert teacher_session["session"]["role"] == "teacher"

    teacher_console = client.get("/api/teacher/console", headers=teacher_headers)
    assert teacher_console.status_code == 200
    launch_options = teacher_console.json()["launch_options"]
    assert launch_options
    launch_option = launch_options[0]

    start_response = client.post(
        "/api/teacher/session/start",
        headers=teacher_headers,
        json={
            "classroom_id": launch_option["classroom_id"],
            "course_id": launch_option["course_id"],
        },
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["session_id"] is not None
    assert start_payload["radar"]["expected"] >= 1
    assert start_payload["radar"]["not_started"] == start_payload["radar"]["expected"]

    student_headers, _ = login(
        role="student",
        school_code="school-a",
        username="240104",
        password="12345",
    )
    heartbeat_response = client.post(
        "/api/student/heartbeat",
        headers=student_headers,
        json={"task_progress": 60},
    )
    assert heartbeat_response.status_code == 200

    help_response = client.post(
        "/api/student/help-requests",
        headers=student_headers,
        json={"message": "老师，我想确认图表结论是否完整。"},
    )
    assert help_response.status_code == 200

    help_console = client.get("/api/teacher/console", headers=teacher_headers)
    assert help_console.status_code == 200
    help_payload = help_console.json()
    assert help_payload["radar"]["help_requests"] >= 1

    help_roster_row = next(
        row for row in help_payload["student_roster"] if row["student_username"] == "240104"
    )
    assert help_roster_row["help_requested"] is True

    submit_response = client.post(
        "/api/student/submission/submit",
        headers=student_headers,
        json={
            "title": "240104 图表作品",
            "content": "我已经补充了图表和两条课堂结论，请老师查看。",
        },
    )
    assert submit_response.status_code == 200

    refreshed_console = client.get("/api/teacher/console", headers=teacher_headers)
    assert refreshed_console.status_code == 200
    refreshed_payload = refreshed_console.json()
    assert refreshed_payload["radar"]["online"] >= 1
    assert refreshed_payload["radar"]["not_started"] == refreshed_payload["radar"]["expected"] - 1

    roster_row = next(
        row for row in refreshed_payload["student_roster"] if row["student_username"] == "240104"
    )
    assert roster_row["attendance_status"] == "present"
    assert roster_row["presence_status"] == "active"
    assert roster_row["help_requested"] is False
    assert roster_row["submission_status"] == "submitted"

    queue_item = next(
        item for item in refreshed_payload["submissions"] if item["student_username"] == "240104"
    )
    assert queue_item["help_requested"] is False
    assert queue_item["status"] == "submitted"

    detail_response = client.get(
        f"/api/teacher/submissions/{queue_item['id']}",
        headers=teacher_headers,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["student_username"] == "240104"
    assert len(detail_payload["help_messages"]) >= 1

    draft_response = client.post(
        f"/api/teacher/submissions/{queue_item['id']}/feedback-draft",
        headers=teacher_headers,
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["draft"]["status"] == "draft"

    review_response = client.post(
        f"/api/teacher/submissions/{queue_item['id']}/review",
        headers=teacher_headers,
        json={
            "decision": "revision_requested",
            "feedback": "图表主体已经完整，请再把数据依据写具体一点。",
            "resolve_help_requests": True,
        },
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["status"] == "reviewed"
    assert review_payload["review_decision"] == "revision_requested"
    assert review_payload["teacher_feedback"].startswith("图表主体已经完整")

    student_home = client.get("/api/student/home", headers=student_headers)
    assert student_home.status_code == 200
    student_payload = student_home.json()
    assert student_payload["submission"]["status"] == "reviewed"
    assert student_payload["submission"]["review_decision"] == "revision_requested"
    assert student_payload["submission"]["can_edit"] is True
    assert student_payload["help_open"] is False


def test_teacher_ai_draft_workflow_is_audited(client, login):
    teacher_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="kylin",
        password="222221",
    )

    teacher_console = client.get("/api/teacher/console", headers=teacher_headers)
    assert teacher_console.status_code == 200
    teacher_payload = teacher_console.json()
    if teacher_payload["session_id"] is None:
        launch_option = teacher_payload["launch_options"][0]
        start_response = client.post(
            "/api/teacher/session/start",
            headers=teacher_headers,
            json={
                "classroom_id": launch_option["classroom_id"],
                "course_id": launch_option["course_id"],
            },
        )
        assert start_response.status_code == 200

    create_response = client.post(
        "/api/teacher/ai/drafts",
        headers=teacher_headers,
        json={"goal": "生成一份分层课堂活动建议"},
    )
    assert create_response.status_code == 200
    created_draft = create_response.json()["draft"]
    assert created_draft["status"] == "draft"

    save_response = client.post(
        f"/api/teacher/ai/drafts/{created_draft['id']}/save",
        headers=teacher_headers,
        json={
            "title": "已整理的 AI 课堂建议",
            "content": "先用 5 分钟完成数据观察，再用 8 分钟进行小组讨论，最后集中展示易错点。",
        },
    )
    assert save_response.status_code == 200
    saved_draft = save_response.json()
    assert saved_draft["status"] == "draft"
    assert saved_draft["title"] == "已整理的 AI 课堂建议"

    accept_response = client.post(
        f"/api/teacher/ai/drafts/{created_draft['id']}/accept",
        headers=teacher_headers,
        json={
            "title": "已采纳的 AI 课堂建议",
            "content": "课堂先完成数据观察，再进行分层讨论，最后由教师统一示范结论写法。",
        },
    )
    assert accept_response.status_code == 200
    accepted_draft = accept_response.json()
    assert accepted_draft["status"] == "accepted"
    assert accepted_draft["title"] == "已采纳的 AI 课堂建议"

    reject_create_response = client.post(
        "/api/teacher/ai/drafts",
        headers=teacher_headers,
        json={"goal": "再生成一份备用建议"},
    )
    assert reject_create_response.status_code == 200
    rejected_draft_id = reject_create_response.json()["draft"]["id"]

    reject_response = client.post(
        f"/api/teacher/ai/drafts/{rejected_draft_id}/reject",
        headers=teacher_headers,
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    refreshed_console = client.get("/api/teacher/console", headers=teacher_headers)
    assert refreshed_console.status_code == 200
    drafts_by_id = {draft["id"]: draft for draft in refreshed_console.json()["ai_drafts"]}
    assert drafts_by_id[created_draft["id"]]["status"] == "accepted"
    assert drafts_by_id[rejected_draft_id]["status"] == "rejected"

    admin_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="admin",
        password="222221",
    )
    admin_overview = client.get("/api/admin/overview", headers=admin_headers)
    assert admin_overview.status_code == 200
    audit_actions = [log["action"] for log in admin_overview.json()["recent_audit_logs"]]
    assert "teacher_ai_draft_created" in audit_actions
    assert "teacher_ai_draft_updated" in audit_actions
    assert "teacher_ai_draft_accepted" in audit_actions
    assert "teacher_ai_draft_rejected" in audit_actions
