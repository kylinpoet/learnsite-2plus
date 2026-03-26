"""round7_teacher_classroom_scope

Revision ID: c2d3e4f5a6b7
Revises: a7b8c9d0e1f2
Create Date: 2026-03-26 23:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("teacher_classroom_assignments"):
        op.create_table(
            "teacher_classroom_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
            sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("teacher_user_id", "classroom_id", name="uq_teacher_classroom_assignment"),
        )
        op.create_index(
            "ix_teacher_classroom_assignments_school_id",
            "teacher_classroom_assignments",
            ["school_id"],
        )
        op.create_index(
            "ix_teacher_classroom_assignments_teacher_user_id",
            "teacher_classroom_assignments",
            ["teacher_user_id"],
        )
        op.create_index(
            "ix_teacher_classroom_assignments_classroom_id",
            "teacher_classroom_assignments",
            ["classroom_id"],
        )

    op.execute(
        """
        INSERT INTO teacher_classroom_assignments (
            school_id,
            teacher_user_id,
            classroom_id,
            created_at,
            updated_at
        )
        SELECT DISTINCT
            class_sessions.school_id,
            class_sessions.teacher_id,
            class_sessions.classroom_id,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM class_sessions
        WHERE class_sessions.teacher_id IS NOT NULL
          AND class_sessions.classroom_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM teacher_classroom_assignments existing
              WHERE existing.teacher_user_id = class_sessions.teacher_id
                AND existing.classroom_id = class_sessions.classroom_id
          )
        """
    )


def downgrade() -> None:
    if _table_exists("teacher_classroom_assignments"):
        op.drop_index("ix_teacher_classroom_assignments_classroom_id", table_name="teacher_classroom_assignments")
        op.drop_index("ix_teacher_classroom_assignments_teacher_user_id", table_name="teacher_classroom_assignments")
        op.drop_index("ix_teacher_classroom_assignments_school_id", table_name="teacher_classroom_assignments")
        op.drop_table("teacher_classroom_assignments")
