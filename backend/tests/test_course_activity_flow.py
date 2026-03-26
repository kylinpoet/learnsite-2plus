from __future__ import annotations

from app.models import Course


def test_teacher_can_save_multi_activity_course_and_reorder(client, login):
    teacher_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="kylin",
        password="222221",
    )

    create_response = client.post(
        "/api/teacher/courses",
        headers=teacher_headers,
        json={
            "title": "多活动课程测试",
            "stage_label": "第 1 课 · 多活动结构",
            "overview": "测试多活动课程创建与排序。",
            "assignment_title": "书面成果提交",
            "assignment_prompt": "完成书面总结并提交。",
            "publish_now": True,
            "activities": [
                {
                    "title": "活动一：观察记录",
                    "activity_type": "rich_text",
                    "summary": "记录课堂观察。",
                    "instructions_html": "<p>先记录关键观察点。</p>",
                },
                {
                    "title": "活动二：互动网页",
                    "activity_type": "interactive_page",
                    "summary": "运行交互网页任务。",
                    "instructions_html": "<p>打开网页并完成交互。</p>",
                },
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    created_course = create_response.json()
    assert created_course["activity_count"] == 2

    detail_response = client.get(f"/api/teacher/courses/{created_course['id']}", headers=teacher_headers)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert [item["title"] for item in detail_payload["activities"]] == ["活动一：观察记录", "活动二：互动网页"]

    first_activity = detail_payload["activities"][0]
    second_activity = detail_payload["activities"][1]

    reorder_response = client.post(
        "/api/teacher/courses",
        headers=teacher_headers,
        json={
            "course_id": created_course["id"],
            "title": "多活动课程测试",
            "stage_label": "第 1 课 · 多活动结构",
            "overview": "测试多活动课程创建与排序。",
            "assignment_title": "书面成果提交",
            "assignment_prompt": "完成书面总结并提交。",
            "publish_now": True,
            "activities": [
                {
                    "id": second_activity["id"],
                    "title": second_activity["title"],
                    "activity_type": second_activity["activity_type"],
                    "summary": second_activity["summary"],
                    "instructions_html": second_activity["instructions_html"],
                },
                {
                    "id": first_activity["id"],
                    "title": first_activity["title"],
                    "activity_type": first_activity["activity_type"],
                    "summary": first_activity["summary"],
                    "instructions_html": first_activity["instructions_html"],
                },
            ],
        },
    )
    assert reorder_response.status_code == 200, reorder_response.text

    reordered_detail = client.get(f"/api/teacher/courses/{created_course['id']}", headers=teacher_headers)
    assert reordered_detail.status_code == 200
    reordered_payload = reordered_detail.json()
    assert [item["title"] for item in reordered_payload["activities"]] == ["活动二：互动网页", "活动一：观察记录"]
    assert [item["position"] for item in reordered_payload["activities"]] == [1, 2]


def test_interactive_activity_upload_and_submission_flow(client, login, db_session):
    teacher_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="kylin",
        password="222221",
    )

    create_response = client.post(
        "/api/teacher/courses",
        headers=teacher_headers,
        json={
            "title": "交互网页活动测试",
            "stage_label": "第 2 课 · 网页互动",
            "overview": "测试交互网页活动上传与提交。",
            "assignment_title": "课堂说明",
            "assignment_prompt": "完成交互网页任务。",
            "publish_now": True,
            "activities": [
                {
                    "title": "互动任务",
                    "activity_type": "interactive_page",
                    "summary": "上传并运行网页。",
                    "instructions_html": "<p>请打开交互网页并完成任务。</p>",
                }
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    course_id = create_response.json()["id"]

    detail_response = client.get(f"/api/teacher/courses/{course_id}", headers=teacher_headers)
    assert detail_response.status_code == 200
    activity = detail_response.json()["activities"][0]

    upload_response = client.post(
        f"/api/teacher/activities/{activity['id']}/interactive-upload",
        headers=teacher_headers,
        files={
            "upload": (
                "interactive.html",
                b"<html><body><button id='submit'>submit</button></body></html>",
                "text/html",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded_activity = upload_response.json()
    assert uploaded_activity["has_interactive_asset"] is True
    assert uploaded_activity["interactive_launch_url"]
    assert uploaded_activity["interactive_submission_api_url"]

    public_page = client.get(uploaded_activity["interactive_launch_url"])
    assert public_page.status_code == 200
    assert "learnsiteSubmit" in public_page.text

    dashboard_response = client.get("/api/teacher/dashboard", headers=teacher_headers)
    assert dashboard_response.status_code == 200
    classroom_id = dashboard_response.json()["managed_classrooms"][0]["id"]

    start_response = client.post(
        "/api/teacher/session/start",
        headers=teacher_headers,
        json={"classroom_id": classroom_id, "course_id": course_id},
    )
    assert start_response.status_code == 200

    student_headers, _ = login(
        role="student",
        school_code="school-a",
        username="240101",
        password="12345",
    )

    student_submission = client.post(
        f"/api/student/activities/{activity['id']}/submissions",
        headers=student_headers,
        json={"score": 98, "answer": "ok"},
    )
    assert student_submission.status_code == 200, student_submission.text
    assert student_submission.json()["submission"]["submitted_by_name"]

    public_submission = client.post(
        uploaded_activity["interactive_submission_api_url"],
        json={"student_name": "外部网页", "payload": {"state": "done"}},
    )
    assert public_submission.status_code == 200, public_submission.text

    refreshed_detail = client.get(f"/api/teacher/courses/{course_id}", headers=teacher_headers)
    assert refreshed_detail.status_code == 200
    refreshed_activity = refreshed_detail.json()["activities"][0]
    assert refreshed_activity["submission_count"] == 2
    assert len(refreshed_activity["recent_submissions"]) == 2

    stored_course = db_session.get(Course, course_id)
    assert stored_course is not None
    assert stored_course.is_published is True
