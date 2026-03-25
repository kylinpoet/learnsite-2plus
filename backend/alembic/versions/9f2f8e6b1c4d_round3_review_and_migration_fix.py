"""round3_review_and_migration_fix

Revision ID: 9f2f8e6b1c4d
Revises: 758bd77cc51c
Create Date: 2026-03-25 17:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f2f8e6b1c4d"
down_revision: Union[str, Sequence[str], None] = "758bd77cc51c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reviewdecision = sa.Enum("APPROVED", "REVISION_REQUESTED", "REJECTED", name="reviewdecision")
submissionrevisionaction = sa.Enum("DRAFT_SAVED", "SUBMITTED", name="submissionrevisionaction")


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
    reviewdecision.create(op.get_bind(), checkfirst=True)
    submissionrevisionaction.create(op.get_bind(), checkfirst=True)

    review_decision_missing = not _column_exists("submissions", "review_decision")
    reviewed_by_missing = not _column_exists("submissions", "reviewed_by_user_id")
    if review_decision_missing:
        op.add_column("submissions", sa.Column("review_decision", reviewdecision, nullable=True))
    if reviewed_by_missing:
        with op.batch_alter_table("submissions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_submissions_reviewed_by_user_id_users",
                "users",
                ["reviewed_by_user_id"],
                ["id"],
            )

    if not _table_exists("submission_revisions"):
        op.create_table(
            "submission_revisions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("submission_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("action", submissionrevisionaction, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"]),
            sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("submission_revisions", op.f("ix_submission_revisions_school_id")):
        op.create_index(op.f("ix_submission_revisions_school_id"), "submission_revisions", ["school_id"], unique=False)
    if not _index_exists("submission_revisions", op.f("ix_submission_revisions_session_id")):
        op.create_index(op.f("ix_submission_revisions_session_id"), "submission_revisions", ["session_id"], unique=False)
    if not _index_exists("submission_revisions", op.f("ix_submission_revisions_submission_id")):
        op.create_index(op.f("ix_submission_revisions_submission_id"), "submission_revisions", ["submission_id"], unique=False)
    if not _index_exists("submission_revisions", op.f("ix_submission_revisions_user_id")):
        op.create_index(op.f("ix_submission_revisions_user_id"), "submission_revisions", ["user_id"], unique=False)

    if not _table_exists("submission_reviews"):
        op.create_table(
            "submission_reviews",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("submission_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
            sa.Column("decision", reviewdecision, nullable=False),
            sa.Column("feedback", sa.Text(), nullable=False),
            sa.Column("ai_draft_content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"]),
            sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("submission_reviews", op.f("ix_submission_reviews_reviewer_user_id")):
        op.create_index(op.f("ix_submission_reviews_reviewer_user_id"), "submission_reviews", ["reviewer_user_id"], unique=False)
    if not _index_exists("submission_reviews", op.f("ix_submission_reviews_school_id")):
        op.create_index(op.f("ix_submission_reviews_school_id"), "submission_reviews", ["school_id"], unique=False)
    if not _index_exists("submission_reviews", op.f("ix_submission_reviews_session_id")):
        op.create_index(op.f("ix_submission_reviews_session_id"), "submission_reviews", ["session_id"], unique=False)
    if not _index_exists("submission_reviews", op.f("ix_submission_reviews_submission_id")):
        op.create_index(op.f("ix_submission_reviews_submission_id"), "submission_reviews", ["submission_id"], unique=False)

    issue_detail_missing = not _column_exists("migration_preview_items", "issue_detail")
    resolution_note_missing = not _column_exists("migration_preview_items", "resolution_note")
    resolved_by_missing = not _column_exists("migration_preview_items", "resolved_by_user_id")
    resolved_at_missing = not _column_exists("migration_preview_items", "resolved_at")
    if issue_detail_missing:
        op.add_column("migration_preview_items", sa.Column("issue_detail", sa.String(length=255), nullable=True))
    if resolution_note_missing:
        op.add_column("migration_preview_items", sa.Column("resolution_note", sa.String(length=255), nullable=True))
    if resolved_at_missing:
        op.add_column("migration_preview_items", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    if resolved_by_missing:
        with op.batch_alter_table("migration_preview_items", schema=None) as batch_op:
            batch_op.add_column(sa.Column("resolved_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_migration_preview_items_resolved_by_user_id_users",
                "users",
                ["resolved_by_user_id"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("migration_preview_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_migration_preview_items_resolved_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("resolved_by_user_id")
        batch_op.drop_column("resolution_note")
        batch_op.drop_column("issue_detail")

    op.drop_index(op.f("ix_submission_reviews_submission_id"), table_name="submission_reviews")
    op.drop_index(op.f("ix_submission_reviews_session_id"), table_name="submission_reviews")
    op.drop_index(op.f("ix_submission_reviews_school_id"), table_name="submission_reviews")
    op.drop_index(op.f("ix_submission_reviews_reviewer_user_id"), table_name="submission_reviews")
    op.drop_table("submission_reviews")

    op.drop_index(op.f("ix_submission_revisions_user_id"), table_name="submission_revisions")
    op.drop_index(op.f("ix_submission_revisions_submission_id"), table_name="submission_revisions")
    op.drop_index(op.f("ix_submission_revisions_session_id"), table_name="submission_revisions")
    op.drop_index(op.f("ix_submission_revisions_school_id"), table_name="submission_revisions")
    op.drop_table("submission_revisions")

    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_submissions_reviewed_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("review_decision")

    submissionrevisionaction.drop(op.get_bind(), checkfirst=True)
    reviewdecision.drop(op.get_bind(), checkfirst=True)
