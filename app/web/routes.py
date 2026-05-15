from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
    UserFeedback,
)
from app.services.attention_service import build_attention_queue
from app.services.contact_service import mark_contact_noise, mark_contact_vip, reset_contact_status
from app.services.draft_service import generate_draft_placeholder
from app.services.feedback_service import (
    CORRECTION_LABELS,
    apply_message_correction,
    classification_tags,
    friendly_classification_label,
)
from app.services.gmail_sync_service import get_sync_state, sync_gmail_messages

web_router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@web_router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    attention = build_attention_queue(db)[:30]
    message_ids = [item.message_id for item in attention if item.message_id]
    classifications = {
        c.message_id: c
        for c in db.query(MessageClassification)
        .filter(MessageClassification.message_id.in_(message_ids))
        .all()
    }
    attention_rows = [
        {
            "item": item,
            "message": item.message,
            "classification": classifications.get(item.message_id),
            "label": friendly_classification_label(classifications.get(item.message_id)),
            "tags": classification_tags(classifications.get(item.message_id)),
        }
        for item in attention
    ]
    vip_contacts = (
        db.query(Contact).filter_by(is_vip=True).order_by(Contact.updated_at.desc()).limit(20).all()
    )
    unread_human = (
        db.query(Message)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(Message.is_unread.is_(True), MessageClassification.is_human_personal.is_(True))
        .order_by(Message.received_at.desc())
        .limit(20)
        .all()
    )
    suspected_noise = (
        db.query(Message)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(
            MessageClassification.is_marketing.is_(True)
            | MessageClassification.is_newsletter.is_(True)
        )
        .order_by(Message.received_at.desc())
        .limit(20)
        .all()
    )
    sync_state = get_sync_state(db)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "attention": attention,
            "attention_rows": attention_rows,
            "vip_contacts": vip_contacts,
            "unread_human": unread_human,
            "suspected_noise": suspected_noise,
            "sync_state": sync_state,
            "sync_error": request.query_params.get("sync_error"),
        },
    )


@web_router.post("/sync/gmail")
def web_sync_gmail(resync: bool = Form(False), db: Session = Depends(get_db)):
    try:
        sync_gmail_messages(db, force_resync=resync)
    except (FileNotFoundError, RuntimeError):
        return RedirectResponse(url="/?sync_error=configuration", status_code=303)
    except Exception:
        return RedirectResponse(url="/?sync_error=failed", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@web_router.get("/messages/{message_id}")
def message_detail(message_id: int, request: Request, db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    classification = None
    attention_item = None
    contact = None
    feedback = []
    status_code = 200
    if message:
        classification = db.query(MessageClassification).filter_by(message_id=message_id).first()
        attention_item = db.query(AttentionItem).filter_by(message_id=message_id).first()
        if message.thread and message.thread.contact_id:
            contact = db.get(Contact, message.thread.contact_id)
        elif message.sender_email:
            contact = db.query(Contact).filter_by(primary_email=message.sender_email).first()
        feedback = (
            db.query(UserFeedback)
            .filter_by(message_id=message_id)
            .order_by(UserFeedback.created_at.desc())
            .limit(10)
            .all()
        )
    else:
        status_code = 404
    return templates.TemplateResponse(
        request,
        "message_detail.html",
        {
            "message": message,
            "classification": classification,
            "attention_item": attention_item,
            "contact": contact,
            "feedback": feedback,
            "correction_labels": CORRECTION_LABELS,
            "friendly_label": friendly_classification_label(classification),
            "classification_tags": classification_tags(classification),
        },
        status_code=status_code,
    )


@web_router.post("/contacts/{contact_id}/vip")
def web_mark_vip(contact_id: int, db: Session = Depends(get_db)):
    try:
        mark_contact_vip(db, contact_id)
    except ValueError:
        pass
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/contacts/{contact_id}/normal")
def web_reset_contact(contact_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        reset_contact_status(db, contact_id)
    except ValueError:
        pass
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)


@web_router.post("/contacts/noise")
def web_mark_noise(sender_email: str = Form(...), db: Session = Depends(get_db)):
    try:
        mark_contact_noise(db, sender_email)
    except ValueError:
        pass
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/attention/{attention_id}/review")
def web_mark_reviewed(attention_id: int, db: Session = Depends(get_db)):
    item = db.get(AttentionItem, attention_id)
    if item:
        item.status = AttentionStatus.REVIEWED
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/messages/{message_id}/requires-reply")
def web_requires_reply(message_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        apply_message_correction(db, message_id=message_id, corrected_label="needs_reply")
    except ValueError:
        pass
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
    )


@web_router.post("/messages/{message_id}/correct-classification")
def web_correct_classification(
    message_id: int,
    request: Request,
    corrected_label: str = Form(...),
    corrected_importance: int | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        apply_message_correction(
            db,
            message_id=message_id,
            corrected_label=corrected_label,
            corrected_importance=corrected_importance,
            notes=notes,
        )
    except ValueError:
        pass
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
    )


@web_router.post("/messages/{message_id}/generate-draft")
def web_generate_draft(message_id: int, request: Request, db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    if message:
        generate_draft_placeholder(db, message)
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
    )
