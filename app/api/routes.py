from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
)
from app.services.attention_service import build_attention_queue
from app.services.contact_service import mark_contact_noise, mark_contact_vip, reset_contact_status
from app.services.draft_service import create_draft_reply
from app.services.feedback_service import apply_message_correction
from app.services.gmail_sync_service import (
    fetch_full_gmail_conversation,
    get_sync_state,
    sync_gmail_backfill,
    sync_gmail_messages,
)

api_router = APIRouter()


@api_router.post("/sync/gmail")
def sync_gmail(resync: bool = Form(False), db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_gmail_messages(db, force_resync=resync)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail OAuth client secrets file is missing. Set GMAIL_CLIENT_SECRETS_FILE "
                "to a valid path before syncing."
            ),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.as_dict()


@api_router.post("/sync/gmail/backfill")
def backfill_gmail(db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_gmail_backfill(db)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail OAuth client secrets file is missing. Set GMAIL_CLIENT_SECRETS_FILE "
                "to a valid path before syncing."
            ),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.as_dict()


@api_router.get("/sync/gmail/status")
def gmail_sync_status(db: Session = Depends(get_db)) -> dict:
    state = get_sync_state(db)
    if not state:
        return {"configured": True, "last_sync": None}
    return {
        "configured": True,
        "source_type": state.source_type,
        "account_identifier": state.account_identifier,
        "high_water_received_at": (
            state.high_water_received_at.isoformat() if state.high_water_received_at else None
        ),
        "last_started_at": state.last_started_at.isoformat() if state.last_started_at else None,
        "last_finished_at": state.last_finished_at.isoformat() if state.last_finished_at else None,
        "last_successful_sync_at": (
            state.last_successful_sync_at.isoformat() if state.last_successful_sync_at else None
        ),
        "last_fetched_count": state.last_fetched_count,
        "last_inserted_count": state.last_inserted_count,
        "last_skipped_duplicate_count": state.last_skipped_duplicate_count,
        "last_updated_thread_count": state.last_updated_thread_count,
        "last_error": state.last_error,
        "backlog_next_page_token": state.backlog_next_page_token,
        "last_backfill_started_at": (
            state.last_backfill_started_at.isoformat() if state.last_backfill_started_at else None
        ),
        "last_backfill_finished_at": (
            state.last_backfill_finished_at.isoformat() if state.last_backfill_finished_at else None
        ),
        "last_backfill_fetched_count": state.last_backfill_fetched_count,
        "last_backfill_inserted_count": state.last_backfill_inserted_count,
        "last_backfill_skipped_duplicate_count": state.last_backfill_skipped_duplicate_count,
        "last_backfill_error": state.last_backfill_error,
    }


@api_router.get("/attention")
def get_attention_queue(
    include_reviewed: bool = False, db: Session = Depends(get_db)
) -> list[dict]:
    items = build_attention_queue(db, include_reviewed=include_reviewed)
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
    try:
        contact = mark_contact_vip(db, contact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"contact_id": contact.id, "is_vip": contact.is_vip}


@api_router.post("/contacts/{contact_id}/normal")
def set_contact_normal(contact_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        contact = reset_contact_status(db, contact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"contact_id": contact.id, "is_vip": contact.is_vip, "is_noise": contact.is_noise}


@api_router.post("/contacts/noise")
def set_noise(sender_email: str = Form(...), db: Session = Depends(get_db)) -> dict:
    try:
        contact = mark_contact_noise(db, sender_email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    try:
        result = apply_message_correction(db, message_id, corrected_label="needs_reply")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "message_id": message_id,
        "requires_reply": result.classification.requires_reply,
        "attention_score": result.attention_item.attention_score,
        "recommended_action": result.attention_item.recommended_action,
    }


@api_router.post("/messages/{message_id}/correct-classification")
def correct_classification(
    message_id: int,
    corrected_label: str = Form(...),
    corrected_importance: int | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = apply_message_correction(
            db,
            message_id=message_id,
            corrected_label=corrected_label,
            corrected_importance=corrected_importance,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "message_id": message_id,
        "corrected_label": result.feedback.corrected_label,
        "reason": result.classification.classification_reason,
        "attention_score": result.attention_item.attention_score,
        "recommended_action": result.attention_item.recommended_action,
        "status": result.attention_item.status,
    }


@api_router.post("/messages/{message_id}/generate-draft")
def generate_draft(
    message_id: int,
    voice_profile_id: int | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    draft = create_draft_reply(db, message, voice_profile_id=voice_profile_id)
    return {
        "draft_id": draft.id,
        "status": draft.status,
        "message_id": draft.message_id,
        "voice_profile_id": draft.voice_profile_id,
        "review_only": True,
    }


@api_router.post("/messages/{message_id}/fetch-conversation")
def fetch_conversation(message_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = fetch_full_gmail_conversation(db, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail OAuth client secrets file is missing. Set GMAIL_CLIENT_SECRETS_FILE "
                "to a valid path before fetching the conversation."
            ),
        ) from exc
    return result.as_dict()


@api_router.get("/vip-contacts")
def vip_contacts(db: Session = Depends(get_db)) -> list[dict]:
    contacts = (
        db.query(Contact).filter_by(is_vip=True).order_by(Contact.updated_at.desc()).limit(50).all()
    )
    return [
        {"id": c.id, "display_name": c.display_name, "email": c.primary_email} for c in contacts
    ]


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
