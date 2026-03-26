"""round4_teacher_analytics_reflection

Revision ID: e4c1f7a9b2d0
Revises: 9f2f8e6b1c4d
Create Date: 2026-03-26 18:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4c1f7a9b2d0"
down_revision: Union[str, Sequence[str], None] = "9f2f8e6b1c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("session_reflections"):
        op.create_table(
            "session_reflections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("teacher_id", sa.Integer(), nullable=False),
            sa.Column("strengths", sa.Text(), nullable=False, server_default=""),
            sa.Column("risks", sa.Text(), nullable=False, server_default=""),
            sa.Column("next_actions", sa.Text(), nullable=False, server_default=""),
            sa.Column("student_support_plan", sa.Text(), nullable=False, server_default=""),
            sa.Column("ai_draft_content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"]),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "teacher_id", name="uq_session_reflections_session_teacher"),
        )
    if not _index_exists("session_reflections", op.f("ix_session_reflections_school_id")):
        op.create_index(op.f("ix_session_reflections_school_id"), "session_reflections", ["school_id"], unique=False)
    if not _index_exists("session_reflections", op.f("ix_session_reflections_session_id")):
        op.create_index(op.f("ix_session_reflections_session_id"), "session_reflections", ["session_id"], unique=False)
    if not _index_exists("session_reflections", op.f("ix_session_reflections_teacher_id")):
        op.create_index(op.f("ix_session_reflections_teacher_id"), "session_reflections", ["teacher_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_session_reflections_teacher_id"), table_name="session_reflections")
    op.drop_index(op.f("ix_session_reflections_session_id"), table_name="session_reflections")
    op.drop_index(op.f("ix_session_reflections_school_id"), table_name="session_reflections")
    op.drop_table("session_reflections")
