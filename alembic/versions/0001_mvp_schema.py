"""mvp schema

Revision ID: 0001_mvp_schema
Revises:
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_mvp_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=True, unique=True),
        sa.Column("primary_phone", sa.String(50), nullable=True),
        sa.Column("relationship_type", sa.String(50), nullable=True),
        sa.Column("importance_tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_vip", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_noise", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("preferred_channel", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "source_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("account_identifier", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "message_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_thread_id", sa.String(255), nullable=False),
        sa.Column("normalized_subject", sa.String(500), nullable=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_attention_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "source_thread_id", name="uq_thread_source"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_threads.id"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_message_id", sa.String(255), nullable=False),
        sa.Column("sender_display_name", sa.String(255), nullable=True),
        sa.Column("sender_email", sa.String(255), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_stored_mode", sa.String(20), nullable=False),
        sa.Column("is_unread", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "source_message_id", name="uq_message_source"),
    )

    op.create_table(
        "contact_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
    )

    op.create_table(
        "message_classifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False, unique=True),
        sa.Column("requires_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("urgency_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_human_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_client_work", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_marketing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_newsletter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_receipt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_group_noise", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_system_notification", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0.0"),
        sa.Column("classification_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "attention_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_threads.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("attention_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("recommended_action", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "voice_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("audience_type", sa.String(100), nullable=True),
        sa.Column("tone_description", sa.String(500), nullable=True),
        sa.Column("formality_level", sa.Integer(), nullable=True),
        sa.Column("humor_level", sa.Integer(), nullable=True),
        sa.Column("apology_style", sa.String(255), nullable=True),
        sa.Column("signoff_style", sa.String(255), nullable=True),
        sa.Column("preferred_phrases", sa.Text(), nullable=True),
        sa.Column("banned_phrases", sa.Text(), nullable=True),
        sa.Column("max_length_preference", sa.Integer(), nullable=True),
    )

    op.create_table(
        "draft_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_threads.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("voice_profile_id", sa.Integer(), sa.ForeignKey("voice_profiles.id"), nullable=True),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="generated"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("feedback_type", sa.String(100), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("original_value", sa.String(500), nullable=True),
        sa.Column("corrected_value", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_feedback")
    op.drop_table("draft_replies")
    op.drop_table("voice_profiles")
    op.drop_table("attention_items")
    op.drop_table("message_classifications")
    op.drop_table("contact_aliases")
    op.drop_table("messages")
    op.drop_table("message_threads")
    op.drop_table("source_accounts")
    op.drop_table("contacts")
