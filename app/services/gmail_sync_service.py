from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.connectors.gmail.client import GmailConnector
from app.models.entities import (
    BodyStoredMode,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
)
from app.services.attention_service import upsert_attention_item
from app.services.classification_service import classify_and_persist


def _find_or_create_contact(db: Session, sender_email: str | None, sender_name: str | None) -> Contact | None:
    if not sender_email:
        return None
    contact = db.query(Contact).filter_by(primary_email=sender_email).first()
    if contact:
        return contact
    contact = Contact(display_name=sender_name or sender_email, primary_email=sender_email)
    db.add(contact)
    db.flush()
    return contact


def sync_gmail_messages(db: Session, since: datetime | None = None) -> int:
    connector = GmailConnector()
    messages = connector.fetch_recent_messages(limit=100, since=since)
    synced = 0

    for item in messages:
        contact = _find_or_create_contact(db, item.sender_email, item.sender_display_name)

        thread = (
            db.query(MessageThread)
            .filter_by(source_type=item.source_type, source_thread_id=item.source_thread_id)
            .first()
        )
        if not thread:
            thread = MessageThread(
                source_type=item.source_type,
                source_thread_id=item.source_thread_id,
                normalized_subject=item.subject,
                contact_id=contact.id if contact else None,
                unread_count=0,
                last_message_at=item.received_at,
            )
            db.add(thread)
            db.flush()

        existing = (
            db.query(Message)
            .filter_by(source_type=item.source_type, source_message_id=item.source_message_id)
            .first()
        )
        if existing:
            continue

        message = Message(
            thread_id=thread.id,
            source_type=item.source_type,
            source_message_id=item.source_message_id,
            sender_display_name=item.sender_display_name,
            sender_email=item.sender_email,
            received_at=item.received_at or datetime.now(UTC),
            subject=item.subject,
            snippet=item.snippet,
            body_text=item.body_text,
            body_stored_mode=BodyStoredMode.FULL_TEXT if item.body_text else BodyStoredMode.SNIPPET_ONLY,
            is_unread=item.is_unread,
            has_attachments=item.has_attachments,
        )
        db.add(message)
        db.flush()

        classification = classify_and_persist(message)
        db.add(classification)
        db.flush()

        thread.unread_count += 1 if message.is_unread else 0
        thread.last_message_at = max(thread.last_message_at or message.received_at, message.received_at)

        upsert_attention_item(db, contact, thread, message, classification)
        synced += 1

    db.commit()
    return synced
