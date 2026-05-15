"""gmail conversation context

Revision ID: 0005_gmail_conversation_context
Revises: 0004_contact_alias_index
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_gmail_conversation_context"
down_revision = "0004_contact_alias_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("recipient_emails", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("cc_emails", sa.Text(), nullable=True))
    op.add_column(
        "message_threads",
        sa.Column("full_content_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_sync_states",
        sa.Column("backlog_next_page_token", sa.String(500), nullable=True),
    )
    op.add_column(
        "source_sync_states",
        sa.Column("last_backfill_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_sync_states",
        sa.Column("last_backfill_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_sync_states",
        sa.Column("last_backfill_fetched_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_sync_states",
        sa.Column("last_backfill_inserted_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_sync_states",
        sa.Column(
            "last_backfill_skipped_duplicate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("source_sync_states", sa.Column("last_backfill_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_sync_states", "last_backfill_error")
    op.drop_column("source_sync_states", "last_backfill_skipped_duplicate_count")
    op.drop_column("source_sync_states", "last_backfill_inserted_count")
    op.drop_column("source_sync_states", "last_backfill_fetched_count")
    op.drop_column("source_sync_states", "last_backfill_finished_at")
    op.drop_column("source_sync_states", "last_backfill_started_at")
    op.drop_column("source_sync_states", "backlog_next_page_token")
    op.drop_column("message_threads", "full_content_fetched_at")
    op.drop_column("messages", "cc_emails")
    op.drop_column("messages", "recipient_emails")
