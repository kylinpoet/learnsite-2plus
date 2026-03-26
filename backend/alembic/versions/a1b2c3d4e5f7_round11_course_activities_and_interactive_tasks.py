"""round11_course_activities_and_interactive_tasks

Revision ID: a1b2c3d4e5f7
Revises: f2a3b4c5d6e7
Create Date: 2026-03-26 21:10:00.000000

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table("course_activities"):
        op.create_table(
            "course_activities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False, index=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False, index=True),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column(
                "activity_type",
                sa.Enum("rich_text", "interactive_page", name="courseactivitytype"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("summary", sa.String(length=255), nullable=True),
            sa.Column("instructions_html", sa.Text(), nullable=False, server_default=""),
            sa.Column("interactive_storage_key", sa.String(length=255), nullable=True),
            sa.Column("interactive_entry_file", sa.String(length=255), nullable=True),
            sa.Column("interactive_asset_name", sa.String(length=255), nullable=True),
            sa.Column("interactive_launch_key", sa.String(length=64), nullable=True, unique=True),
            sa.Column("interactive_submission_key", sa.String(length=64), nullable=True, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("course_id", "position", name="uq_course_activities_course_position"),
        )

    if not _has_table("activity_submissions"):
        op.create_table(
            "activity_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False, index=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False, index=True),
            sa.Column("activity_id", sa.Integer(), sa.ForeignKey("course_activities.id"), nullable=False, index=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("class_sessions.id"), nullable=True, index=True),
            sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("submitted_by_name", sa.String(length=128), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    activity_count = bind.execute(sa.text("SELECT COUNT(1) FROM course_activities")).scalar_one()
    if activity_count == 0:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = bind.execute(
            sa.text(
                """
                SELECT id, school_id, assignment_title, assignment_prompt
                FROM courses
                ORDER BY id
                """
            )
        ).mappings()
        for row in rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO course_activities (
                      school_id,
                      course_id,
                      title,
                      activity_type,
                      position,
                      summary,
                      instructions_html,
                      created_at,
                      updated_at
                    ) VALUES (
                      :school_id,
                      :course_id,
                      :title,
                      'rich_text',
                      1,
                      :summary,
                      :instructions_html,
                      :created_at,
                      :updated_at
                    )
                    """
                ),
                {
                    "school_id": row["school_id"],
                    "course_id": row["id"],
                    "title": row["assignment_title"],
                    "summary": "Migrated default activity from the legacy assignment prompt.",
                    "instructions_html": row["assignment_prompt"],
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    if _has_table("activity_submissions"):
        op.drop_table("activity_submissions")
    if _has_table("course_activities"):
        op.drop_table("course_activities")
