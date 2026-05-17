from fastapi import APIRouter, Depends, Form, Header, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    ExecutionRecord,
    Contact,
    InferenceStatus,
    Message,
    MessageClassification,
    ProposedActionReviewPackage,
    ReviewPackageStatus,
)
from app.services.attention_service import build_attention_queue
from app.services.analysis_service import analyze_message, update_review_package_status
from app.services.admin_service import clear_cached_content, run_retention_cleanup
from app.services.bulk_triage_service import (
    apply_bulk_action,
    automation_candidates_for_dashboard,
    get_bulk_backlog_page,
    refresh_automation_candidates,
    undo_bulk_action,
)
from app.services.contact_service import mark_contact_noise, mark_contact_vip, reset_contact_status
from app.services.draft_service import create_draft_reply
from app.services.feedback_service import apply_message_correction
from app.services.gmail_sync_service import (
    fetch_full_gmail_conversation,
    get_sync_state,
    sync_gmail_backfill,
    sync_gmail_messages,
)
from app.services.live_ai_client import ai_provider_status
from app.services.execution_service import (
    approve_execution,
    audit_entries_for_execution,
    cancel_execution,
    confirm_execution,
    list_execution_records,
    prepare_execution_for_draft,
    prepare_execution_for_review_package,
)
from app.services.external_connectors_service import (
    ingest_notification_summary,
    sync_outlook_messages,
    sync_teams_messages,
)
from app.services.voice_learning_service import (
    run_sent_mail_learning,
    update_vip_candidate_status,
    update_voice_guidance_status,
    vip_candidates_for_review,
    voice_guidance_for_review,
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


@api_router.post("/sync/outlook")
def sync_outlook(db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_outlook_messages(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.as_dict()


@api_router.post("/sync/teams")
def sync_teams(db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_teams_messages(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.as_dict()


@api_router.post("/notifications/webhook")
def notification_webhook(
    payload: dict,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    expected_secret = get_settings().notification_webhook_secret
    if expected_secret and x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    result = ingest_notification_summary(db, payload)
    return result.as_dict()


@api_router.post("/admin/retention/run")
def admin_retention_run(db: Session = Depends(get_db)) -> dict:
    return run_retention_cleanup(db).as_dict()


@api_router.post("/admin/cache/clear")
def admin_cache_clear(
    clear_message_bodies: bool = Form(False),
    clear_sent_learning_excerpts: bool = Form(False),
    db: Session = Depends(get_db),
) -> dict:
    return clear_cached_content(
        db,
        clear_message_bodies=clear_message_bodies,
        clear_sent_learning_excerpts=clear_sent_learning_excerpts,
    ).as_dict()


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


@api_router.get("/ai/status")
def ai_status() -> dict:
    status = ai_provider_status(get_settings())
    return {
        "requested_provider": status.requested_provider,
        "effective_provider": status.effective_provider,
        "model": status.model,
        "live_enabled": status.live_enabled,
        "fallback_provider": status.fallback_provider,
        "detail": status.detail,
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
        "provider_name": draft.provider_name,
        "review_only": True,
    }


@api_router.post("/messages/{message_id}/analyze")
def analyze_message_endpoint(message_id: int, db: Session = Depends(get_db)) -> dict:
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    result = analyze_message(db, message)
    package = result.review_package
    summary = result.conversation_summary
    return {
        "review_package_id": package.id,
        "conversation_summary_id": summary.id,
        "summary": summary.summary_text,
        "action_type": package.action_type.value,
        "explanation": package.explanation,
        "confidence": float(package.confidence),
        "draft_response": package.draft_response,
        "provider_name": package.provider_name,
        "review_only": True,
        "external_action_created": False,
    }


@api_router.get("/review-packages")
def get_review_packages(db: Session = Depends(get_db)) -> list[dict]:
    packages = (
        db.query(ProposedActionReviewPackage)
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .limit(100)
        .all()
    )
    return [_review_package_dict(package) for package in packages]


@api_router.post("/review-packages/{package_id}/status")
def set_review_package_status(
    package_id: int,
    status: str = Form(...),
    user_note: str | None = Form(None),
    draft_response: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        package = update_review_package_status(
            db,
            package_id,
            status=ReviewPackageStatus(status),
            user_note=user_note,
            draft_response=draft_response,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _review_package_dict(package)


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


@api_router.post("/learning/sent-mail/run")
def run_sent_learning(db: Session = Depends(get_db)) -> dict:
    result = run_sent_mail_learning(db)
    return {
        "fetched_count": result.fetched_count,
        "inserted_count": result.inserted_count,
        "updated_count": result.updated_count,
        "vip_candidate_count": result.vip_candidate_count,
        "guidance_count": result.guidance_count,
    }


@api_router.get("/learning/voice-calibration")
def get_voice_calibration(db: Session = Depends(get_db)) -> dict:
    vip_candidates = vip_candidates_for_review(db)
    guidance_rows = voice_guidance_for_review(db)
    return {
        "vip_candidates": [
            {
                "id": row.id,
                "contact_id": row.contact_id,
                "contact_name": row.contact.display_name if row.contact else None,
                "contact_email": row.contact.primary_email if row.contact else None,
                "score": row.score,
                "sent_count": row.sent_count,
                "reply_ratio": float(row.reply_ratio),
                "reasons": row.reasons,
                "status": row.status.value,
                "review_note": row.review_note,
            }
            for row in vip_candidates
        ],
        "voice_guidance": [
            {
                "id": row.id,
                "contact_id": row.contact_id,
                "relationship_type": row.relationship_type,
                "salutation_style": row.salutation_style,
                "preferred_name": row.preferred_name,
                "tone_notes": row.tone_notes,
                "evidence_excerpt": row.evidence_excerpt,
                "source": row.source,
                "status": row.status.value,
                "is_active": row.is_active,
            }
            for row in guidance_rows
        ],
    }


@api_router.post("/learning/vip/{candidate_id}/status")
def set_vip_learning_status(
    candidate_id: int,
    status: str = Form(...),
    review_note: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        candidate = update_vip_candidate_status(
            db,
            candidate_id,
            status=InferenceStatus(status),
            review_note=review_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": candidate.id,
        "contact_id": candidate.contact_id,
        "status": candidate.status.value,
        "score": candidate.score,
    }


@api_router.post("/learning/guidance/{guidance_id}/status")
def set_voice_guidance_status(
    guidance_id: int,
    status: str = Form(...),
    salutation_style: str | None = Form(None),
    preferred_name: str | None = Form(None),
    tone_notes: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        guidance = update_voice_guidance_status(
            db,
            guidance_id,
            status=InferenceStatus(status),
            salutation_style=salutation_style,
            preferred_name=preferred_name,
            tone_notes=tone_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": guidance.id,
        "status": guidance.status.value,
        "is_active": guidance.is_active,
        "salutation_style": guidance.salutation_style,
        "preferred_name": guidance.preferred_name,
    }


@api_router.post("/bulk-triage/candidates/refresh")
def refresh_bulk_candidates(db: Session = Depends(get_db)) -> dict:
    changed = refresh_automation_candidates(db)
    return {"updated_candidate_count": changed}


@api_router.get("/bulk-triage/candidates")
def get_bulk_candidates(limit: int = 200, db: Session = Depends(get_db)) -> list[dict]:
    candidates = automation_candidates_for_dashboard(db, limit=limit)
    return [
        {
            "id": candidate.id,
            "candidate_type": candidate.candidate_type.value,
            "status": candidate.status.value,
            "reason": candidate.reason,
            "confidence": float(candidate.confidence),
            "message_id": candidate.message_id,
            "thread_id": candidate.thread_id,
            "contact_id": candidate.contact_id,
        }
        for candidate in candidates
    ]


@api_router.get("/bulk-triage/backlog")
def get_bulk_backlog(
    queue_filter: str = "unreviewed",
    page: int = 1,
    page_size: int = 100,
    db: Session = Depends(get_db),
) -> dict:
    backlog = get_bulk_backlog_page(
        db,
        queue_filter=queue_filter,
        page=page,
        page_size=page_size,
    )
    return {
        "queue_filter": queue_filter,
        "page": backlog.page,
        "page_size": backlog.page_size,
        "total_count": backlog.total_count,
        "reviewed_count": backlog.reviewed_count,
        "dismissed_count": backlog.dismissed_count,
        "items": [
            {
                "attention_id": item.id,
                "message_id": item.message_id,
                "thread_id": item.thread_id,
                "score": item.attention_score,
                "status": item.status.value,
                "reason": item.reason,
                "sender_email": item.message.sender_email if item.message else None,
                "subject": item.message.subject if item.message else None,
            }
            for item in backlog.items
        ],
    }


@api_router.post("/bulk-triage/actions/apply")
def apply_bulk_triage_action(
    action_type: str = Form(...),
    attention_ids: list[int] = Form([]),
    queue_filter: str = Form("unreviewed"),
    relationship_type: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        action_log = apply_bulk_action(
            db,
            attention_ids=attention_ids,
            action_type=action_type,
            queue_filter=queue_filter,
            relationship_type=relationship_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "action_log_id": action_log.id,
        "action_type": action_log.action_type,
        "item_count": action_log.item_count,
        "is_undone": action_log.is_undone,
    }


@api_router.post("/bulk-triage/actions/{action_log_id}/undo")
def undo_bulk_triage_action(action_log_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        log = undo_bulk_action(db, action_log_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"action_log_id": log.id, "is_undone": log.is_undone}


@api_router.post("/executions/drafts/{draft_id}/prepare")
def prepare_draft_execution(draft_id: int, actor: str = Form("local-user"), db: Session = Depends(get_db)) -> dict:
    try:
        prepared = prepare_execution_for_draft(db, draft_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _execution_dict(prepared.record, already_exists=prepared.already_exists)


@api_router.post("/executions/review-packages/{package_id}/prepare")
def prepare_package_execution(
    package_id: int, actor: str = Form("local-user"), db: Session = Depends(get_db)
) -> dict:
    try:
        prepared = prepare_execution_for_review_package(db, package_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_dict(prepared.record, already_exists=prepared.already_exists)


@api_router.post("/executions/{execution_id}/approve")
def approve_execution_endpoint(
    execution_id: int, actor: str = Form("local-user"), db: Session = Depends(get_db)
) -> dict:
    try:
        record = approve_execution(db, execution_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_dict(record)


@api_router.post("/executions/{execution_id}/confirm")
def confirm_execution_endpoint(
    execution_id: int,
    actor: str = Form("local-user"),
    destructive_confirm_token: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        record = confirm_execution(
            db,
            execution_id,
            actor=actor,
            destructive_confirm_token=destructive_confirm_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_dict(record)


@api_router.post("/executions/{execution_id}/cancel")
def cancel_execution_endpoint(
    execution_id: int, actor: str = Form("local-user"), db: Session = Depends(get_db)
) -> dict:
    try:
        record = cancel_execution(db, execution_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_dict(record)


@api_router.get("/executions")
def get_executions(db: Session = Depends(get_db)) -> list[dict]:
    return [_execution_dict(record) for record in list_execution_records(db)]


@api_router.get("/executions/{execution_id}")
def get_execution(execution_id: int, db: Session = Depends(get_db)) -> dict:
    record = db.get(ExecutionRecord, execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="Execution record not found")
    data = _execution_dict(record)
    data["audit"] = [
        {
            "id": entry.id,
            "event_type": entry.event_type,
            "actor": entry.actor,
            "details": entry.details,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in audit_entries_for_execution(db, execution_id)
    ]
    return data


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


def _review_package_dict(package: ProposedActionReviewPackage) -> dict:
    calendar_proposal = package.calendar_proposals[0] if package.calendar_proposals else None
    return {
        "id": package.id,
        "thread_id": package.thread_id,
        "message_id": package.message_id,
        "summary": (
            package.conversation_summary.summary_text if package.conversation_summary else None
        ),
        "action_type": package.action_type.value,
        "explanation": package.explanation,
        "confidence": float(package.confidence),
        "draft_response": package.draft_response,
        "status": package.status.value,
        "provider_name": package.provider_name,
        "review_only": True,
        "external_action_created": False,
        "calendar_proposal": (
            {
                "action_kind": calendar_proposal.action_kind,
                "proposed_start_at": (
                    calendar_proposal.proposed_start_at.isoformat()
                    if calendar_proposal.proposed_start_at
                    else None
                ),
                "proposed_end_at": (
                    calendar_proposal.proposed_end_at.isoformat()
                    if calendar_proposal.proposed_end_at
                    else None
                ),
                "reminder_at": (
                    calendar_proposal.reminder_at.isoformat()
                    if calendar_proposal.reminder_at
                    else None
                ),
                "availability_reasoning": calendar_proposal.availability_reasoning,
                "conflict_summary": calendar_proposal.conflict_summary,
                "available_windows": calendar_proposal.available_windows,
                "provider_name": calendar_proposal.provider_name,
            }
            if calendar_proposal
            else None
        ),
    }


def _execution_dict(record: ExecutionRecord, *, already_exists: bool = False) -> dict:
    return {
        "id": record.id,
        "review_package_id": record.review_package_id,
        "draft_id": record.draft_id,
        "calendar_proposal_id": record.calendar_proposal_id,
        "action_type": record.action_type.value,
        "status": record.status.value,
        "created_by": record.created_by,
        "approved_by": record.approved_by,
        "confirmed_by": record.confirmed_by,
        "provider_name": record.provider_name,
        "payload_json": record.payload_json,
        "result_json": record.result_json,
        "error_text": record.error_text,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "executed_at": record.executed_at.isoformat() if record.executed_at else None,
        "already_exists": already_exists,
    }
