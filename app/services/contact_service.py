from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
)

RELATIONSHIP_WEIGHTS = {
    "partner": 30,
    "family": 25,
    "friend": 15,
    "client": 20,
    "vendor": 8,
}


def contact_importance_weight(contact: Contact | None) -> int:
    if not contact:
        return 0
    score = 0
    score += min(max(contact.importance_tier, 0), 5) * 5
    score += RELATIONSHIP_WEIGHTS.get((contact.relationship_type or "").lower(), 0)
    if contact.is_vip:
        score += 40
    if contact.is_noise:
        score -= 35
    return score


def mark_contact_vip(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise ValueError("Contact not found")
    contact.is_vip = True
    contact.is_noise = False
    contact.importance_tier = max(contact.importance_tier, 4)
    recalculate_attention_for_contact(db, contact)
    db.commit()
    db.refresh(contact)
    return contact


def mark_contact_noise(db: Session, sender_email: str) -> Contact:
    sender_email = sender_email.strip()
    if not sender_email:
        raise ValueError("Sender email is required")
    contact = db.query(Contact).filter_by(primary_email=sender_email).first()
    if not contact:
        contact = Contact(display_name=sender_email, primary_email=sender_email)
        db.add(contact)
        db.flush()
    contact.is_noise = True
    contact.is_vip = False
    contact.importance_tier = 0
    recalculate_attention_for_contact(db, contact, dismiss_noise_items=True)
    db.commit()
    db.refresh(contact)
    return contact


def reset_contact_status(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise ValueError("Contact not found")
    contact.is_vip = False
    contact.is_noise = False
    contact.importance_tier = max(contact.importance_tier, 1)
    recalculate_attention_for_contact(db, contact)
    db.commit()
    db.refresh(contact)
    return contact


def recalculate_attention_for_contact(
    db: Session, contact: Contact, dismiss_noise_items: bool = False
) -> None:
    from app.services.attention_service import upsert_attention_item

    records = (
        db.query(Message, MessageThread, MessageClassification)
        .join(MessageThread, Message.thread_id == MessageThread.id)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(
            (Message.sender_email == contact.primary_email)
            | (MessageThread.contact_id == contact.id)
        )
        .all()
    )
    for message, thread, classification in records:
        if thread.contact_id is None:
            thread.contact_id = contact.id
        item = upsert_attention_item(db, contact, thread, message, classification)
        if dismiss_noise_items and contact.is_noise:
            item.status = AttentionStatus.DISMISSED
