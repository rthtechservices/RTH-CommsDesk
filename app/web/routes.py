from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import AttentionItem, Contact, Message, MessageClassification
from app.services.contact_service import mark_contact_noise, mark_contact_vip
from app.services.draft_service import generate_draft_placeholder

web_router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@web_router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    attention = db.query(AttentionItem).order_by(desc(AttentionItem.attention_score)).limit(30).all()
    vip_contacts = db.query(Contact).filter_by(is_vip=True).order_by(desc(Contact.updated_at)).limit(20).all()
    unread_human = (
        db.query(Message)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(Message.is_unread.is_(True), MessageClassification.is_human_personal.is_(True))
        .order_by(desc(Message.received_at))
        .limit(20)
        .all()
    )
    suspected_noise = (
        db.query(Message)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(
            MessageClassification.is_marketing.is_(True) | MessageClassification.is_newsletter.is_(True)
        )
        .order_by(desc(Message.received_at))
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "attention": attention,
            "vip_contacts": vip_contacts,
            "unread_human": unread_human,
            "suspected_noise": suspected_noise,
        },
    )


@web_router.get("/messages/{message_id}")
def message_detail(message_id: int, request: Request, db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    classification = db.query(MessageClassification).filter_by(message_id=message_id).first()
    return templates.TemplateResponse(
        request,
        "message_detail.html",
        {"message": message, "classification": classification},
    )


@web_router.post("/contacts/{contact_id}/vip")
def web_mark_vip(contact_id: int, db: Session = Depends(get_db)):
    mark_contact_vip(db, contact_id)
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/contacts/noise")
def web_mark_noise(sender_email: str = Form(...), db: Session = Depends(get_db)):
    mark_contact_noise(db, sender_email)
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/attention/{attention_id}/review")
def web_mark_reviewed(attention_id: int, db: Session = Depends(get_db)):
    item = db.get(AttentionItem, attention_id)
    if item:
        item.status = "reviewed"
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/messages/{message_id}/requires-reply")
def web_requires_reply(message_id: int, db: Session = Depends(get_db)):
    c = db.query(MessageClassification).filter_by(message_id=message_id).first()
    if c:
        c.requires_reply = True
        c.classification_reason = "User marked requires reply"
        db.commit()
    return RedirectResponse(url=f"/messages/{message_id}", status_code=303)


@web_router.post("/messages/{message_id}/correct-classification")
def web_correct_classification(message_id: int, reason: str = Form(...), db: Session = Depends(get_db)):
    c = db.query(MessageClassification).filter_by(message_id=message_id).first()
    if c:
        c.classification_reason = f"Corrected: {reason}"
        db.commit()
    return RedirectResponse(url=f"/messages/{message_id}", status_code=303)


@web_router.post("/messages/{message_id}/generate-draft")
def web_generate_draft(message_id: int, db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    if message:
        generate_draft_placeholder(db, message)
    return RedirectResponse(url=f"/messages/{message_id}", status_code=303)
