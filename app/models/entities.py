from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BodyStoredMode(StrEnum):
    METADATA_ONLY = "metadata_only"
    SNIPPET_ONLY = "snippet_only"
    FULL_TEXT = "full_text"


class AttentionStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    REPLIED_ELSEWHERE = "replied_elsewhere"


class DraftStatus(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    primary_email: Mapped[str | None] = mapped_column(String(255), unique=True)
    primary_phone: Mapped[str | None] = mapped_column(String(50))
    relationship_type: Mapped[str | None] = mapped_column(String(50))
    importance_tier: Mapped[int] = mapped_column(Integer, default=1)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    is_noise: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_channel: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ContactAlias(Base):
    __tablename__ = "contact_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    source_system: Mapped[str] = mapped_column(String(50))
    source_identifier: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str | None] = mapped_column(String(255))

    contact: Mapped[Contact] = relationship()


class SourceAccount(Base):
    __tablename__ = "source_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50))
    account_identifier: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SourceSyncState(Base):
    __tablename__ = "source_sync_states"
    __table_args__ = (
        UniqueConstraint("source_type", "account_identifier", name="uq_sync_state_source_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50))
    account_identifier: Mapped[str] = mapped_column(String(255))
    high_water_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    high_water_message_id: Mapped[str | None] = mapped_column(String(255))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    last_inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    last_skipped_duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_thread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MessageThread(Base):
    __tablename__ = "message_threads"
    __table_args__ = (UniqueConstraint("source_type", "source_thread_id", name="uq_thread_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50))
    source_thread_id: Mapped[str] = mapped_column(String(255))
    normalized_subject: Mapped[str | None] = mapped_column(String(500))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    requires_attention_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    contact: Mapped[Contact | None] = relationship()


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("source_type", "source_message_id", name="uq_message_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("message_threads.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50))
    source_message_id: Mapped[str] = mapped_column(String(255))
    sender_display_name: Mapped[str | None] = mapped_column(String(255))
    sender_email: Mapped[str | None] = mapped_column(String(255), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    subject: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_stored_mode: Mapped[BodyStoredMode] = mapped_column(
        Enum(BodyStoredMode), default=BodyStoredMode.SNIPPET_ONLY
    )
    is_unread: Mapped[bool] = mapped_column(Boolean, default=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    thread: Mapped[MessageThread] = relationship()


class MessageClassification(Base):
    __tablename__ = "message_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), unique=True)
    requires_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency_level: Mapped[int] = mapped_column(Integer, default=0)
    is_human_personal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_client_work: Mapped[bool] = mapped_column(Boolean, default=False)
    is_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_newsletter: Mapped[bool] = mapped_column(Boolean, default=False)
    is_receipt: Mapped[bool] = mapped_column(Boolean, default=False)
    is_group_noise: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system_notification: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0"))
    classification_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped[Message] = relationship()


class AttentionItem(Base):
    __tablename__ = "attention_items"
    __table_args__ = (
        Index("uq_attention_items_thread_message", "thread_id", "message_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    thread_id: Mapped[int] = mapped_column(ForeignKey("message_threads.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    attention_score: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str | None] = mapped_column(String(500))
    recommended_action: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[AttentionStatus] = mapped_column(
        Enum(AttentionStatus), default=AttentionStatus.NEW
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    contact: Mapped[Contact | None] = relationship(foreign_keys=[contact_id])
    thread: Mapped[MessageThread] = relationship()
    message: Mapped[Message | None] = relationship(foreign_keys=[message_id])


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    audience_type: Mapped[str | None] = mapped_column(String(100))
    tone_description: Mapped[str | None] = mapped_column(String(500))
    formality_level: Mapped[int | None] = mapped_column(Integer)
    humor_level: Mapped[int | None] = mapped_column(Integer)
    apology_style: Mapped[str | None] = mapped_column(String(255))
    signoff_style: Mapped[str | None] = mapped_column(String(255))
    preferred_phrases: Mapped[str | None] = mapped_column(Text)
    banned_phrases: Mapped[str | None] = mapped_column(Text)
    max_length_preference: Mapped[int | None] = mapped_column(Integer)


class DraftReply(Base):
    __tablename__ = "draft_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("message_threads.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    voice_profile_id: Mapped[int | None] = mapped_column(ForeignKey("voice_profiles.id"))
    draft_text: Mapped[str] = mapped_column(Text)
    status: Mapped[DraftStatus] = mapped_column(Enum(DraftStatus), default=DraftStatus.GENERATED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    feedback_type: Mapped[str] = mapped_column(String(100))
    feedback_text: Mapped[str | None] = mapped_column(Text)
    original_value: Mapped[str | None] = mapped_column(String(500))
    corrected_value: Mapped[str | None] = mapped_column(String(500))
    original_classification_summary: Mapped[str | None] = mapped_column(String(500))
    corrected_label: Mapped[str | None] = mapped_column(String(100))
    corrected_importance: Mapped[int | None] = mapped_column(Integer)
    corrected_requires_reply: Mapped[bool | None] = mapped_column(Boolean)
    corrected_is_noise: Mapped[bool | None] = mapped_column(Boolean)
    corrected_is_newsletter: Mapped[bool | None] = mapped_column(Boolean)
    corrected_is_client_work: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped[Message | None] = relationship(foreign_keys=[message_id])
    contact: Mapped[Contact | None] = relationship(foreign_keys=[contact_id])
