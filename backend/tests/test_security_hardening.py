from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.auth import SESSION_STORE


def test_session_tokens_in_query_string_are_rejected(client, login):
    _, session_payload = login(
        role="student",
        school_code="school-a",
        username="240101",
        password="12345",
    )
    token = session_payload["session"]["token"]

    response = client.get(f"/api/auth/me?token={token}")

    assert response.status_code == 401


def test_authenticated_student_resource_download_still_works(client, login):
    headers, _ = login(
        role="student",
        school_code="school-a",
        username="240101",
        password="12345",
    )
    home_response = client.get("/api/student/home", headers=headers)
    assert home_response.status_code == 200
    resources = home_response.json()["resources"]
    assert resources

    download_response = client.get(
        f"/api/student/resources/{resources[0]['id']}/download",
        headers=headers,
    )

    assert download_response.status_code == 200
    assert download_response.headers["content-disposition"].startswith("attachment;")


def test_only_platform_admin_can_manage_sqlite_backups(client, login):
    school_admin_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="admin",
        password="222221",
    )

    forbidden_create = client.post(
        "/api/admin/backups",
        headers=school_admin_headers,
        json={"note": "school admin should be blocked"},
    )
    assert forbidden_create.status_code == 403
    assert "platform admins" in forbidden_create.json()["detail"]

    platform_admin_headers, _ = login(
        role="teacher",
        school_code="school-a",
        username="platform",
        password="222221",
    )
    allowed_create = client.post(
        "/api/admin/backups",
        headers=platform_admin_headers,
        json={"note": "platform admin backup"},
    )
    assert allowed_create.status_code == 200
    snapshot_id = allowed_create.json()["backup_snapshots"][0]["id"]

    forbidden_restore = client.post(
        f"/api/admin/backups/{snapshot_id}/restore",
        headers=school_admin_headers,
    )
    assert forbidden_restore.status_code == 403
    assert "platform admins" in forbidden_restore.json()["detail"]


def test_logout_revokes_active_session(client, login):
    headers, session_payload = login(
        role="student",
        school_code="school-a",
        username="240101",
        password="12345",
    )
    token = session_payload["session"]["token"]

    logout_response = client.post("/api/auth/logout", headers=headers)

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Signed out successfully."
    assert token not in SESSION_STORE

    me_response = client.get("/api/auth/me", headers=headers)

    assert me_response.status_code == 401


def test_expired_session_is_rejected_and_revoked(client, login):
    headers, session_payload = login(
        role="teacher",
        school_code="school-a",
        username="kylin",
        password="222221",
    )
    token = session_payload["session"]["token"]
    SESSION_STORE[token].expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    me_response = client.get("/api/auth/me", headers=headers)

    assert me_response.status_code == 401
    assert me_response.json()["detail"] == "Session expired. Please sign in again."
    assert token not in SESSION_STORE
