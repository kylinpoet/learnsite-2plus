"""round5_admin_terms_and_assignments

Revision ID: f1a2c3d4e5f6
Revises: e4c1f7a9b2d0
Create Date: 2026-03-26 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e4c1f7a9b2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("academic_terms"):
        op.create_table(
            "academic_terms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("school_year_label", sa.String(length=32), nullable=False),
            sa.Column("term_name", sa.String(length=64), nullable=False),
            sa.Column("start_on", sa.Date(), nullable=True),
            sa.Column("end_on", sa.Date(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("school_id", "school_year_label", "term_name", name="uq_terms_school_year_name"),
        )
    if not _index_exists("academic_terms", op.f("ix_academic_terms_school_id")):
        op.create_index(op.f("ix_academic_terms_school_id"), "academic_terms", ["school_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_academic_terms_school_id"), table_name="academic_terms")
    op.drop_table("academic_terms")
