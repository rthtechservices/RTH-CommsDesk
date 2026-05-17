"""live ai provider diagnostics

Revision ID: 0012_live_ai_provider_diagnostics
Revises: 0011_connector_source_confidence
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_live_ai_provider_diagnostics"
down_revision = "0011_connector_source_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "draft_replies",
        sa.Column("provider_name", sa.String(length=100), nullable=False, server_default="mock"),
    )


def downgrade() -> None:
    op.drop_column("draft_replies", "provider_name")
