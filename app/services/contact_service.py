from sqlalchemy.orm import Session

from app.models.entities import Contact

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
    contact.importance_tier = max(contact.importance_tier, 4)
    db.commit()
    db.refresh(contact)
    return contact


def mark_contact_noise(db: Session, sender_email: str) -> Contact:
    contact = db.query(Contact).filter_by(primary_email=sender_email).first()
    if not contact:
        contact = Contact(display_name=sender_email, primary_email=sender_email)
        db.add(contact)
        db.flush()
    contact.is_noise = True
    contact.importance_tier = 0
    db.commit()
    db.refresh(contact)
    return contact
