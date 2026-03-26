"""round6_student_import_and_course_publish

Revision ID: a7b8c9d0e1f2
Revises: f1a2c3d4e5f6
Create Date: 2026-03-26 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _column_exists("courses", "overview"):
        op.add_column("courses", sa.Column("overview", sa.Text(), nullable=True))
    if not _column_exists("courses", "is_published"):
        op.add_column(
            "courses",
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if not _column_exists("courses", "published_at"):
        op.add_column("courses", sa.Column("published_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE courses SET is_published = 1 WHERE is_published IS NULL")
    op.execute("UPDATE courses SET published_at = COALESCE(published_at, created_at) WHERE is_published = 1")


def downgrade() -> None:
    op.drop_column("courses", "published_at")
    op.drop_column("courses", "is_published")
    op.drop_column("courses", "overview")
