"""bulk triage candidates and action logs

Revision ID: 0008_bulk_triage_candidates
Revises: 0007_sent_mail_learning
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_bulk_triage_candidates"
down_revision = "0007_sent_mail_learning"
branch_labels = None
depends_on = None


candidate_status = sa.Enum("PENDING", "APPROVED", "REJECTED", "UNDONE", name="candidatestatus")
proposed_action_type = sa.Enum(
    "NO_RESPONSE_NEEDED",
    "REPLY",
    "SCHEDULE_MEETING",
    "ASK_CLARIFYING_QUESTION",
    "MARK_NOISE",
    "UNSUBSCRIBE_REVIEW",
    "CREATE_CALENDAR_REMINDER",
    "FOLLOW_UP_LATER",
    "ARCHIVE_CANDIDATE",
    "DELETE_CANDIDATE",
    "REVIEW_NEEDED",
    name="proposedactiontype",
)


def upgrade() -> None:
    op.create_table(
        "automation_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("candidate_type", proposed_action_type, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("status", candidate_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["message_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "candidate_type",
            name="uq_automation_candidate_message_type",
        ),
    )
    op.create_index(
        op.f("ix_automation_candidates_contact_id"), "automation_candidates", ["contact_id"], unique=False
    )
    op.create_index(
        op.f("ix_automation_candidates_message_id"), "automation_candidates", ["message_id"], unique=False
    )
    op.create_index(
        op.f("ix_automation_candidates_thread_id"), "automation_candidates", ["thread_id"], unique=False
    )
    op.create_index(
        "ix_automation_candidate_type_status",
        "automation_candidates",
        ["candidate_type", "status"],
        unique=False,
    )

    op.create_table(
        "bulk_triage_action_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("queue_filter", sa.String(length=100), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("is_undone", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bulk_triage_action_logs_created",
        "bulk_triage_action_logs",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "bulk_triage_action_log_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_log_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_log_id"], ["bulk_triage_action_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bulk_triage_action_log_items_action_log_id"),
        "bulk_triage_action_log_items",
        ["action_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_bulk_action_log_item_log_entity",
        "bulk_triage_action_log_items",
        ["action_log_id", "entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bulk_action_log_item_log_entity", table_name="bulk_triage_action_log_items")
    op.drop_index(
        op.f("ix_bulk_triage_action_log_items_action_log_id"),
        table_name="bulk_triage_action_log_items",
    )
    op.drop_table("bulk_triage_action_log_items")
    op.drop_index("ix_bulk_triage_action_logs_created", table_name="bulk_triage_action_logs")
    op.drop_table("bulk_triage_action_logs")
    op.drop_index("ix_automation_candidate_type_status", table_name="automation_candidates")
    op.drop_index(op.f("ix_automation_candidates_thread_id"), table_name="automation_candidates")
    op.drop_index(op.f("ix_automation_candidates_message_id"), table_name="automation_candidates")
    op.drop_index(op.f("ix_automation_candidates_contact_id"), table_name="automation_candidates")
    op.drop_table("automation_candidates")
