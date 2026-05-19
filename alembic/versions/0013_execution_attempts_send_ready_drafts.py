"""execution attempts and send-ready draft fields

Revision ID: 0013_execution_attempts_send_ready_drafts
Revises: 0012_live_ai_provider_diagnostics
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_execution_attempts_send_ready_drafts"
down_revision = "0012_live_ai_provider_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("draft_replies", sa.Column("review_text", sa.Text(), nullable=True))
    op.add_column("draft_replies", sa.Column("caveats_json", sa.Text(), nullable=True))
    op.add_column(
        "draft_replies",
        sa.Column("send_ready_subject", sa.String(length=500), nullable=True),
    )
    op.add_column("draft_replies", sa.Column("send_ready_body", sa.Text(), nullable=True))

    with op.batch_alter_table("execution_records") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.drop_constraint("uq_execution_review_action", type_="unique")
        batch_op.drop_constraint("uq_execution_draft_action", type_="unique")

    op.create_index(
        "ix_execution_records_review_attempt",
        "execution_records",
        ["review_package_id", "action_type", "attempt_number"],
        unique=False,
    )
    op.create_index(
        "ix_execution_records_draft_attempt",
        "execution_records",
        ["draft_id", "action_type", "attempt_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_records_draft_attempt", table_name="execution_records")
    op.drop_index("ix_execution_records_review_attempt", table_name="execution_records")

    with op.batch_alter_table("execution_records") as batch_op:
        batch_op.create_unique_constraint(
            "uq_execution_draft_action", ["draft_id", "action_type"]
        )
        batch_op.create_unique_constraint(
            "uq_execution_review_action", ["review_package_id", "action_type"]
        )
        batch_op.drop_column("attempt_number")

    op.drop_column("draft_replies", "send_ready_body")
    op.drop_column("draft_replies", "send_ready_subject")
    op.drop_column("draft_replies", "caveats_json")
    op.drop_column("draft_replies", "review_text")
