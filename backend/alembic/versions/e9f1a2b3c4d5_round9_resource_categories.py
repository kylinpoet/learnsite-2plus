"""round9_resource_categories

Revision ID: e9f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2026-03-27 02:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e9f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("resource_categories"):
        op.create_table(
            "resource_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("school_id", "name", name="uq_resource_categories_school_name"),
        )

    if not _index_exists("resource_categories", "ix_resource_categories_school_id"):
        op.create_index("ix_resource_categories_school_id", "resource_categories", ["school_id"])

    if not _column_exists("learning_resources", "category_id"):
        with op.batch_alter_table("learning_resources") as batch_op:
            batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_learning_resources_category_id_resource_categories",
                "resource_categories",
                ["category_id"],
                ["id"],
            )

    if not _index_exists("learning_resources", "ix_learning_resources_category_id"):
        op.create_index("ix_learning_resources_category_id", "learning_resources", ["category_id"])


def downgrade() -> None:
    if _index_exists("learning_resources", "ix_learning_resources_category_id"):
        op.drop_index("ix_learning_resources_category_id", table_name="learning_resources")

    if _table_exists("learning_resources") and _column_exists("learning_resources", "category_id"):
        with op.batch_alter_table("learning_resources") as batch_op:
            batch_op.drop_constraint("fk_learning_resources_category_id_resource_categories", type_="foreignkey")
            batch_op.drop_column("category_id")

    if _index_exists("resource_categories", "ix_resource_categories_school_id"):
        op.drop_index("ix_resource_categories_school_id", table_name="resource_categories")

    if _table_exists("resource_categories"):
        op.drop_table("resource_categories")
