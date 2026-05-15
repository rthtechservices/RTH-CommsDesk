"""calendar availability proposals

Revision ID: 0009_calendar_action_proposals
Revises: 0008_bulk_triage_candidates
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_calendar_action_proposals"
down_revision = "0008_bulk_triage_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_action_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_package_id", sa.Integer(), nullable=False),
        sa.Column("action_kind", sa.String(length=100), nullable=False),
        sa.Column("proposed_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_reasoning", sa.Text(), nullable=True),
        sa.Column("conflict_summary", sa.Text(), nullable=True),
        sa.Column("available_windows", sa.Text(), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_package_id"], ["proposed_action_review_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calendar_action_proposals_review_package_id"),
        "calendar_action_proposals",
        ["review_package_id"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_action_proposals_package",
        "calendar_action_proposals",
        ["review_package_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_action_proposals_package", table_name="calendar_action_proposals")
    op.drop_index(
        op.f("ix_calendar_action_proposals_review_package_id"),
        table_name="calendar_action_proposals",
    )
    op.drop_table("calendar_action_proposals")
