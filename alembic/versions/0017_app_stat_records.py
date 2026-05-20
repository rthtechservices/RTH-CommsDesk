"""app_stat_records — durable life-to-date statistics

Revision ID: 0017_app_stat_records
Revises: 0016_operator_polish_voice_profile_enabled
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_app_stat_records"
down_revision = "0016_operator_polish_voice_profile_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_stat_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stat_key", sa.String(100), nullable=False),
        sa.Column("stat_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("first_tracked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recalculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stat_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("stat_key", name="uq_app_stat_key"),
    )


def downgrade() -> None:
    op.drop_table("app_stat_records")
