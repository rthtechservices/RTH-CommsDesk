"""mailbox cleanup candidates and action logs

Revision ID: 0015_mailbox_cleanup_candidates
Revises: 0014_operational_smoke_persistence
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_mailbox_cleanup_candidates"
down_revision = "0014_operational_smoke_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailbox_cleanup_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_key", sa.String(length=255), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=True),
        sa.Column("sender_display_name", sa.String(length=255), nullable=True),
        sa.Column("sender_domain", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="gmail"),
        sa.Column("total_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("oldest_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("newest_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marketing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("newsletter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_noise_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("system_notification_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unsubscribe_language_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_personal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vip_contact_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("existing_contact_is_vip", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("existing_contact_is_noise", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("existing_contact_relationship", sa.String(length=50), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False, server_default="0.0"),
        sa.Column(
            "recommended_action",
            sa.String(length=50),
            nullable=False,
            server_default="review_only",
        ),
        sa.Column("recommended_gmail_label", sa.String(length=255), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("sample_subjects_json", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "last_execution_record_id",
            sa.Integer(),
            sa.ForeignKey("execution_records.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sender_key", name="uq_cleanup_candidate_sender_key"),
    )
    op.create_index(
        "ix_cleanup_candidate_status_confidence",
        "mailbox_cleanup_candidates",
        ["status", "confidence_score"],
        unique=False,
    )
    op.create_index(
        "ix_cleanup_candidate_sender_email",
        "mailbox_cleanup_candidates",
        ["sender_email"],
        unique=False,
    )
    op.create_index(
        "ix_cleanup_candidate_contact_id",
        "mailbox_cleanup_candidates",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "ix_cleanup_candidate_last_execution",
        "mailbox_cleanup_candidates",
        ["last_execution_record_id"],
        unique=False,
    )

    op.create_table(
        "mailbox_cleanup_action_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("mailbox_cleanup_candidates.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column(
            "execution_record_id",
            sa.Integer(),
            sa.ForeignKey("execution_records.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cleanup_action_log_candidate_created",
        "mailbox_cleanup_action_logs",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_cleanup_action_log_execution",
        "mailbox_cleanup_action_logs",
        ["execution_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cleanup_action_log_execution", table_name="mailbox_cleanup_action_logs")
    op.drop_index(
        "ix_cleanup_action_log_candidate_created", table_name="mailbox_cleanup_action_logs"
    )
    op.drop_table("mailbox_cleanup_action_logs")

    op.drop_index("ix_cleanup_candidate_last_execution", table_name="mailbox_cleanup_candidates")
    op.drop_index("ix_cleanup_candidate_contact_id", table_name="mailbox_cleanup_candidates")
    op.drop_index("ix_cleanup_candidate_sender_email", table_name="mailbox_cleanup_candidates")
    op.drop_index(
        "ix_cleanup_candidate_status_confidence", table_name="mailbox_cleanup_candidates"
    )
    op.drop_table("mailbox_cleanup_candidates")
