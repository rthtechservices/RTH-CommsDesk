"""ai review packages

Revision ID: 0006_ai_review_packages
Revises: 0005_gmail_conversation_context
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_ai_review_packages"
down_revision = "0005_gmail_conversation_context"
branch_labels = None
depends_on = None


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

review_package_status = sa.Enum(
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EDITED",
    "SNOOZED",
    name="reviewpackagestatus",
)


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("detected_due_date", sa.String(length=100), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["message_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_conversation_summaries_thread"),
    )
    op.create_index(
        op.f("ix_conversation_summaries_thread_id"),
        "conversation_summaries",
        ["thread_id"],
        unique=False,
    )

    op.create_table(
        "proposed_action_review_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("conversation_summary_id", sa.Integer(), nullable=True),
        sa.Column("action_type", proposed_action_type, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("draft_response", sa.Text(), nullable=True),
        sa.Column("status", review_package_status, nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("is_external_action", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_summary_id"], ["conversation_summaries.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["message_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_review_packages_message"),
    )
    op.create_index(
        op.f("ix_proposed_action_review_packages_message_id"),
        "proposed_action_review_packages",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposed_action_review_packages_thread_id"),
        "proposed_action_review_packages",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_packages_thread_created",
        "proposed_action_review_packages",
        ["thread_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_packages_thread_created", table_name="proposed_action_review_packages")
    op.drop_index(
        op.f("ix_proposed_action_review_packages_thread_id"),
        table_name="proposed_action_review_packages",
    )
    op.drop_index(
        op.f("ix_proposed_action_review_packages_message_id"),
        table_name="proposed_action_review_packages",
    )
    op.drop_table("proposed_action_review_packages")
    op.drop_index(op.f("ix_conversation_summaries_thread_id"), table_name="conversation_summaries")
    op.drop_table("conversation_summaries")
