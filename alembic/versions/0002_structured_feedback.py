"""structured feedback fields

Revision ID: 0002_structured_feedback
Revises: 0001_mvp_schema
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_structured_feedback"
down_revision = "0001_mvp_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_feedback",
        sa.Column("original_classification_summary", sa.String(500), nullable=True),
    )
    op.add_column("user_feedback", sa.Column("corrected_label", sa.String(100), nullable=True))
    op.add_column("user_feedback", sa.Column("corrected_importance", sa.Integer(), nullable=True))
    op.add_column(
        "user_feedback", sa.Column("corrected_requires_reply", sa.Boolean(), nullable=True)
    )
    op.add_column("user_feedback", sa.Column("corrected_is_noise", sa.Boolean(), nullable=True))
    op.add_column(
        "user_feedback", sa.Column("corrected_is_newsletter", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "user_feedback", sa.Column("corrected_is_client_work", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_feedback", "corrected_is_client_work")
    op.drop_column("user_feedback", "corrected_is_newsletter")
    op.drop_column("user_feedback", "corrected_is_noise")
    op.drop_column("user_feedback", "corrected_requires_reply")
    op.drop_column("user_feedback", "corrected_importance")
    op.drop_column("user_feedback", "corrected_label")
    op.drop_column("user_feedback", "original_classification_summary")
