"""connector source confidence metadata

Revision ID: 0011_connector_source_confidence
Revises: 0010_execution_engine
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_connector_source_confidence"
down_revision = "0010_execution_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("source_channel", sa.String(length=50), nullable=True))
    op.add_column(
        "messages",
        sa.Column("source_confidence", sa.Numeric(precision=4, scale=3), nullable=False, server_default="1.000"),
    )


def downgrade() -> None:
    op.drop_column("messages", "source_confidence")
    op.drop_column("messages", "source_channel")
