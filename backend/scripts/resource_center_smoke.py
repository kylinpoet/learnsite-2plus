from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    with TemporaryDirectory(prefix="learnsite-resource-smoke-", ignore_cleanup_errors=True) as temp_dir:
        temp_path = Path(temp_dir)
        sqlite_path = temp_path / "resource_smoke.sqlite3"
        storage_path = temp_path / "resource_storage"
        backup_path = temp_path / "backup_storage"

        os.environ["LEARNSITE_SQLITE_URL"] = f"sqlite:///{sqlite_path.resolve().as_posix()}"
        os.environ["LEARNSITE_RESOURCE_STORAGE_DIR"] = str(storage_path.resolve())
        os.environ["LEARNSITE_BACKUP_STORAGE_DIR"] = str(backup_path.resolve())

        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from app.core.auth import hash_password
        from app.core.database import SessionLocal, engine
        from app.main import app
        from app.models import ClassSession, Classroom, School, User, UserRole

        def login(client: TestClient, role: str, school_code: str, username: str, password: str) -> str:
            response = client.post(
                "/api/auth/login",
                json={
                    "role": role,
                    "school_code": school_code,
                    "username": username,
                    "password": password,
                },
            )
            assert response.status_code == 200, response.text
            return response.json()["session"]["token"]

        def auth_headers(token: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {token}"}

        with TestClient(app) as client:
            teacher_token = login(client, "teacher", "school-a", "kylin", "222221")
            teacher_console = client.get("/api/teacher/console", headers=auth_headers(teacher_token))
            assert teacher_console.status_code == 200, teacher_console.text
            teacher_console_data = teacher_console.json()
            teacher_classroom_id = teacher_console_data["managed_classrooms"][0]["id"]
            teacher_category_id = next(
                item["id"] for item in teacher_console_data["resource_categories"] if item["active"]
            )
            assert teacher_console_data["student_roster_live"] is True, teacher_console_data
            assert len(teacher_console_data["student_roster"]) == teacher_console_data["radar"]["expected"], teacher_console_data
            assert any(item["help_requested"] for item in teacher_console_data["student_roster"]), teacher_console_data[
                "student_roster"
            ]
            assert any(
                item["submission_status"] == "submitted" for item in teacher_console_data["student_roster"]
            ), teacher_console_data["student_roster"]

            teacher_upload = client.post(
                "/api/teacher/resources",
                headers=auth_headers(teacher_token),
                data={
                    "title": "round8-class-resource",
                    "audience": "student",
                    "description": "class-only smoke resource",
                    "category_id": str(teacher_category_id),
                    "classroom_id": str(teacher_classroom_id),
                },
                files={
                    "upload": ("class-resource.txt", io.BytesIO(b"class resource"), "text/plain"),
                },
            )
            assert teacher_upload.status_code == 200, teacher_upload.text
            teacher_resource = teacher_upload.json()
            assert teacher_resource["category_id"] == teacher_category_id, teacher_resource
            assert teacher_resource["category_name"], teacher_resource

            teacher_download = client.get(
                f"/api/teacher/resources/{teacher_resource['id']}/download",
                headers=auth_headers(teacher_token),
            )
            assert teacher_download.status_code == 200, teacher_download.text
            assert teacher_download.content == b"class resource"

            admin_token = login(client, "teacher", "school-a", "admin", "222221")
            category_create = client.post(
                "/api/admin/resource-categories",
                headers=auth_headers(admin_token),
                json={
                    "name": "项目案例",
                    "description": "resource center smoke custom category",
                    "sort_order": 99,
                },
            )
            assert category_create.status_code == 200, category_create.text
            created_category = next(
                item for item in category_create.json()["resource_categories"] if item["name"] == "项目案例"
            )

            category_disable = client.post(
                f"/api/admin/resource-categories/{created_category['id']}/status",
                headers=auth_headers(admin_token),
                json={"active": False},
            )
            assert category_disable.status_code == 200, category_disable.text
            assert next(
                item for item in category_disable.json()["resource_categories"] if item["id"] == created_category["id"]
            )["active"] is False

            category_enable = client.post(
                f"/api/admin/resource-categories/{created_category['id']}/status",
                headers=auth_headers(admin_token),
                json={"active": True},
            )
            assert category_enable.status_code == 200, category_enable.text
            created_category = next(
                item for item in category_enable.json()["resource_categories"] if item["id"] == created_category["id"]
            )
            assert created_category["active"] is True

            admin_console = client.get("/api/teacher/console", headers=auth_headers(admin_token))
            assert admin_console.status_code == 200, admin_console.text
            admin_console_data = admin_console.json()
            admin_classroom_id = admin_console_data["managed_classrooms"][0]["id"]

            admin_class_upload = client.post(
                "/api/teacher/resources",
                headers=auth_headers(admin_token),
                data={
                    "title": "round8-admin-class-resource",
                    "audience": "student",
                    "description": "admin classroom smoke resource",
                    "category_id": str(created_category["id"]),
                    "classroom_id": str(admin_classroom_id),
                },
                files={
                    "upload": ("admin-class-resource.txt", io.BytesIO(b"admin class resource"), "text/plain"),
                },
            )
            assert admin_class_upload.status_code == 200, admin_class_upload.text
            admin_class_resource = admin_class_upload.json()
            assert admin_class_resource["category_name"] == "项目案例", admin_class_resource

            admin_school_upload = client.post(
                "/api/teacher/resources",
                headers=auth_headers(admin_token),
                data={
                    "title": "round8-schoolwide-resource",
                    "audience": "student",
                    "description": "schoolwide smoke resource",
                    "category_id": str(teacher_category_id),
                },
                files={
                    "upload": ("schoolwide-resource.txt", io.BytesIO(b"schoolwide resource"), "text/plain"),
                },
            )
            assert admin_school_upload.status_code == 200, admin_school_upload.text
            admin_school_resource = admin_school_upload.json()
            assert admin_school_resource["category_name"], admin_school_resource

            admin_backup = client.post(
                "/api/admin/backups",
                headers=auth_headers(admin_token),
                json={"note": "resource center governance smoke backup"},
            )
            assert admin_backup.status_code == 200, admin_backup.text
            admin_backup_overview = admin_backup.json()
            assert admin_backup_overview["backup_snapshots"], admin_backup_overview
            latest_backup = admin_backup_overview["backup_snapshots"][0]
            assert latest_backup["note"] == "resource center governance smoke backup", latest_backup
            assert latest_backup["file_size"] > 0, latest_backup
            assert any(
                log["action"] == "backup_created" for log in admin_backup_overview["recent_audit_logs"]
            ), admin_backup_overview["recent_audit_logs"]
            assert any(
                log["action"] == "resource_category_created" for log in admin_backup_overview["recent_audit_logs"]
            ), admin_backup_overview["recent_audit_logs"]

            student_token = login(client, "student", "school-a", "240101", "12345")
            active_home = client.get("/api/student/home", headers=auth_headers(student_token))
            assert active_home.status_code == 200, active_home.text
            active_home_data = active_home.json()
            active_resource_ids = {item["id"] for item in active_home_data["resources"]}
            assert active_home_data["session_status"] == "active", active_home_data
            assert teacher_resource["id"] in active_resource_ids, active_home_data["resources"]
            assert admin_class_resource["id"] in active_resource_ids, active_home_data["resources"]
            assert admin_school_resource["id"] in active_resource_ids, active_home_data["resources"]
            assert next(
                item for item in active_home_data["resources"] if item["id"] == admin_class_resource["id"]
            )["category_name"] == "项目案例"

            student_download = client.get(
                f"/api/student/resources/{teacher_resource['id']}/download",
                headers=auth_headers(student_token),
            )
            assert student_download.status_code == 200, student_download.text
            assert student_download.content == b"class resource"

            teacher_console_after_download = client.get("/api/teacher/console", headers=auth_headers(teacher_token))
            assert teacher_console_after_download.status_code == 200, teacher_console_after_download.text
            teacher_console_after_download_data = teacher_console_after_download.json()
            teacher_resource_summary = next(
                item for item in teacher_console_after_download_data["resources"] if item["id"] == teacher_resource["id"]
            )
            assert teacher_resource_summary["download_count"] == 2, teacher_resource_summary
            assert teacher_resource_summary["category_name"], teacher_resource_summary

            active_home_after_download = client.get("/api/student/home", headers=auth_headers(student_token))
            assert active_home_after_download.status_code == 200, active_home_after_download.text
            active_home_after_download_data = active_home_after_download.json()
            teacher_resource_for_student = next(
                item for item in active_home_after_download_data["resources"] if item["id"] == teacher_resource["id"]
            )
            assert teacher_resource_for_student["download_count"] == 2, teacher_resource_for_student
            assert teacher_resource_for_student["category_name"], teacher_resource_for_student

            with SessionLocal() as db:
                school = db.scalar(select(School).where(School.code == "school-a"))
                current_session = db.get(ClassSession, teacher_console_data["session_id"])
                assert school is not None
                assert current_session is not None
                classroom = db.scalar(
                    select(Classroom).where(
                        Classroom.school_id == school.id,
                        Classroom.id != current_session.classroom_id,
                    )
                )
                assert classroom is not None
                idle_student = db.scalar(
                    select(User).where(
                        User.school_id == school.id,
                        User.username == "249901",
                    )
                )
                if idle_student is None:
                    idle_student = User(
                        school_id=school.id,
                        classroom_id=classroom.id,
                        username="249901",
                        display_name="resource smoke idle student",
                        password_hash=hash_password("12345"),
                        role=UserRole.STUDENT,
                    )
                    db.add(idle_student)
                    db.commit()

            idle_token = login(client, "student", "school-a", "249901", "12345")
            idle_home = client.get("/api/student/home", headers=auth_headers(idle_token))
            assert idle_home.status_code == 200, idle_home.text
            idle_home_data = idle_home.json()
            idle_resource_ids = {item["id"] for item in idle_home_data["resources"]}
            assert idle_home_data["session_status"] == "idle", idle_home_data
            assert admin_school_resource["id"] in idle_resource_ids, idle_home_data["resources"]
            assert teacher_resource["id"] not in idle_resource_ids, idle_home_data["resources"]
            assert admin_class_resource["id"] not in idle_resource_ids, idle_home_data["resources"]

            print(
                json.dumps(
                    {
                        "teacher_classroom_id": teacher_classroom_id,
                        "teacher_resource_id": teacher_resource["id"],
                        "teacher_resource_category_id": teacher_category_id,
                        "created_category_id": created_category["id"],
                        "backup_snapshot_id": latest_backup["id"],
                        "admin_class_resource_id": admin_class_resource["id"],
                        "admin_school_resource_id": admin_school_resource["id"],
                        "active_resource_ids": sorted(active_resource_ids),
                        "idle_resource_ids": sorted(idle_resource_ids),
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )

        engine.dispose()


if __name__ == "__main__":
    main()
