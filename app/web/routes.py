from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
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
from app.services.contact_service import (
    CONTACT_STATUS_OPTIONS,
    PREFERRED_CHANNEL_OPTIONS,
    SUPPORTED_RELATIONSHIP_TYPES,
    contact_alias_emails,
    contact_status,
    create_contact_profile,
    find_contact_by_sender_email,
    mark_contact_noise,
    mark_contact_vip,
    normalize_email,
    reset_contact_status,
    update_contact_profile,
)
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
            contact = find_contact_by_sender_email(db, message.sender_email)
        feedback = (
            db.query(UserFeedback)
            .filter_by(message_id=message_id)
            .order_by(UserFeedback.created_at.desc())
            .limit(10)
            .all()
        )
        contact_feedback = []
        contact_aliases = []
        if contact:
            contact_aliases = contact_alias_emails(db, contact)
            contact_feedback = (
                db.query(UserFeedback)
                .filter_by(contact_id=contact.id)
                .order_by(UserFeedback.created_at.desc())
                .limit(5)
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
            "contact_aliases": contact_aliases if message else [],
            "contact_feedback": contact_feedback if message else [],
            "contact_status": contact_status(contact),
            "feedback": feedback,
            "correction_labels": CORRECTION_LABELS,
            "friendly_label": friendly_classification_label(classification),
            "classification_tags": classification_tags(classification),
        },
        status_code=status_code,
    )


@web_router.get("/contacts")
def contacts_index(request: Request, db: Session = Depends(get_db)):
    contacts = (
        db.query(Contact)
        .order_by(Contact.is_vip.desc(), Contact.is_noise.asc(), Contact.updated_at.desc())
        .limit(200)
        .all()
    )
    feedback_counts = dict(
        db.query(UserFeedback.contact_id, func.count(UserFeedback.id))
        .filter(UserFeedback.contact_id.is_not(None))
        .group_by(UserFeedback.contact_id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "contacts.html",
        {
            "contacts": contacts,
            "aliases_by_contact": {
                contact.id: contact_alias_emails(db, contact) for contact in contacts
            },
            "feedback_counts": feedback_counts,
            "relationship_types": SUPPORTED_RELATIONSHIP_TYPES,
            "status_options": CONTACT_STATUS_OPTIONS,
            "preferred_channels": PREFERRED_CHANNEL_OPTIONS,
            "contact_error": request.query_params.get("contact_error"),
        },
    )


@web_router.post("/contacts")
def web_create_contact(
    display_name: str | None = Form(None),
    primary_email: str | None = Form(None),
    aliases: str | None = Form(None),
    relationship_type: str = Form("unknown"),
    importance_tier: int = Form(1),
    preferred_channel: str | None = Form(None),
    notes: str | None = Form(None),
    status: str = Form("normal"),
    db: Session = Depends(get_db),
):
    try:
        contact = create_contact_profile(
            db,
            display_name=display_name,
            primary_email=primary_email,
            aliases_text=aliases,
            relationship_type=relationship_type,
            importance_tier=importance_tier,
            preferred_channel=preferred_channel,
            notes=notes,
            status=status,
        )
    except ValueError:
        return RedirectResponse(url="/contacts?contact_error=invalid", status_code=303)
    return RedirectResponse(url=f"/contacts/{contact.id}", status_code=303)


@web_router.get("/contacts/{contact_id}")
def contact_detail(contact_id: int, request: Request, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        return templates.TemplateResponse(
            request,
            "contact_detail.html",
            {"contact": None},
            status_code=404,
        )

    emails = set(contact_alias_emails(db, contact))
    primary_email = normalize_email(contact.primary_email)
    if primary_email:
        emails.add(primary_email)
    filters = [Message.thread.has(contact_id=contact.id)]
    if emails:
        filters.append(func.lower(Message.sender_email).in_(emails))
    recent_messages = (
        db.query(Message).filter(or_(*filters)).order_by(Message.received_at.desc()).limit(25).all()
    )
    feedback = (
        db.query(UserFeedback)
        .filter_by(contact_id=contact.id)
        .order_by(UserFeedback.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "contact_detail.html",
        {
            "contact": contact,
            "aliases": contact_alias_emails(db, contact),
            "aliases_text": "\n".join(contact_alias_emails(db, contact)),
            "feedback": feedback,
            "recent_messages": recent_messages,
            "relationship_types": SUPPORTED_RELATIONSHIP_TYPES,
            "status_options": CONTACT_STATUS_OPTIONS,
            "preferred_channels": PREFERRED_CHANNEL_OPTIONS,
            "contact_status": contact_status(contact),
            "contact_error": request.query_params.get("contact_error"),
        },
    )


@web_router.post("/contacts/{contact_id}/edit")
def web_update_contact(
    contact_id: int,
    display_name: str | None = Form(None),
    primary_email: str | None = Form(None),
    aliases: str | None = Form(None),
    relationship_type: str = Form("unknown"),
    importance_tier: int = Form(1),
    preferred_channel: str | None = Form(None),
    notes: str | None = Form(None),
    status: str = Form("normal"),
    db: Session = Depends(get_db),
):
    try:
        update_contact_profile(
            db,
            contact_id,
            display_name=display_name,
            primary_email=primary_email,
            aliases_text=aliases,
            relationship_type=relationship_type,
            importance_tier=importance_tier,
            preferred_channel=preferred_channel,
            notes=notes,
            status=status,
        )
    except ValueError:
        return RedirectResponse(
            url=f"/contacts/{contact_id}?contact_error=invalid", status_code=303
        )
    return RedirectResponse(url=f"/contacts/{contact_id}", status_code=303)


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
