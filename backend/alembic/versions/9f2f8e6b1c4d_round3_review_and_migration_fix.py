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


def upgrade() -> None:
    reviewdecision.create(op.get_bind(), checkfirst=True)
    submissionrevisionaction.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("review_decision", reviewdecision, nullable=True))
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_submissions_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
        )

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
    op.create_index(op.f("ix_submission_revisions_school_id"), "submission_revisions", ["school_id"], unique=False)
    op.create_index(op.f("ix_submission_revisions_session_id"), "submission_revisions", ["session_id"], unique=False)
    op.create_index(op.f("ix_submission_revisions_submission_id"), "submission_revisions", ["submission_id"], unique=False)
    op.create_index(op.f("ix_submission_revisions_user_id"), "submission_revisions", ["user_id"], unique=False)

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
    op.create_index(op.f("ix_submission_reviews_reviewer_user_id"), "submission_reviews", ["reviewer_user_id"], unique=False)
    op.create_index(op.f("ix_submission_reviews_school_id"), "submission_reviews", ["school_id"], unique=False)
    op.create_index(op.f("ix_submission_reviews_session_id"), "submission_reviews", ["session_id"], unique=False)
    op.create_index(op.f("ix_submission_reviews_submission_id"), "submission_reviews", ["submission_id"], unique=False)

    with op.batch_alter_table("migration_preview_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("issue_detail", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("resolution_note", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("resolved_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))
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
