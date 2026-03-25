"""round2_workflow_support

Revision ID: 758bd77cc51c
Revises: b93c9baa7f6b
Create Date: 2026-03-25 15:38:44.402881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '758bd77cc51c'
down_revision: Union[str, Sequence[str], None] = 'b93c9baa7f6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("legacy_id_mappings"):
        op.create_table(
            "legacy_id_mappings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("legacy_id", sa.String(length=128), nullable=False),
            sa.Column("new_id", sa.String(length=128), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["migration_batches.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("legacy_id_mappings", op.f("ix_legacy_id_mappings_batch_id")):
        op.create_index(op.f("ix_legacy_id_mappings_batch_id"), "legacy_id_mappings", ["batch_id"], unique=False)
    if not _index_exists("legacy_id_mappings", op.f("ix_legacy_id_mappings_school_id")):
        op.create_index(op.f("ix_legacy_id_mappings_school_id"), "legacy_id_mappings", ["school_id"], unique=False)

    if not _table_exists("attendance_records"):
        op.create_table(
            "attendance_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("PENDING", "PRESENT", "LATE", "ABSENT", "EXCUSED", name="attendancestatus"),
                nullable=False,
            ),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("note", sa.String(length=255), nullable=True),
            sa.Column("marked_by_user_id", sa.Integer(), nullable=True),
            sa.Column("marked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["marked_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "user_id", name="uq_attendance_session_user"),
        )
    if not _index_exists("attendance_records", op.f("ix_attendance_records_school_id")):
        op.create_index(op.f("ix_attendance_records_school_id"), "attendance_records", ["school_id"], unique=False)
    if not _index_exists("attendance_records", op.f("ix_attendance_records_session_id")):
        op.create_index(op.f("ix_attendance_records_session_id"), "attendance_records", ["session_id"], unique=False)
    if not _index_exists("attendance_records", op.f("ix_attendance_records_user_id")):
        op.create_index(op.f("ix_attendance_records_user_id"), "attendance_records", ["user_id"], unique=False)

    if not _table_exists("submissions"):
        op.create_table(
            "submissions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.Enum("DRAFT", "SUBMITTED", "REVIEWED", name="submissionstatus"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("draft_saved_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("teacher_feedback", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "user_id", name="uq_submission_session_user"),
        )
    if not _index_exists("submissions", op.f("ix_submissions_school_id")):
        op.create_index(op.f("ix_submissions_school_id"), "submissions", ["school_id"], unique=False)
    if not _index_exists("submissions", op.f("ix_submissions_session_id")):
        op.create_index(op.f("ix_submissions_session_id"), "submissions", ["session_id"], unique=False)
    if not _index_exists("submissions", op.f("ix_submissions_user_id")):
        op.create_index(op.f("ix_submissions_user_id"), "submissions", ["user_id"], unique=False)

    if not _column_exists("courses", "assignment_title"):
        op.add_column(
            "courses",
            sa.Column(
                "assignment_title",
                sa.String(length=128),
                nullable=False,
                server_default="课堂作品提交",
            ),
        )
    if not _column_exists("courses", "assignment_prompt"):
        op.add_column(
            "courses",
            sa.Column(
                "assignment_prompt",
                sa.Text(),
                nullable=False,
                server_default="请整理课堂作品内容并提交给老师。",
            ),
        )
    op.execute("UPDATE courses SET assignment_title = title WHERE assignment_title = '课堂作品提交'")


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('courses', 'assignment_prompt')
    op.drop_column('courses', 'assignment_title')
    op.drop_index(op.f('ix_submissions_user_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_session_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_school_id'), table_name='submissions')
    op.drop_table('submissions')
    op.drop_index(op.f('ix_attendance_records_user_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_session_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_school_id'), table_name='attendance_records')
    op.drop_table('attendance_records')
    op.drop_index(op.f('ix_legacy_id_mappings_school_id'), table_name='legacy_id_mappings')
    op.drop_index(op.f('ix_legacy_id_mappings_batch_id'), table_name='legacy_id_mappings')
    op.drop_table('legacy_id_mappings')
    # ### end Alembic commands ###
