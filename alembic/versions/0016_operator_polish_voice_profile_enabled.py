"""operator polish voice profile enabled flag

Revision ID: 0016_operator_polish_voice_profile_enabled
Revises: 0015_mailbox_cleanup_candidates
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_operator_polish_voice_profile_enabled"
down_revision = "0015_mailbox_cleanup_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "voice_profiles",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("voice_profiles", "is_enabled")
