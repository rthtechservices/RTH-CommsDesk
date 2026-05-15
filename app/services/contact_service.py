from __future__ import annotations

from email.utils import parseaddr

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    ContactAlias,
    Message,
    MessageClassification,
    MessageThread,
    UserFeedback,
)

SUPPORTED_RELATIONSHIP_TYPES = [
    "partner",
    "close_friend",
    "friend",
    "family",
    "client",
    "prospect",
    "vendor",
    "newsletter",
    "system",
    "unknown",
]

CONTACT_STATUS_OPTIONS = ["normal", "vip", "noise"]

PREFERRED_CHANNEL_OPTIONS = [
    "gmail",
    "email",
    "phone",
    "sms",
    "outlook",
    "teams",
    "unknown",
]

RELATIONSHIP_WEIGHTS = {
    "partner": 35,
    "close_friend": 28,
    "family": 24,
    "client": 22,
    "friend": 14,
    "prospect": 10,
    "vendor": 6,
    "newsletter": -18,
    "system": -14,
    "unknown": 0,
}


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    _, parsed_email = parseaddr(email)
    normalized = (parsed_email or email).strip().lower()
    return normalized or None


def parse_aliases(raw_aliases: str | None) -> list[str]:
    if not raw_aliases:
        return []
    normalized = raw_aliases.replace(";", "\n").replace(",", "\n")
    aliases: list[str] = []
    seen: set[str] = set()
    for raw_alias in normalized.splitlines():
        alias = normalize_email(raw_alias)
        if alias and "@" in alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def contact_status(contact: Contact | None) -> str:
    if not contact:
        return "unknown"
    if contact.is_vip:
        return "vip"
    if contact.is_noise:
        return "noise"
    return "normal"


def contact_alias_emails(db: Session, contact: Contact) -> list[str]:
    aliases = (
        db.query(ContactAlias.email)
        .filter(ContactAlias.contact_id == contact.id, ContactAlias.email.is_not(None))
        .order_by(ContactAlias.email)
        .all()
    )
    return [email for (email,) in aliases if email]


def find_contact_by_sender_email(db: Session, sender_email: str | None) -> Contact | None:
    normalized_email = normalize_email(sender_email)
    if not normalized_email:
        return None

    contact = (
        db.query(Contact).filter(func.lower(Contact.primary_email) == normalized_email).first()
    )
    if contact:
        return contact

    alias = (
        db.query(ContactAlias).filter(func.lower(ContactAlias.email) == normalized_email).first()
    )
    return alias.contact if alias else None


def ensure_contact_for_sender(
    db: Session, sender_email: str | None, sender_name: str | None
) -> Contact | None:
    normalized_email = normalize_email(sender_email)
    if not normalized_email:
        return None

    contact = find_contact_by_sender_email(db, normalized_email)
    if contact:
        if sender_name and not contact.display_name:
            contact.display_name = sender_name
        return contact

    contact = Contact(
        display_name=sender_name or normalized_email,
        primary_email=normalized_email,
        relationship_type="unknown",
    )
    db.add(contact)
    db.flush()
    return contact


def contact_importance_weight(contact: Contact | None) -> int:
    if not contact:
        return 0
    score = 0
    score += min(max(contact.importance_tier or 0, 0), 5) * 5
    score += RELATIONSHIP_WEIGHTS.get((contact.relationship_type or "unknown").lower(), 0)
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
    contact.importance_tier = max(contact.importance_tier or 0, 4)
    recalculate_attention_for_contact(db, contact)
    db.commit()
    db.refresh(contact)
    return contact


def mark_contact_noise(db: Session, sender_email: str) -> Contact:
    normalized_email = normalize_email(sender_email)
    if not normalized_email:
        raise ValueError("Sender email is required")
    contact = find_contact_by_sender_email(db, normalized_email)
    if not contact:
        contact = Contact(
            display_name=normalized_email,
            primary_email=normalized_email,
            relationship_type="unknown",
        )
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
    contact.importance_tier = max(contact.importance_tier or 0, 1)
    recalculate_attention_for_contact(db, contact)
    db.commit()
    db.refresh(contact)
    return contact


