from __future__ import annotations

from sqlalchemy import select

from app.models import LegacyIdMapping


def test_admin_can_update_school_settings(client, login):
    admin_headers, admin_session = login(
        role="teacher",
        school_code="school-a",
        username="admin",
        password="222221",
    )
    assert admin_session["session"]["role"] == "school_admin"

    update_response = client.post(
        "/api/admin/school-settings",
        headers=admin_headers,
        json={
            "name": "实验学校 A 试点校",
            "city": "上海",
            "slogan": "让课堂更清楚，让学习更有参与感",
            "theme_style": "material",
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["current_school"]["name"] == "实验学校 A 试点校"
    assert payload["current_school"]["city"] == "上海"
    assert payload["current_school"]["slogan"] == "让课堂更清楚，让学习更有参与感"
    assert payload["current_school"]["theme_style"] == "material"
    assert any(log["action"] == "school_settings_updated" for log in payload["recent_audit_logs"])


def test_admin_can_resolve_execute_and_rollback_migration(client, login, db_session):
    admin_headers, admin_session = login(
        role="teacher",
        school_code="school-a",
        username="admin",
        password="222221",
    )
    assert admin_session["session"]["role"] == "school_admin"

    overview_response = client.get("/api/admin/overview", headers=admin_headers)
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["can_execute_migration"] is False
    assert overview_payload["unresolved_preview_count"] == 1

    active_batch = overview_payload["active_migration"]
    unresolved_row = next(row for row in active_batch["preview_rows"] if row["requires_resolution"])

    resolve_response = client.post(
        f"/api/admin/migrations/{active_batch['id']}/preview-items/{unresolved_row['id']}/resolve",
        headers=admin_headers,
        json={
            "new_value": "kylin",
            "resolution_note": "将旧教师名称映射到当前教师账号。",
            "status": "resolved",
        },
    )
    assert resolve_response.status_code == 200
    resolved_payload = resolve_response.json()
    assert resolved_payload["unresolved_preview_count"] == 0
    assert resolved_payload["can_execute_migration"] is True
    assert resolved_payload["active_migration"]["status"] == "previewed"

    execute_response = client.post(
        f"/api/admin/migrations/{active_batch['id']}/execute",
        headers=admin_headers,
    )
    assert execute_response.status_code == 200
    executed_payload = execute_response.json()
    assert executed_payload["active_migration"]["status"] == "completed"
    assert executed_payload["can_rollback_migration"] is True
    assert len(executed_payload["legacy_mappings"]) >= 3
    assert any(log["action"] == "migration_executed" for log in executed_payload["recent_audit_logs"])

    rollback_response = client.post(
        f"/api/admin/migrations/{active_batch['id']}/rollback",
        headers=admin_headers,
    )
    assert rollback_response.status_code == 200
    rolled_back_payload = rollback_response.json()
    assert rolled_back_payload["active_migration"]["status"] == "rolled_back"
    assert rolled_back_payload["can_rollback_migration"] is False
    assert any(log["action"] == "migration_rolled_back" for log in rolled_back_payload["recent_audit_logs"])

    mappings = db_session.scalars(
        select(LegacyIdMapping).where(LegacyIdMapping.batch_id == active_batch["id"])
    ).all()
    assert mappings
    assert not any(mapping.active for mapping in mappings)
