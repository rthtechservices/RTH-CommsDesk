"""sent mail learning and voice calibration

Revision ID: 0007_sent_mail_learning
Revises: 0006_ai_review_packages
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_sent_mail_learning"
down_revision = "0006_ai_review_packages"
branch_labels = None
depends_on = None


inference_status = sa.Enum("PENDING", "APPROVED", "REJECTED", name="inferencestatus")


def upgrade() -> None:
    op.create_table(
        "sent_mail_learning_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_message_id", sa.String(length=255), nullable=False),
        sa.Column("source_thread_id", sa.String(length=255), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("snippet_excerpt", sa.String(length=500), nullable=True),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("is_reply", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_message_id",
            "recipient_email",
            name="uq_sent_learning_source_message_recipient",
        ),
    )
    op.create_index(
        op.f("ix_sent_mail_learning_records_recipient_email"),
        "sent_mail_learning_records",
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        "ix_sent_learning_contact_sent_at",
        "sent_mail_learning_records",
        ["contact_id", "sent_at"],
        unique=False,
    )

    op.create_table(
        "vip_inference_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("reply_ratio", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=False),
        sa.Column("status", inference_status, nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact_id", name="uq_vip_inference_contact"),
    )
    op.create_index(
        op.f("ix_vip_inference_candidates_contact_id"),
        "vip_inference_candidates",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "ix_vip_inference_score",
        "vip_inference_candidates",
        ["score"],
        unique=False,
    )

    op.create_table(
        "voice_guidance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("relationship_type", sa.String(length=50), nullable=True),
        sa.Column("salutation_style", sa.String(length=50), nullable=True),
        sa.Column("preferred_name", sa.String(length=255), nullable=True),
        sa.Column("tone_notes", sa.String(length=500), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", inference_status, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_voice_guidance_contact_id"), "voice_guidance", ["contact_id"], unique=False)
    op.create_index("ix_voice_guidance_status", "voice_guidance", ["status"], unique=False)
    op.create_index(
        "ix_voice_guidance_contact_relationship",
        "voice_guidance",
        ["contact_id", "relationship_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_voice_guidance_contact_relationship", table_name="voice_guidance")
    op.drop_index("ix_voice_guidance_status", table_name="voice_guidance")
    op.drop_index(op.f("ix_voice_guidance_contact_id"), table_name="voice_guidance")
    op.drop_table("voice_guidance")
    op.drop_index("ix_vip_inference_score", table_name="vip_inference_candidates")
    op.drop_index(op.f("ix_vip_inference_candidates_contact_id"), table_name="vip_inference_candidates")
    op.drop_table("vip_inference_candidates")
    op.drop_index("ix_sent_learning_contact_sent_at", table_name="sent_mail_learning_records")
    op.drop_index(
        op.f("ix_sent_mail_learning_records_recipient_email"), table_name="sent_mail_learning_records"
    )
    op.drop_table("sent_mail_learning_records")
