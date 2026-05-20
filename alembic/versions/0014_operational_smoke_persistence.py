"""operational smoke persistence

Revision ID: 0014_operational_smoke_persistence
Revises: 0013_execution_attempts_send_ready_drafts
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_operational_smoke_persistence"
down_revision = "0013_execution_attempts_send_ready_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_smoke_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.Enum("MANUAL", "API", "STARTUP", "CLI", name="operationalsmokemode"), nullable=False),
        sa.Column(
            "overall_status",
            sa.Enum("PASSED", "WARNING", "FAILED", name="operationalsmokestatus"),
            nullable=False,
        ),
        sa.Column("app_env", sa.String(length=50), nullable=True),
        sa.Column("ai_provider", sa.String(length=100), nullable=True),
        sa.Column("execution_provider", sa.String(length=100), nullable=True),
        sa.Column("external_write_dry_run", sa.Boolean(), nullable=False),
        sa.Column("operational_test_mode", sa.Boolean(), nullable=False),
        sa.Column("allowlist_configured", sa.Boolean(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("sanitized_detail_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_smoke_runs_started",
        "operational_smoke_runs",
        ["started_at"],
        unique=False,
    )
    op.create_table(
        "operational_smoke_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("smoke_run_id", sa.Integer(), nullable=False),
        sa.Column("check_key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PASSED",
                "WARNING",
                "FAILED",
                "SKIPPED",
                name="operationalsmokecheckstatus",
            ),
            nullable=False,
        ),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column(
            "external_write_performed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("sanitized_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["smoke_run_id"], ["operational_smoke_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_smoke_checks_run",
        "operational_smoke_checks",
        ["smoke_run_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_smoke_checks_smoke_run_id"),
        "operational_smoke_checks",
        ["smoke_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_smoke_checks_smoke_run_id"), table_name="operational_smoke_checks")
    op.drop_index("ix_operational_smoke_checks_run", table_name="operational_smoke_checks")
    op.drop_table("operational_smoke_checks")
    op.drop_index("ix_operational_smoke_runs_started", table_name="operational_smoke_runs")
    op.drop_table("operational_smoke_runs")
