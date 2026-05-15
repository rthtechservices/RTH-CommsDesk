"""approved outbound execution engine

Revision ID: 0010_execution_engine
Revises: 0009_calendar_action_proposals
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_execution_engine"
down_revision = "0009_calendar_action_proposals"
branch_labels = None
depends_on = None


execution_status = sa.Enum(
    "PENDING_REVIEW",
    "APPROVED",
    "EXECUTING",
    "EXECUTED",
    "FAILED",
    "CANCELLED",
    name="executionstatus",
)

execution_action_type = sa.Enum(
    "CREATE_EXTERNAL_GMAIL_DRAFT",
    "SEND_GMAIL_REPLY",
    "CREATE_CALENDAR_EVENT",
    "APPLY_GMAIL_LABEL_ARCHIVE",
    "DELETE_UNSUBSCRIBE",
    name="executionactiontype",
)


def upgrade() -> None:
    op.create_table(
        "execution_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_package_id", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("calendar_proposal_id", sa.Integer(), nullable=True),
        sa.Column("action_type", execution_action_type, nullable=False),
        sa.Column("status", execution_status, nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_proposal_id"], ["calendar_action_proposals.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["draft_replies.id"]),
        sa.ForeignKeyConstraint(["review_package_id"], ["proposed_action_review_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "action_type", name="uq_execution_draft_action"),
        sa.UniqueConstraint("review_package_id", "action_type", name="uq_execution_review_action"),
    )
    op.create_index(
        op.f("ix_execution_records_calendar_proposal_id"),
        "execution_records",
        ["calendar_proposal_id"],
        unique=False,
    )
    op.create_index(op.f("ix_execution_records_draft_id"), "execution_records", ["draft_id"], unique=False)
    op.create_index(
        op.f("ix_execution_records_review_package_id"),
        "execution_records",
        ["review_package_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_records_status_created",
        "execution_records",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "execution_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execution_record_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_record_id"], ["execution_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execution_audit_logs_execution_record_id"),
        "execution_audit_logs",
        ["execution_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_audit_record_created",
        "execution_audit_logs",
        ["execution_record_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_audit_record_created", table_name="execution_audit_logs")
    op.drop_index(
        op.f("ix_execution_audit_logs_execution_record_id"),
        table_name="execution_audit_logs",
    )
    op.drop_table("execution_audit_logs")
    op.drop_index("ix_execution_records_status_created", table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_review_package_id"), table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_draft_id"), table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_calendar_proposal_id"), table_name="execution_records")
    op.drop_table("execution_records")
