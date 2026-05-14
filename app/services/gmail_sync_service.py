from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.connectors.gmail.client import GmailConnector
from app.core.config import get_settings
from app.models.entities import (
    BodyStoredMode,
    Contact,
    Message,
    MessageThread,
)
from app.services.attention_service import upsert_attention_item
from app.services.classification_service import classify_and_persist


def _find_or_create_contact(
    db: Session, sender_email: str | None, sender_name: str | None
) -> Contact | None:
    if not sender_email:
        return None
    contact = db.query(Contact).filter_by(primary_email=sender_email).first()
    if contact:
        return contact
    contact = Contact(display_name=sender_name or sender_email, primary_email=sender_email)
    db.add(contact)
    db.flush()
    return contact


def sync_gmail_messages(
    db: Session, since: datetime | None = None, connector: GmailConnector | None = None
) -> int:
    connector = connector or GmailConnector()
    settings = get_settings()
    messages = connector.fetch_recent_messages(limit=settings.gmail_read_max_results, since=since)
    synced = 0
    touched_thread_ids: set[int] = set()

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
        else:
            if contact and thread.contact_id is None:
                thread.contact_id = contact.id
            if item.subject and item.subject != thread.normalized_subject:
                thread.normalized_subject = item.subject

        existing = (
            db.query(Message)
            .filter_by(source_type=item.source_type, source_message_id=item.source_message_id)
            .first()
        )
        if existing:
            touched_thread_ids.add(thread.id)
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
            body_stored_mode=(
                BodyStoredMode.FULL_TEXT if item.body_text else BodyStoredMode.SNIPPET_ONLY
            ),
            is_unread=item.is_unread,
            has_attachments=item.has_attachments,
        )
        db.add(message)
        db.flush()

        classification = classify_and_persist(message, headers=item.headers)
        db.add(classification)
        db.flush()

        upsert_attention_item(db, contact, thread, message, classification)
        touched_thread_ids.add(thread.id)
        synced += 1

    for thread_id in touched_thread_ids:
        thread = db.get(MessageThread, thread_id)
        if not thread:
            continue
        thread.unread_count = (
            db.query(func.count(Message.id))
            .filter(Message.thread_id == thread_id, Message.is_unread.is_(True))
            .scalar()
            or 0
        )
        thread.last_message_at = (
            db.query(func.max(Message.received_at)).filter(Message.thread_id == thread_id).scalar()
            or thread.last_message_at
        )

    db.commit()
    return synced
