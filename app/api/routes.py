from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import AttentionItem, AttentionStatus, Contact, Message, MessageClassification
from app.services.attention_service import build_attention_queue
from app.services.contact_service import mark_contact_noise, mark_contact_vip
from app.services.draft_service import generate_draft_placeholder
from app.services.gmail_sync_service import sync_gmail_messages

api_router = APIRouter()


@api_router.post("/sync/gmail")
def sync_gmail(db: Session = Depends(get_db)) -> dict:
    result = sync_gmail_messages(db)
    return {"synced": result}


@api_router.get("/attention")
def get_attention_queue(db: Session = Depends(get_db)) -> list[dict]:
    items = build_attention_queue(db)
    return [
        {
            "id": item.id,
            "score": item.attention_score,
            "reason": item.reason,
            "thread_id": item.thread_id,
            "status": item.status,
        }
        for item in items
    ]


@api_router.get("/messages/{message_id}")
def get_message(message_id: int, db: Session = Depends(get_db)) -> dict:
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    classification = db.query(MessageClassification).filter_by(message_id=message_id).first()
    return {
        "id": msg.id,
        "subject": msg.subject,
        "snippet": msg.snippet,
        "sender": msg.sender_email,
        "is_unread": msg.is_unread,
        "classification": classification.classification_reason if classification else None,
    }


@api_router.post("/contacts/{contact_id}/vip")
def set_vip(contact_id: int, db: Session = Depends(get_db)) -> dict:
    contact = mark_contact_vip(db, contact_id)
    return {"contact_id": contact.id, "is_vip": contact.is_vip}


@api_router.post("/contacts/noise")
def set_noise(sender_email: str = Form(...), db: Session = Depends(get_db)) -> dict:
    contact = mark_contact_noise(db, sender_email)
    return {"contact_id": contact.id, "is_noise": contact.is_noise}


@api_router.post("/attention/{attention_id}/review")
def mark_reviewed(attention_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(AttentionItem, attention_id)
    if not item:
        raise HTTPException(status_code=404, detail="Attention item not found")
    item.status = AttentionStatus.REVIEWED
    db.commit()
    return {"id": item.id, "status": item.status}


@api_router.post("/messages/{message_id}/requires-reply")
def force_requires_reply(message_id: int, db: Session = Depends(get_db)) -> dict:
    c = db.query(MessageClassification).filter_by(message_id=message_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Classification not found")
    c.requires_reply = True
    c.classification_reason = "User marked requires reply"
    db.commit()
    return {"message_id": message_id, "requires_reply": True}


@api_router.post("/messages/{message_id}/correct-classification")
def correct_classification(
    message_id: int,
    reason: str = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    c = db.query(MessageClassification).filter_by(message_id=message_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Classification not found")
    c.classification_reason = f"Corrected: {reason}"
    db.commit()
    return {"message_id": message_id, "reason": c.classification_reason}


@api_router.post("/messages/{message_id}/generate-draft")
def generate_draft(message_id: int, db: Session = Depends(get_db)) -> dict:
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    draft = generate_draft_placeholder(db, message)
    return {"draft_id": draft.id, "status": draft.status}


@api_router.get("/vip-contacts")
def vip_contacts(db: Session = Depends(get_db)) -> list[dict]:
    contacts = db.query(Contact).filter_by(is_vip=True).order_by(Contact.updated_at.desc()).limit(50).all()
    return [{"id": c.id, "display_name": c.display_name, "email": c.primary_email} for c in contacts]


@api_router.get("/unread-human")
def unread_human(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Message, MessageClassification)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(Message.is_unread.is_(True), MessageClassification.is_human_personal.is_(True))
        .order_by(desc(Message.received_at))
        .limit(50)
        .all()
    )
    return [{"id": m.id, "subject": m.subject, "sender": m.sender_email} for m, _ in rows]
