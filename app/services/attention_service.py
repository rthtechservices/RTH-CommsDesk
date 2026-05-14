from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.entities import AttentionItem, Contact, Message, MessageClassification, MessageThread
from app.services.contact_service import contact_importance_weight


def calculate_attention_score(
    contact: Contact | None,
    thread: MessageThread,
    message: Message,
    classification: MessageClassification,
) -> int:
    score = 0
    score += 40 if contact and contact.is_vip else 0
    score += contact_importance_weight(contact)
    score += min(thread.unread_count * 3, 15)

    age_hours = max((datetime.now(UTC) - message.received_at).total_seconds() / 3600, 0)
    if age_hours > 24:
        score += 8
    elif age_hours > 6:
        score += 4

    if classification.requires_reply:
        score += 20
    score += classification.urgency_level * 10
    if classification.is_client_work:
        score += 12

    if classification.is_marketing:
        score -= 25
    if classification.is_newsletter:
        score -= 20
    if contact and contact.is_noise:
        score -= 35

    return max(score, 0)


def upsert_attention_item(
    db: Session,
    contact: Contact | None,
    thread: MessageThread,
    message: Message,
    classification: MessageClassification,
) -> AttentionItem:
    score = calculate_attention_score(contact, thread, message, classification)
    item = db.query(AttentionItem).filter_by(thread_id=thread.id, message_id=message.id).first()
    if not item:
        item = AttentionItem(contact_id=contact.id if contact else None, thread_id=thread.id, message_id=message.id)
        db.add(item)

    item.attention_score = score
    item.reason = classification.classification_reason
    item.recommended_action = "Reply" if classification.requires_reply else "Review"
    return item


def build_attention_queue(db: Session) -> list[AttentionItem]:
    return (
        db.query(AttentionItem)
        .order_by(desc(AttentionItem.attention_score), desc(AttentionItem.updated_at))
        .limit(100)
        .all()
    )
