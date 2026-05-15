"""contact alias lookup index

Revision ID: 0004_contact_alias_index
Revises: 0003_sync_state_reliability
Create Date: 2026-05-15
"""

from alembic import op


revision = "0004_contact_alias_index"
down_revision = "0003_sync_state_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_contact_aliases_email", "contact_aliases", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contact_aliases_email", table_name="contact_aliases")
