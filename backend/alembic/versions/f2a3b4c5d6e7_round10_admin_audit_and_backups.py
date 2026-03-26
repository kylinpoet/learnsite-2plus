"""round10_admin_audit_and_backups

Revision ID: f2a3b4c5d6e7
Revises: e9f1a2b3c4d5
Create Date: 2026-03-26 15:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e9f1a2b3c4d5"
branch_labels = None
depends_on = None


user_role_enum = sa.Enum("student", "teacher", "school_admin", "platform_admin", name="userrole")
audit_log_level_enum = sa.Enum("info", "warning", "risk", name="auditloglevel")
backup_snapshot_status_enum = sa.Enum("ready", "restored", name="backupsnapshotstatus")


def upgrade() -> None:
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)
    audit_log_level_enum.create(bind, checkfirst=True)
    backup_snapshot_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column("actor_display_name", sa.String(length=64), nullable=False),
        sa.Column("actor_role", user_role_enum, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=False),
        sa.Column("level", audit_log_level_enum, nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_school_id", "audit_logs", ["school_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_actor_role", "audit_logs", ["actor_role"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_level", "audit_logs", ["level"])

    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("school_name", sa.String(length=128), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column("actor_display_name", sa.String(length=64), nullable=False),
        sa.Column("actor_role", user_role_enum, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status", backup_snapshot_status_enum, nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("storage_path", name="uq_backup_snapshots_storage_path"),
    )
    op.create_index("ix_backup_snapshots_school_id", "backup_snapshots", ["school_id"])
    op.create_index("ix_backup_snapshots_actor_user_id", "backup_snapshots", ["actor_user_id"])
    op.create_index("ix_backup_snapshots_actor_role", "backup_snapshots", ["actor_role"])
    op.create_index("ix_backup_snapshots_status", "backup_snapshots", ["status"])


def downgrade() -> None:
    op.drop_index("ix_backup_snapshots_status", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_actor_role", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_actor_user_id", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_school_id", table_name="backup_snapshots")
    op.drop_table("backup_snapshots")

    op.drop_index("ix_audit_logs_level", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_role", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_school_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    bind = op.get_bind()
    backup_snapshot_status_enum.drop(bind, checkfirst=True)
    audit_log_level_enum.drop(bind, checkfirst=True)