def create_contact_profile(
    db: Session,
    *,
    display_name: str | None,
    primary_email: str | None,
    relationship_type: str,
    importance_tier: int,
    preferred_channel: str | None,
    notes: str | None,
    status: str,
    aliases_text: str | None = None,
) -> Contact:
    normalized_email = normalize_email(primary_email)
    if normalized_email and find_contact_by_sender_email(db, normalized_email):
        raise ValueError("A contact already exists for that email or alias")

    contact = Contact(
        display_name=_clean_optional(display_name) or normalized_email or "New contact",
        primary_email=normalized_email,
        relationship_type=_validated_relationship(relationship_type),
        importance_tier=_validated_importance(importance_tier),
        preferred_channel=_clean_optional(preferred_channel),
        notes=_clean_optional(notes),
    )
    _apply_status(contact, status)
    db.add(contact)
    db.flush()
    _replace_aliases(db, contact, aliases_text)

    db.add(
        UserFeedback(
            contact_id=contact.id,
            feedback_type="contact_profile_created",
            corrected_value=summarize_contact_profile(db, contact),
        )
    )
    recalculate_attention_for_contact(db, contact, dismiss_noise_items=contact.is_noise)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact_profile(
    db: Session,
    contact_id: int,
    *,
    display_name: str | None,
    primary_email: str | None,
    relationship_type: str,
    importance_tier: int,
    preferred_channel: str | None,
    notes: str | None,
    status: str,
    aliases_text: str | None = None,
) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise ValueError("Contact not found")

    original_summary = summarize_contact_profile(db, contact)
    normalized_email = normalize_email(primary_email)
    if normalized_email:
        existing = (
            db.query(Contact)
            .filter(func.lower(Contact.primary_email) == normalized_email, Contact.id != contact.id)
            .first()
        )
        if existing:
            raise ValueError("Another contact already uses that primary email")

    contact.display_name = _clean_optional(display_name) or normalized_email or contact.display_name
    contact.primary_email = normalized_email
    contact.relationship_type = _validated_relationship(relationship_type)
    contact.importance_tier = _validated_importance(importance_tier)
    contact.preferred_channel = _clean_optional(preferred_channel)
    contact.notes = _clean_optional(notes)
    _apply_status(contact, status)
    db.flush()
    _replace_aliases(db, contact, aliases_text)
    corrected_summary = summarize_contact_profile(db, contact)

    if original_summary != corrected_summary:
        db.add(
            UserFeedback(
                contact_id=contact.id,
                feedback_type="contact_profile_update",
                original_value=original_summary,
                corrected_value=corrected_summary,
            )
        )

    recalculate_attention_for_contact(db, contact, dismiss_noise_items=contact.is_noise)
    db.commit()
    db.refresh(contact)
    return contact


def summarize_contact_profile(db: Session, contact: Contact) -> str:
    aliases = ", ".join(contact_alias_emails(db, contact)) or "none"
    summary = (
        f"name={contact.display_name or 'none'}; "
        f"email={contact.primary_email or 'none'}; "
        f"aliases={aliases}; "
        f"relationship={contact.relationship_type or 'unknown'}; "
        f"tier={contact.importance_tier}; "
        f"channel={contact.preferred_channel or 'none'}; "
        f"status={contact_status(contact)}"
    )
    return summary[:500]


def recalculate_attention_for_contact(
    db: Session, contact: Contact, dismiss_noise_items: bool = False
) -> None:
    from app.services.attention_service import upsert_attention_item

    emails = set(contact_alias_emails(db, contact))
    primary_email = normalize_email(contact.primary_email)
    if primary_email:
        emails.add(primary_email)

    filters = [MessageThread.contact_id == contact.id]
    if emails:
        filters.append(func.lower(Message.sender_email).in_(emails))

    records = (
        db.query(Message, MessageThread, MessageClassification)
        .join(MessageThread, Message.thread_id == MessageThread.id)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(or_(*filters))
        .all()
    )
    touched_thread_ids: set[int] = set()
    for message, thread, classification in records:
        thread.contact_id = contact.id
        item = upsert_attention_item(db, contact, thread, message, classification)
        if dismiss_noise_items and contact.is_noise:
            item.status = AttentionStatus.DISMISSED
        touched_thread_ids.add(thread.id)

    for thread_id in touched_thread_ids:
        max_score = (
            db.query(func.max(AttentionItem.attention_score))
            .filter(AttentionItem.thread_id == thread_id)
            .scalar()
            or 0
        )
        thread = db.get(MessageThread, thread_id)
        if thread:
            thread.requires_attention_score = max_score


def _replace_aliases(db: Session, contact: Contact, aliases_text: str | None) -> None:
    desired_aliases = set(parse_aliases(aliases_text))
    primary_email = normalize_email(contact.primary_email)
    desired_aliases.discard(primary_email)

    current_aliases = db.query(ContactAlias).filter_by(contact_id=contact.id).all()
    for alias in current_aliases:
        if normalize_email(alias.email) not in desired_aliases:
            db.delete(alias)

    for email in sorted(desired_aliases):
        existing = db.query(ContactAlias).filter(func.lower(ContactAlias.email) == email).first()
        if existing:
            existing.contact_id = contact.id
            existing.source_system = existing.source_system or "manual"
            continue
        db.add(
            ContactAlias(
                contact_id=contact.id,
                source_system="manual",
                source_identifier=email,
                email=email,
                display_name=contact.display_name,
            )
        )
    db.flush()


def _validated_relationship(value: str | None) -> str:
    relationship = (value or "unknown").strip().lower()
    if relationship not in SUPPORTED_RELATIONSHIP_TYPES:
        raise ValueError("Unsupported relationship type")
    return relationship


def _validated_importance(value: int | None) -> int:
    if value is None:
        return 1
    return min(max(int(value), 0), 5)


def _apply_status(contact: Contact, status: str | None) -> None:
    normalized_status = (status or "normal").strip().lower()
    if normalized_status not in CONTACT_STATUS_OPTIONS:
        raise ValueError("Unsupported contact status")
    contact.is_vip = normalized_status == "vip"
    contact.is_noise = normalized_status == "noise"
    if contact.is_vip:
        contact.importance_tier = max(contact.importance_tier or 0, 4)
    if contact.is_noise:
        contact.importance_tier = 0


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
