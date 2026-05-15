from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
)
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

    received_at = message.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    age_hours = max((datetime.now(UTC) - received_at).total_seconds() / 3600, 0)
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
    if classification.is_receipt and classification.urgency_level < 2:
        score -= 10
    if classification.is_system_notification and classification.urgency_level < 2:
        score -= 8
    if classification.is_group_noise and classification.urgency_level == 0:
        score -= 10
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
        item = AttentionItem(
            contact_id=contact.id if contact else None, thread_id=thread.id, message_id=message.id
        )
        db.add(item)

    item.contact_id = contact.id if contact else None
    item.attention_score = score
    item.reason = classification.classification_reason
    item.recommended_action = _recommended_action(classification)
    return item


def _recommended_action(classification: MessageClassification) -> str:
    if classification.requires_reply:
        return "Reply"
    if classification.urgency_level >= 2:
        return "Review soon"
    if classification.is_newsletter or classification.is_marketing or classification.is_group_noise:
        return "Skim or ignore"
    return "Review"


def build_attention_queue(db: Session, include_reviewed: bool = False) -> list[AttentionItem]:
    query = db.query(AttentionItem)
    if not include_reviewed:
        query = query.filter(AttentionItem.status == AttentionStatus.NEW)
    return (
        query.order_by(desc(AttentionItem.attention_score), desc(AttentionItem.updated_at))
        .limit(100)
        .all()
    )
