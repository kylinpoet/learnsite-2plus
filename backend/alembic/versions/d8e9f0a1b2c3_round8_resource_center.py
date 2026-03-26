"""round8_resource_center

Revision ID: d8e9f0a1b2c3
Revises: c2d3e4f5a6b7
Create Date: 2026-03-27 00:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("learning_resources"):
        return

    audience_enum = sa.Enum("STUDENT", "TEACHER", "ALL", name="resourceaudience")
    audience_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "learning_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=True),
        sa.Column("uploader_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audience", audience_enum, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_learning_resources_school_id", "learning_resources", ["school_id"])
    op.create_index("ix_learning_resources_classroom_id", "learning_resources", ["classroom_id"])
    op.create_index("ix_learning_resources_uploader_user_id", "learning_resources", ["uploader_user_id"])
    op.create_index("ix_learning_resources_audience", "learning_resources", ["audience"])


def downgrade() -> None:
    if not _table_exists("learning_resources"):
        return

    op.drop_index("ix_learning_resources_audience", table_name="learning_resources")
    op.drop_index("ix_learning_resources_uploader_user_id", table_name="learning_resources")
    op.drop_index("ix_learning_resources_classroom_id", table_name="learning_resources")
    op.drop_index("ix_learning_resources_school_id", table_name="learning_resources")
    op.drop_table("learning_resources")
    sa.Enum(name="resourceaudience").drop(op.get_bind(), checkfirst=True)
