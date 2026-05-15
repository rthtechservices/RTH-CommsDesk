"""sync state reliability

Revision ID: 0003_sync_state_reliability
Revises: 0002_structured_feedback
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_sync_state_reliability"
down_revision = "0002_structured_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_sync_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("account_identifier", sa.String(255), nullable=False),
        sa.Column("high_water_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("high_water_message_id", sa.String(255), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_skipped_duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_thread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_type", "account_identifier", name="uq_sync_state_source_account"
        ),
    )
    op.execute(
        """
        DELETE FROM attention_items
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM attention_items
            GROUP BY thread_id, message_id
        )
        """
    )
    op.create_index(
        "uq_attention_items_thread_message",
        "attention_items",
        ["thread_id", "message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_attention_items_thread_message", table_name="attention_items")
    op.drop_table("source_sync_states")
