from datetime import UTC, datetime, time
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.auth import build_session_token, verify_login_credentials
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    BulkTriageActionLog,
    Contact,
    DraftReply,
    ExecutionActionType,
    ExecutionStatus,
    ExecutionAuditLog,
    ExecutionRecord,
    InferenceStatus,
    Message,
    MessageClassification,
    OperationalSmokeMode,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
    SentMailLearningRecord,
    UserFeedback,
    VoiceGuidance,
    VoiceProfile,
)
from app.services.admin_service import clear_cached_content, run_retention_cleanup
from app.services.backup_service import create_local_backup, latest_backup_metadata
from app.services.attention_service import build_attention_queue
from app.services.analysis_service import (
    analyze_message,
    recent_review_packages_for_message,
    update_review_package_status,
)
from app.services.bulk_triage_service import (
    apply_bulk_action,
    automation_candidates_for_dashboard,
    get_bulk_backlog_page,
    refresh_automation_candidates,
    undo_bulk_action,
)
from app.services.conversation_service import conversation_timeline
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
from app.services.draft_service import (
    DraftContext,
    MockDraftProvider,
    available_voice_profiles,
    cancel_local_draft,
    create_draft_reply,
    draft_status_counts,
    list_drafts,
    normalize_draft_content,
    recent_drafts_for_message,
    soft_delete_local_draft,
    suggested_voice_profile_id,
)
from app.services.feedback_service import (
    CORRECTION_LABELS,
    REVIEW_PACKAGE_CORRECTION_TYPES,
    apply_message_correction,
    apply_review_package_correction,
    classification_tags,
    friendly_classification_label,
)
from app.services.execution_service import (
    approve_execution,
    audit_entries_for_execution,
    cancel_execution,
    clone_execution,
    confirm_execution,
    execution_attempt_history,
    list_execution_records,
    prepare_execution_for_draft,
    prepare_execution_for_review_package,
    prepare_new_execution_from_existing,
    rerun_execution,
)
from app.services.execution_test_policy import readiness_for_execution, readiness_for_payload
from app.services.external_connectors_service import sync_outlook_messages, sync_teams_messages
from app.services.gmail_sync_service import get_sync_state, sync_gmail_messages
from app.services.gmail_sync_service import (
    deserialize_addresses,
    fetch_full_gmail_conversation,
    sync_gmail_backfill,
)
from app.services.live_ai_client import ai_provider_status
from app.services.operational_status_service import (
    cleanup_execution_posture,
    operational_smoke_status,
    source_filter_options,
    source_operational_counts,
)
from app.services.operational_smoke_runner import (
    latest_smoke_run,
    recent_smoke_runs,
    run_operational_smoke,
    smoke_run_detail,
    smoke_run_to_dict,
)
from app.services.provider_status_service import provider_status_rows
from app.services.voice_learning_service import (
    disable_voice_guidance,
    reset_voice_guidance_to_default,
    run_sent_mail_learning,
    update_vip_candidate_status,
    update_voice_guidance_status,
    vip_candidates_for_review,
    voice_guidance_for_review,
    voice_memory_summary,
)
from app.services.mailbox_cleanup_service import (
    action_logs_for_candidate,
    build_cleanup_rollups,
    cleanup_candidate_summary,
    cleanup_dashboard_stats,
    cleanup_execution_details,
    get_cleanup_candidate,
    get_cleanup_candidates,
    mark_delete_candidate_local,
    mark_sender_noise_local,
    mark_sender_not_noise,
    mark_sender_protected,
    prepare_cleanup_archive_execution,
    prepare_cleanup_label_and_archive_execution,
    prepare_cleanup_label_execution,
)

web_router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


def _parse_date_start(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(datetime.fromisoformat(value).date(), time.min, tzinfo=UTC)
    except ValueError:
        return None


def _parse_date_end(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(datetime.fromisoformat(value).date(), time.max, tzinfo=UTC)
    except ValueError:
        return None


def _queue_filters(request: Request) -> dict:
    params = request.query_params
    queue_filter = params.get("queue_filter", "active")
    return {
        "status_filter": queue_filter,
        "needs_reply": params.get("needs_reply") == "1" or queue_filter == "needs_reply",
        "important": params.get("important") == "1" or queue_filter == "important",
        "noise": queue_filter == "noise",
        "date_start": _parse_date_start(params.get("date_start")),
        "date_end": _parse_date_end(params.get("date_end")),
        "sender": params.get("sender") or None,
        "source": params.get("source") or None,
    }


def _safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/"):
        return "/"
    return value


def _compute_next_best_action(backlog_stats: dict, provider_rows: list) -> dict:
    """Determine the single most important next operator action for the dashboard NBA strip."""
    ready_execs = backlog_stats.get("ready_executions", 0)
    test_blocker = backlog_stats.get("test_execution_blocker")
    test_ready_execs = backlog_stats.get("test_ready_executions", 0)
    if ready_execs > 0 and test_ready_execs > 0:
        return {
            "tier": "pending",
            "message": f"Review {test_ready_execs} allowlisted test execution record{'s' if test_ready_execs != 1 else ''} awaiting operator action",
            "primary_label": "Next execution approval",
            "primary_url": "/executions/next",
            "secondary": [{"label": "Operational Smoke", "url": "/operational-smoke"}],
        }
    if ready_execs > 0 and test_blocker:
        return {
            "tier": "blocker",
            "message": f"Phase 19 test execution blocked: {test_blocker}",
            "primary_label": "Operational Smoke",
            "primary_url": "/operational-smoke",
            "secondary": [{"label": "Executions", "url": "/executions"}],
        }
    blockers = [
        row for row in provider_rows
        if row.state in {"missing_configuration", "failed"}
    ]
    if blockers:
        label = blockers[0].label
        return {
            "tier": "blocker",
            "message": f"Resolve provider blocker: {label}",
            "primary_label": "View Providers",
            "primary_url": "/providers",
            "secondary": [{"label": "Operational Smoke", "url": "/operational-smoke"}],
        }
    pending_pkgs = backlog_stats.get("pending_review_packages", 0)
    attention_total = backlog_stats.get("attention_total", 0)
    reviewed_total = backlog_stats.get("reviewed_total", 0)
    unreviewed = max(0, attention_total - reviewed_total)
    if pending_pkgs > 0 and ready_execs > 0:
        return {
            "tier": "pending",
            "message": f"Process {pending_pkgs} pending review package{'s' if pending_pkgs != 1 else ''} and approve {ready_execs} execution record{'s' if ready_execs != 1 else ''}",
            "primary_label": "Next review package",
            "primary_url": "/review-packages/next",
            "secondary": [{"label": "Next execution approval", "url": "/executions/next"}],
        }
    if pending_pkgs > 0:
        return {
            "tier": "pending",
            "message": f"Process {pending_pkgs} pending review package{'s' if pending_pkgs != 1 else ''}",
            "primary_label": "Next review package",
            "primary_url": "/review-packages/next",
            "secondary": [{"label": "All review packages", "url": "/review-packages"}],
        }
    if ready_execs > 0:
        return {
            "tier": "pending",
            "message": f"Approve {ready_execs} execution record{'s' if ready_execs != 1 else ''} awaiting confirmation",
            "primary_label": "Next execution approval",
            "primary_url": "/executions/next",
            "secondary": [{"label": "All executions", "url": "/executions"}],
        }
    if unreviewed > 0:
        return {
            "tier": "triage",
            "message": f"Review {unreviewed} attention item{'s' if unreviewed != 1 else ''} in the queue",
            "primary_label": "Process next item",
            "primary_url": "/process-next",
            "secondary": [],
        }
    return {
        "tier": "clear",
        "message": "No immediate action required. Queue is clear.",
        "primary_label": "View dashboard",
        "primary_url": "/",
        "secondary": [],
    }


@web_router.get("/login")
def login_page(request: Request):
    settings = get_settings()
    if not settings.auth_required:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "next_path": _safe_next_path(request.query_params.get("next")),
            "error": request.query_params.get("error") == "1",
        },
    )


@web_router.post("/login")
def login_submit(
    username: str = Form(""),
    password: str = Form(""),
    next_path: str = Form("/"),
):
    settings = get_settings()
    if not settings.auth_required:
        return RedirectResponse(url="/", status_code=303)
    safe_next = _safe_next_path(next_path)
    if not verify_login_credentials(username.strip(), password, settings):
        return RedirectResponse(
            url=f"/login?error=1&next={quote(safe_next, safe='/?=&')}",
            status_code=303,
        )
    token = build_session_token(settings.app_auth_username or username.strip(), settings)
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        max_age=max(1, settings.auth_session_ttl_hours) * 3600,
        httponly=True,
        secure=settings.normalized_env in {"production", "prod", "staging"},
        samesite="lax",
    )
    return response


@web_router.post("/logout")
def logout():
    settings = get_settings()
    response = RedirectResponse(url="/login" if settings.auth_required else "/", status_code=303)
    response.delete_cookie(settings.auth_session_cookie_name)
    return response


@web_router.get("/admin")
def admin_panel(request: Request, db: Session = Depends(get_db)):
    message_body_count = (
        db.query(func.count(Message.id)).filter(Message.body_text.is_not(None)).scalar() or 0
    )
    sent_excerpt_count = (
        db.query(func.count(SentMailLearningRecord.id))
        .filter(
            or_(
                SentMailLearningRecord.body_excerpt.is_not(None),
                SentMailLearningRecord.snippet_excerpt.is_not(None),
            )
        )
        .scalar()
        or 0
    )
    audit_count = db.query(func.count(ExecutionAuditLog.id)).scalar() or 0
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "message_body_count": message_body_count,
            "sent_excerpt_count": sent_excerpt_count,
            "audit_count": audit_count,
            "retention_result": request.query_params.get("retention_result"),
            "cache_result": request.query_params.get("cache_result"),
            "backup_result": request.query_params.get("backup_result"),
            "latest_backup": latest_backup_metadata(),
        },
    )


@web_router.post("/admin/retention/run")
def run_retention(db: Session = Depends(get_db)):
    result = run_retention_cleanup(db).as_dict()
    serialized = ",".join(f"{key}:{value}" for key, value in result.items())
    return RedirectResponse(
        url=f"/admin?retention_result={quote(serialized, safe='')}", status_code=303
    )


@web_router.post("/admin/cache/clear")
def clear_cache(
    clear_message_bodies: bool = Form(False),
    clear_sent_learning_excerpts: bool = Form(False),
    db: Session = Depends(get_db),
):
    result = clear_cached_content(
        db,
        clear_message_bodies=clear_message_bodies,
        clear_sent_learning_excerpts=clear_sent_learning_excerpts,
    ).as_dict()
    serialized = ",".join(f"{key}:{value}" for key, value in result.items())
    return RedirectResponse(url=f"/admin?cache_result={quote(serialized, safe='')}", status_code=303)


@web_router.post("/admin/backup/create")
def web_create_backup():
    result = create_local_backup().as_dict()
    serialized = (
        f"filename:{result['filename']},database_included:{result['database_included']},"
        f"oauth_tokens_included:{result['oauth_tokens_included']},"
        f"env_snapshot:{result['env_snapshot_status']},size_bytes:{result['size_bytes']}"
    )
    return RedirectResponse(url=f"/admin?backup_result={quote(serialized, safe='')}", status_code=303)


@web_router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    filters = _queue_filters(request)
    attention = build_attention_queue(db, **filters)[:30]
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
    review_packages = (
        db.query(ProposedActionReviewPackage)
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .limit(10)
        .all()
    )
    ready_executions = (
        db.query(ExecutionRecord)
        .filter(ExecutionRecord.status.in_([ExecutionStatus.PENDING_REVIEW, ExecutionStatus.APPROVED]))
        .order_by(ExecutionRecord.updated_at.desc(), ExecutionRecord.id.desc())
        .limit(8)
        .all()
    )
    calendar_candidates = (
        db.query(ProposedActionReviewPackage)
        .filter(
            ProposedActionReviewPackage.action_type.in_(
                [ProposedActionType.CREATE_CALENDAR_REMINDER, ProposedActionType.SCHEDULE_MEETING]
            )
        )
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .limit(6)
        .all()
    )
    automation_candidates = automation_candidates_for_dashboard(db, limit=12)
    _cleanup_stats = cleanup_dashboard_stats(db)
    backlog_stats = {
        "attention_total": db.query(func.count(AttentionItem.id)).scalar() or 0,
        "reviewed_total": (
            db.query(func.count(AttentionItem.id))
            .filter(AttentionItem.status == AttentionStatus.REVIEWED)
            .scalar()
            or 0
        ),
        "pending_review_packages": (
            db.query(func.count(ProposedActionReviewPackage.id))
            .filter(ProposedActionReviewPackage.status == ReviewPackageStatus.PENDING)
            .scalar()
            or 0
        ),
        "ready_executions": len(ready_executions),
        "cleanup_candidates": _cleanup_stats.total_candidates,
        "cleanup_high_confidence": _cleanup_stats.high_confidence_count,
        "cleanup_protected": _cleanup_stats.protected_count,
        "cleanup_pending_execution": _cleanup_stats.pending_execution_count,
    }
    ai_status = ai_provider_status(settings)
    provider_rows = provider_status_rows(settings)
    smoke_status = operational_smoke_status(db, settings)
    last_smoke = latest_smoke_run(db)
    outlook_sync_state = get_sync_state(db, source_type="outlook", account_identifier="microsoft-graph")
    pending_voice_guidance = (
        db.query(func.count(VoiceGuidance.id))
        .filter(VoiceGuidance.status == InferenceStatus.PENDING)
        .scalar()
        or 0
    )
    ready_readiness = [readiness_for_execution(record, settings) for record in ready_executions]
    first_blocker = next((item.blocked_reason for item in ready_readiness if item.blocked_reason), None)
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
            "queue_filter": request.query_params.get("queue_filter", "active"),
            "filter_needs_reply": request.query_params.get("needs_reply") == "1",
            "filter_important": request.query_params.get("important") == "1",
            "filter_sender": request.query_params.get("sender", ""),
            "filter_source": request.query_params.get("source", ""),
            "filter_date_start": request.query_params.get("date_start", ""),
            "filter_date_end": request.query_params.get("date_end", ""),
            "review_packages": review_packages,
            "ready_executions": ready_executions,
            "calendar_candidates": calendar_candidates,
            "automation_candidates": automation_candidates,
            "backlog_stats": backlog_stats,
            "provider_status": {
                "ai_provider": ai_status.effective_provider,
                "ai_requested_provider": ai_status.requested_provider,
                "ai_model": ai_status.model,
                "ai_deployment": ai_status.deployment,
                "ai_live_enabled": ai_status.live_enabled,
                "ai_fallback_provider": ai_status.fallback_provider,
                "ai_detail": ai_status.detail,
                "calendar_provider": settings.calendar_provider,
                "execution_provider": settings.execution_provider,
                "gmail_full_body": settings.gmail_store_full_body,
            },
            "provider_rows": provider_rows,
            "source_filter_options": source_filter_options(),
            "source_counts": source_operational_counts(db),
            "smoke_status": smoke_status,
            "daily_start": {
                "last_smoke": last_smoke,
                "last_outlook_sync": outlook_sync_state,
                "pending_voice_guidance": pending_voice_guidance,
                "provider_blockers": [
                    row for row in provider_rows if row.state in {"missing_configuration", "failed"}
                ],
                "cleanup_stats": _cleanup_stats,
            },
            "provider_warnings": [
                row
                for row in provider_rows
                if row.state in {"missing_configuration", "failed"}
                or (row.state == "dry_run" and row.key != "ai_provider")
            ][:5],
            "ready_execution_readiness": dict(zip([record.id for record in ready_executions], ready_readiness, strict=False)),
            "next_best_action": _compute_next_best_action(
                {
                    **backlog_stats,
                    "test_ready_executions": len([item for item in ready_readiness if item.allowed]),
                    "test_execution_blocker": (
                        "Phase 19 test execution unavailable because operational test mode is disabled."
                        if not settings.operational_test_mode
                        else first_blocker
                    ),
                },
                provider_rows,
            ),
        },
    )


@web_router.get("/providers")
def providers_page(request: Request):
    rows = provider_status_rows(get_settings())
    return templates.TemplateResponse(
        request,
        "providers.html",
        {
            "provider_rows": rows,
            "state_counts": {
                state: len([row for row in rows if row.state == state])
                for state in ("live", "mock", "disabled", "missing_configuration", "dry_run", "failed")
            },
        },
    )


@web_router.get("/operational-smoke")
def operational_smoke_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "operational_smoke.html",
        {
            "smoke_status": operational_smoke_status(db, get_settings()),
            "latest_smoke_run": latest_smoke_run(db),
            "recent_smoke_runs": recent_smoke_runs(db, limit=10),
        },
    )


@web_router.post("/operational-smoke/run")
def web_run_operational_smoke(db: Session = Depends(get_db)):
    run = run_operational_smoke(
        db,
        mode=OperationalSmokeMode.MANUAL,
        triggered_by="local-user",
    )
    return RedirectResponse(url=f"/operational-smoke/runs/{run.id}", status_code=303)


@web_router.get("/operational-smoke/runs/{run_id}")
def operational_smoke_run_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = smoke_run_detail(db, run_id)
    return templates.TemplateResponse(
        request,
        "operational_smoke_run.html",
        {"run": run, "run_detail": smoke_run_to_dict(run, include_checks=True) if run else None},
        status_code=200 if run else 404,
    )


def _assistant_profile_context(
    request: Request,
    db: Session,
    *,
    preview_input: dict[str, str] | None = None,
) -> dict:
    summary = voice_memory_summary(db)
    preview = None
    sample = preview_input or {
        "sender_name": "Client Contact",
        "sender_email": "client@example.com",
        "subject": "Quick follow-up",
        "message_text": "Can you confirm the next step when you have a chance?",
        "relationship": "client",
    }
    if preview_input is not None:
        preview = _build_local_voice_preview(sample, summary)
    return {
        "voice_memory": summary,
        "guidance_rows": voice_guidance_for_review(db),
        "inference_statuses": list(InferenceStatus),
        "voice_profile_count": db.query(func.count(VoiceProfile.id)).scalar() or 0,
        "active_voice_profile_count": (
            db.query(func.count(VoiceProfile.id))
            .filter(VoiceProfile.is_enabled.is_(True))
            .scalar()
            or 0
        ),
        "preview": preview,
        "preview_sample": sample,
        "profile_result": request.query_params.get("profile_result"),
    }


def _build_local_voice_preview(sample: dict[str, str], summary) -> dict:
    tone_notes = "; ".join(summary.tone_guidance)
    if summary.preferred_signoff_will_apply and summary.preferred_signoff:
        tone_notes = (
            f"{tone_notes}; preferred sign-off: {summary.preferred_signoff}"
            if tone_notes
            else f"preferred sign-off: {summary.preferred_signoff}"
        )
    context = DraftContext(
        message_id=0,
        thread_id=0,
        subject=(sample.get("subject") or "").strip(),
        sender_name=(sample.get("sender_name") or "").strip(),
        sender_email=(sample.get("sender_email") or "").strip(),
        contact_name=(sample.get("sender_name") or "").strip(),
        contact_relationship=(sample.get("relationship") or "client").strip() or "client",
        contact_importance_tier=None,
        contact_state="sample",
        classification_label="Needs reply",
        classification_summary="local preview sample",
        attention_score=None,
        attention_reason="Local Assistant Profile preview.",
        recommended_action="Reply",
        feedback_summary="No correction history used for local preview.",
        conversation_summary=(sample.get("message_text") or "").strip(),
        proposed_action_type="reply",
        proposed_action_explanation="Local preview only.",
        review_package_draft_response="",
        full_thread_context=(sample.get("message_text") or "").strip(),
        learned_salutation_style="first_name",
        learned_preferred_name=(sample.get("sender_name") or "").strip().split(" ")[0],
        learned_tone_notes=tone_notes,
    )
    profile = available_voice_profiles_for_preview(sample)
    content = normalize_draft_content(
        MockDraftProvider().generate(context, profile),
        fallback_subject=f"Re: {context.subject}" if context.subject else "Re:",
    )
    influenced = []
    if summary.preferred_signoff_will_apply and summary.preferred_signoff:
        influenced.append(f"Preferred sign-off: {summary.preferred_signoff}")
    influenced.extend(summary.tone_guidance[:4])
    influenced.extend(f"Avoid: {phrase}" for phrase in summary.avoided_phrases[:3])
    return {
        "subject": content.send_ready_subject,
        "body": content.send_ready_body,
        "influenced_traits": influenced,
    }


def available_voice_profiles_for_preview(sample: dict[str, str]):
    from app.models.entities import VoiceProfile

    relationship = (sample.get("relationship") or "client").strip().lower() or "client"
    return VoiceProfile(
        name="Local Assistant Profile Preview",
        audience_type=relationship if relationship in {"client", "friend", "partner", "vendor"} else "client",
        tone_description="current approved voice memory",
        signoff_style="approved guidance",
    )


@web_router.get("/assistant-profile")
def assistant_profile(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "assistant_profile.html",
        _assistant_profile_context(request, db),
    )


@web_router.get("/voice-memory")
def voice_memory_redirect():
    return RedirectResponse(url="/assistant-profile", status_code=303)


@web_router.post("/assistant-profile/preview")
def assistant_profile_preview(
    request: Request,
    sender_name: str = Form("Client Contact"),
    sender_email: str = Form("client@example.com"),
    subject: str = Form("Quick follow-up"),
    message_text: str = Form("Can you confirm the next step when you have a chance?"),
    relationship: str = Form("client"),
    db: Session = Depends(get_db),
):
    sample = {
        "sender_name": sender_name,
        "sender_email": sender_email,
        "subject": subject,
        "message_text": message_text,
        "relationship": relationship,
    }
    return templates.TemplateResponse(
        request,
        "assistant_profile.html",
        _assistant_profile_context(request, db, preview_input=sample),
    )


@web_router.post("/assistant-profile/guidance/{guidance_id}")
def assistant_profile_update_guidance(
    guidance_id: int,
    action: str = Form(...),
    status: str | None = Form(None),
    salutation_style: str | None = Form(None),
    preferred_name: str | None = Form(None),
    tone_notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        if action == "disable":
            disable_voice_guidance(db, guidance_id)
        elif action == "reset":
            reset_voice_guidance_to_default(db, guidance_id)
        else:
            status_value = status or {"approve": "approved", "reject": "rejected"}.get(action, action)
            selected = InferenceStatus(status_value)
            update_voice_guidance_status(
                db,
                guidance_id,
                status=selected,
                salutation_style=salutation_style,
                preferred_name=preferred_name,
                tone_notes=tone_notes,
            )
    except ValueError:
        return RedirectResponse(url="/assistant-profile?profile_result=invalid", status_code=303)
    return RedirectResponse(url="/assistant-profile?profile_result=ok", status_code=303)


@web_router.get("/process-next")
def process_next_attention(request: Request, db: Session = Depends(get_db)):
    filters = _queue_filters(request)
    filters["status_filter"] = request.query_params.get("queue_filter", "active")
    item = next((row for row in build_attention_queue(db, **filters) if row.message_id), None)
    if not item:
        return RedirectResponse(url="/?next_empty=attention", status_code=303)
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=item.message_id),
        status_code=303,
    )


@web_router.get("/review-packages/next")
def next_review_package(request: Request, db: Session = Depends(get_db)):
    current_id = _parse_int(request.query_params.get("current_id"))
    query = db.query(ProposedActionReviewPackage).filter(
        ProposedActionReviewPackage.status == ReviewPackageStatus.PENDING
    )
    if current_id:
        query = query.filter(ProposedActionReviewPackage.id != current_id)
    package = (
        query.order_by(
            ProposedActionReviewPackage.updated_at.desc(),
            ProposedActionReviewPackage.id.desc(),
        )
        .first()
    )
    if not package:
        return RedirectResponse(url="/review-packages?next_empty=1", status_code=303)
    return RedirectResponse(
        url=request.url_for("review_package_detail", package_id=package.id),
        status_code=303,
    )


@web_router.get("/executions/next")
def next_execution(request: Request, db: Session = Depends(get_db)):
    current_id = _parse_int(request.query_params.get("current_id"))
    query = db.query(ExecutionRecord).filter(
        ExecutionRecord.status.in_([ExecutionStatus.PENDING_REVIEW, ExecutionStatus.APPROVED])
    )
    if current_id:
        query = query.filter(ExecutionRecord.id != current_id)
    record = query.order_by(ExecutionRecord.updated_at.desc(), ExecutionRecord.id.desc()).first()
    if not record:
        return RedirectResponse(url="/executions?next_empty=1", status_code=303)
    return RedirectResponse(
        url=request.url_for("execution_detail", execution_id=record.id),
        status_code=303,
    )


def _parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _cleanup_label_posture(settings) -> dict:
    """Return cleanup execution posture for the UI — what is gated, what can run, etc."""
    return cleanup_execution_posture(settings)


@web_router.post("/sync/gmail")
def web_sync_gmail(resync: bool = Form(False), db: Session = Depends(get_db)):
    try:
        sync_gmail_messages(db, force_resync=resync)
    except (FileNotFoundError, RuntimeError):
        return RedirectResponse(url="/?sync_error=configuration", status_code=303)
    except Exception:
        return RedirectResponse(url="/?sync_error=failed", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/sync/gmail/backfill")
def web_backfill_gmail(db: Session = Depends(get_db)):
    try:
        sync_gmail_backfill(db)
    except (FileNotFoundError, RuntimeError):
        return RedirectResponse(url="/?sync_error=configuration", status_code=303)
    except Exception:
        return RedirectResponse(url="/?sync_error=failed", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/sync/outlook")
def web_sync_outlook(db: Session = Depends(get_db)):
    try:
        sync_outlook_messages(db)
    except Exception:
        return RedirectResponse(url="/?sync_error=failed", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@web_router.post("/sync/teams")
def web_sync_teams(db: Session = Depends(get_db)):
    try:
        sync_teams_messages(db)
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
        draft_replies = recent_drafts_for_message(db, message_id)
        review_packages = recent_review_packages_for_message(db, message_id)
        voice_profiles = available_voice_profiles(db)
        suggested_profile_id = suggested_voice_profile_id(db, message)
        timeline = conversation_timeline(db, message.thread_id, message.id)
        has_full_conversation = bool(message.thread and message.thread.full_content_fetched_at)
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
            "draft_replies": draft_replies if message else [],
            "review_packages": review_packages if message else [],
            "voice_profiles": voice_profiles if message else [],
            "suggested_profile_id": suggested_profile_id if message else None,
            "timeline": timeline if message else [],
            "has_full_conversation": has_full_conversation if message else False,
            "recipient_emails": deserialize_addresses(message.recipient_emails) if message else [],
            "cc_emails": deserialize_addresses(message.cc_emails) if message else [],
            "conversation_error": request.query_params.get("conversation_error"),
            "correction_labels": CORRECTION_LABELS,
            "friendly_label": friendly_classification_label(classification),
            "classification_tags": classification_tags(classification),
        },
        status_code=status_code,
    )


@web_router.post("/messages/{message_id}/analyze")
def web_analyze_message(message_id: int, request: Request, db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    if message:
        result = analyze_message(db, message)
        return RedirectResponse(
            url=request.url_for("review_package_detail", package_id=result.review_package.id),
            status_code=303,
        )
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
    )


@web_router.post("/messages/{message_id}/fetch-conversation")
def web_fetch_conversation(message_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        fetch_full_gmail_conversation(db, message_id)
    except (FileNotFoundError, RuntimeError):
        return RedirectResponse(
            url=f"{request.url_for('message_detail', message_id=message_id)}?conversation_error=configuration",
            status_code=303,
        )
    except Exception:
        return RedirectResponse(
            url=f"{request.url_for('message_detail', message_id=message_id)}?conversation_error=failed",
            status_code=303,
        )
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
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
def web_generate_draft(
    message_id: int,
    request: Request,
    voice_profile_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    message = db.get(Message, message_id)
    if message:
        draft = create_draft_reply(db, message, voice_profile_id=voice_profile_id)
        return RedirectResponse(
            url=request.url_for("draft_detail", draft_id=draft.id), status_code=303
        )
    return RedirectResponse(
        url=request.url_for("message_detail", message_id=message_id), status_code=303
    )


@web_router.get("/drafts")
def drafts_index(request: Request, db: Session = Depends(get_db)):
    status_filter = request.query_params.get("status", "active")
    return templates.TemplateResponse(
        request,
        "drafts.html",
        {
            "drafts": list_drafts(db, status_filter=status_filter),
            "status_filter": status_filter,
            "draft_counts": draft_status_counts(db),
            "draft_result": request.query_params.get("draft_result"),
            "draft_error": request.query_params.get("draft_error"),
        },
    )


@web_router.get("/voice-calibration")
def voice_calibration(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "voice_calibration.html",
        {
            "profiles": db.query(VoiceProfile).order_by(VoiceProfile.name.asc()).all(),
            "vip_candidates": vip_candidates_for_review(db),
            "guidance_rows": voice_guidance_for_review(db),
            "inference_statuses": list(InferenceStatus),
            "learning_run": request.query_params.get("learning_run"),
        },
    )


@web_router.get("/voice-calibration/new")
def new_voice_profile(request: Request):
    return templates.TemplateResponse(
        request,
        "voice_profile_form.html",
        {
            "error": request.query_params.get("error"),
            "profile": None,
        },
    )


@web_router.post("/voice-calibration/new")
def create_voice_profile(
    profile_name: str = Form(...),
    description: str | None = Form(None),
    default_signoff: str | None = Form(None),
    enabled: bool = Form(False),
    db: Session = Depends(get_db),
):
    name = profile_name.strip()
    if not name:
        return RedirectResponse(url="/voice-calibration/new?error=name_required", status_code=303)
    db.add(
        VoiceProfile(
            name=name,
            audience_type="custom",
            tone_description=(description or "").strip() or None,
            formality_level=3,
            humor_level=0,
            signoff_style=(default_signoff or "").strip() or None,
            is_enabled=enabled,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(url="/voice-calibration/new?error=duplicate", status_code=303)
    return RedirectResponse(url="/voice-calibration?profile_created=1", status_code=303)


@web_router.get("/voice-calibration/import-sent")
def import_sent_samples_preview(request: Request):
    return templates.TemplateResponse(
        request,
        "voice_import_samples.html",
        {"learning_run": request.query_params.get("learning_run")},
    )


@web_router.post("/voice-calibration/learn-from-sent")
def web_import_sent_samples_html(db: Session = Depends(get_db)):
    try:
        run_sent_mail_learning(db)
        return RedirectResponse(url="/voice-calibration/import-sent?learning_run=ok", status_code=303)
    except Exception:
        return RedirectResponse(
            url="/voice-calibration/import-sent?learning_run=config_required",
            status_code=303,
        )


@web_router.get("/bulk-triage")
def bulk_triage_dashboard(request: Request, db: Session = Depends(get_db)):
    def _as_int(raw: str | None, default: int) -> int:
        try:
            return int(raw or default)
        except (TypeError, ValueError):
            return default

    queue_filter = request.query_params.get("queue_filter", "unreviewed")
    page = _as_int(request.query_params.get("page"), 1)
    page_size = _as_int(request.query_params.get("page_size"), 100)
    backlog = get_bulk_backlog_page(
        db,
        page=page,
        page_size=page_size,
        queue_filter=queue_filter,
    )
    candidate_rows = automation_candidates_for_dashboard(db)
    action_logs = (
        db.query(BulkTriageActionLog)
        .order_by(BulkTriageActionLog.created_at.desc(), BulkTriageActionLog.id.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "bulk_triage.html",
        {
            "backlog": backlog,
            "queue_filter": queue_filter,
            "page_size": page_size,
            "candidate_rows": candidate_rows,
            "action_logs": action_logs,
            "bulk_error": request.query_params.get("bulk_error"),
            "candidate_refresh": request.query_params.get("candidate_refresh"),
        },
    )


@web_router.post("/bulk-triage/generate-candidates")
def web_generate_automation_candidates(db: Session = Depends(get_db)):
    refresh_automation_candidates(db)
    return RedirectResponse(url="/bulk-triage?candidate_refresh=ok", status_code=303)


@web_router.post("/bulk-triage/apply")
def web_apply_bulk_action(
    attention_ids: list[int] = Form([]),
    action_type: str = Form(...),
    queue_filter: str = Form("unreviewed"),
    relationship_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        apply_bulk_action(
            db,
            attention_ids=attention_ids,
            action_type=action_type,
            queue_filter=queue_filter,
            relationship_type=relationship_type,
        )
    except ValueError:
        return RedirectResponse(
            url=f"/bulk-triage?queue_filter={queue_filter}&bulk_error=invalid_action",
            status_code=303,
        )
    return RedirectResponse(url=f"/bulk-triage?queue_filter={queue_filter}", status_code=303)


@web_router.post("/bulk-triage/undo/{action_log_id}")
def web_undo_bulk_action(action_log_id: int, db: Session = Depends(get_db)):
    try:
        undo_bulk_action(db, action_log_id)
    except ValueError:
        return RedirectResponse(url="/bulk-triage?bulk_error=undo_failed", status_code=303)
    return RedirectResponse(url="/bulk-triage", status_code=303)


# ─── Mailbox Cleanup Routes ───────────────────────────────────────────────────


@web_router.get("/bulk-triage/mailbox-cleanup")
def mailbox_cleanup_index(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    status_filter = request.query_params.get("status_filter", "pending")
    candidates = get_cleanup_candidates(db, status_filter=status_filter)
    stats = cleanup_dashboard_stats(db)
    summary = cleanup_candidate_summary(db)
    cleanup_label_posture = _cleanup_label_posture(settings)
    return templates.TemplateResponse(
        request,
        "mailbox_cleanup.html",
        {
            "candidates": candidates,
            "stats": stats,
            "summary": summary,
            "status_filter": status_filter,
            "cleanup_label_posture": cleanup_label_posture,
            "refresh_result": request.query_params.get("refresh_result"),
            "action_result": request.query_params.get("action_result"),
            "action_error": request.query_params.get("action_error"),
        },
    )


@web_router.get("/bulk-triage/mailbox-cleanup/{candidate_id}")
def mailbox_cleanup_detail(candidate_id: int, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    candidate = get_cleanup_candidate(db, candidate_id)
    if not candidate:
        return RedirectResponse(url="/bulk-triage/mailbox-cleanup?action_error=not_found", status_code=303)
    logs = action_logs_for_candidate(db, candidate_id)
    cleanup_label_posture = _cleanup_label_posture(settings)
    import json as _json
    sample_subjects = []
    if candidate.sample_subjects_json:
        try:
            sample_subjects = _json.loads(candidate.sample_subjects_json)
        except Exception:
            pass
    return templates.TemplateResponse(
        request,
        "mailbox_cleanup_detail.html",
        {
            "candidate": candidate,
            "logs": logs,
            "sample_subjects": sample_subjects,
            "cleanup_label_posture": cleanup_label_posture,
            "action_result": request.query_params.get("action_result"),
            "action_error": request.query_params.get("action_error"),
        },
    )


@web_router.post("/bulk-triage/mailbox-cleanup/refresh")
def web_refresh_cleanup_candidates(db: Session = Depends(get_db)):
    count = build_cleanup_rollups(db)
    return RedirectResponse(
        url=f"/bulk-triage/mailbox-cleanup?refresh_result={count}", status_code=303
    )


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/mark-noise")
def web_cleanup_mark_noise(candidate_id: int, db: Session = Depends(get_db)):
    try:
        mark_sender_noise_local(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_result=marked_noise",
        status_code=303,
    )


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/mark-protected")
def web_cleanup_mark_protected(candidate_id: int, db: Session = Depends(get_db)):
    try:
        mark_sender_protected(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_result=marked_protected",
        status_code=303,
    )


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/mark-not-noise")
def web_cleanup_mark_not_noise(candidate_id: int, db: Session = Depends(get_db)):
    try:
        mark_sender_not_noise(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_result=reset_pending",
        status_code=303,
    )


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/prepare-label")
def web_cleanup_prepare_label(candidate_id: int, db: Session = Depends(get_db)):
    try:
        record = prepare_cleanup_label_execution(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(url=f"/executions/{record.id}", status_code=303)


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/prepare-archive")
def web_cleanup_prepare_archive(candidate_id: int, db: Session = Depends(get_db)):
    try:
        record = prepare_cleanup_archive_execution(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(url=f"/executions/{record.id}", status_code=303)


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/prepare-label-and-archive")
def web_cleanup_prepare_label_and_archive(candidate_id: int, db: Session = Depends(get_db)):
    try:
        record = prepare_cleanup_label_and_archive_execution(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(url=f"/executions/{record.id}", status_code=303)


@web_router.post("/bulk-triage/mailbox-cleanup/{candidate_id}/mark-delete-candidate")
def web_cleanup_mark_delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    try:
        mark_delete_candidate_local(db, candidate_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/bulk-triage/mailbox-cleanup/{candidate_id}?action_result=marked_delete_candidate",
        status_code=303,
    )


@web_router.post("/voice-calibration/run-learning")
def web_run_sent_learning(db: Session = Depends(get_db)):
    run_sent_mail_learning(db)
    return RedirectResponse(url="/voice-calibration?learning_run=ok", status_code=303)


@web_router.post("/voice-calibration/vip/{candidate_id}")
def web_update_vip_candidate(
    candidate_id: int,
    status: str = Form(...),
    review_note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        update_vip_candidate_status(
            db,
            candidate_id,
            status=InferenceStatus(status),
            review_note=review_note,
        )
    except ValueError:
        pass
    return RedirectResponse(url="/voice-calibration", status_code=303)


@web_router.post("/voice-calibration/guidance/{guidance_id}")
def web_update_voice_guidance(
    guidance_id: int,
    status: str = Form(...),
    salutation_style: str | None = Form(None),
    preferred_name: str | None = Form(None),
    tone_notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        update_voice_guidance_status(
            db,
            guidance_id,
            status=InferenceStatus(status),
            salutation_style=salutation_style,
            preferred_name=preferred_name,
            tone_notes=tone_notes,
        )
    except ValueError:
        pass
    return RedirectResponse(url="/voice-calibration", status_code=303)


@web_router.get("/drafts/{draft_id}")
def draft_detail(draft_id: int, request: Request, db: Session = Depends(get_db)):
    draft = db.get(DraftReply, draft_id)
    readiness = None
    source_type = "unknown"
    platform_block = None
    if draft:
        source_type = (
            (draft.message.source_type if draft.message else None)
            or (draft.thread.source_type if draft.thread else None)
            or "gmail"
        ).strip().lower()
        if source_type == "outlook":
            platform_block = "Outlook draft creation is not implemented or not enabled."
        else:
            readiness = readiness_for_payload(
                ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
                {"to": draft.message.sender_email if draft.message else None},
                get_settings(),
            )
    return templates.TemplateResponse(
        request,
        "draft_review.html",
        {
            "draft": draft,
            "test_readiness": readiness,
            "source_type": source_type,
            "platform_block": platform_block,
            "draft_error": request.query_params.get("draft_error"),
        },
        status_code=200 if draft else 404,
    )


@web_router.post("/drafts/{draft_id}/prepare-execution")
def web_prepare_draft_execution(draft_id: int, db: Session = Depends(get_db)):
    try:
        prepared = prepare_execution_for_draft(db, draft_id, actor="local-user")
    except ValueError as exc:
        return RedirectResponse(
            url=f"/drafts/{draft_id}?draft_error={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(url=f"/executions/{prepared.record.id}", status_code=303)


@web_router.post("/drafts/{draft_id}/cancel")
def web_cancel_local_draft(draft_id: int, db: Session = Depends(get_db)):
    try:
        cancel_local_draft(db, draft_id)
    except ValueError:
        return RedirectResponse(url="/drafts?draft_error=not_found", status_code=303)
    return RedirectResponse(url=f"/drafts/{draft_id}?draft_result=cancelled", status_code=303)


@web_router.post("/drafts/{draft_id}/delete")
def web_delete_local_draft(draft_id: int, db: Session = Depends(get_db)):
    try:
        soft_delete_local_draft(db, draft_id)
    except ValueError:
        return RedirectResponse(url="/drafts?draft_error=not_found", status_code=303)
    return RedirectResponse(url="/drafts?draft_result=deleted", status_code=303)


@web_router.post("/review-packages/{package_id}/prepare-execution")
def web_prepare_package_execution(package_id: int, db: Session = Depends(get_db)):
    try:
        prepared = prepare_execution_for_review_package(db, package_id, actor="local-user")
    except ValueError:
        return RedirectResponse(url="/review-packages", status_code=303)
    return RedirectResponse(url=f"/executions/{prepared.record.id}", status_code=303)


@web_router.get("/review-packages")
def review_packages_index(request: Request, db: Session = Depends(get_db)):
    packages = (
        db.query(ProposedActionReviewPackage)
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(request, "review_packages.html", {"packages": packages})


@web_router.get("/review-packages/{package_id}")
def review_package_detail(package_id: int, request: Request, db: Session = Depends(get_db)):
    package = db.get(ProposedActionReviewPackage, package_id)
    package_position = None
    package_total = 0
    timeline = []
    contact = None
    active_guidance = []
    package_corrections = []
    if package:
        package_total = db.query(func.count(ProposedActionReviewPackage.id)).scalar() or 0
        package_position = (
            db.query(func.count(ProposedActionReviewPackage.id))
            .filter(
                (ProposedActionReviewPackage.updated_at > package.updated_at)
                | (
                    (ProposedActionReviewPackage.updated_at == package.updated_at)
                    & (ProposedActionReviewPackage.id > package.id)
                )
            )
            .scalar()
            or 0
        ) + 1
        timeline = conversation_timeline(db, package.thread_id, package.message_id)
        if package.message:
            if package.message.thread and package.message.thread.contact_id:
                contact = db.get(Contact, package.message.thread.contact_id)
            elif package.message.sender_email:
                contact = find_contact_by_sender_email(db, package.message.sender_email)
        if contact:
            active_guidance = (
                db.query(VoiceGuidance)
                .filter(
                    VoiceGuidance.is_active.is_(True),
                    (VoiceGuidance.contact_id == contact.id)
                    | (VoiceGuidance.relationship_type == contact.relationship_type),
                )
                .order_by(VoiceGuidance.contact_id.desc(), VoiceGuidance.updated_at.desc())
                .limit(5)
                .all()
            )
        package_corrections = (
            db.query(UserFeedback)
            .filter(
                UserFeedback.message_id == package.message_id,
                UserFeedback.feedback_type.like("review_package_%"),
            )
            .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
            .limit(10)
            .all()
        )
        readiness_action = None
        readiness_payload: dict[str, object] = {}
        if package.action_type in {
            ProposedActionType.REPLY,
            ProposedActionType.ASK_CLARIFYING_QUESTION,
        }:
            readiness_action = ExecutionActionType.SEND_GMAIL_REPLY
            readiness_payload = {"to": package.message.sender_email if package.message else None}
        elif package.action_type in {
            ProposedActionType.CREATE_CALENDAR_REMINDER,
            ProposedActionType.SCHEDULE_MEETING,
        }:
            readiness_action = ExecutionActionType.CREATE_CALENDAR_EVENT
        test_readiness = (
            readiness_for_payload(readiness_action, readiness_payload, get_settings())
            if readiness_action
            else None
        )
    else:
        test_readiness = None
    return templates.TemplateResponse(
        request,
        "review_package_detail.html",
        {
            "package": package,
            "status_options": list(ReviewPackageStatus),
            "package_position": package_position,
            "package_total": package_total,
            "timeline": timeline,
            "contact": contact,
            "active_guidance": active_guidance,
            "package_corrections": package_corrections,
            "review_correction_types": REVIEW_PACKAGE_CORRECTION_TYPES,
            "proposed_action_types": list(ProposedActionType),
            "test_readiness": test_readiness,
        },
        status_code=200 if package else 404,
    )


@web_router.post("/review-packages/{package_id}/status")
def web_update_review_package_status(
    package_id: int,
    status: str = Form(...),
    user_note: str | None = Form(None),
    draft_response: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        selected_status = ReviewPackageStatus(status)
        package = update_review_package_status(
            db,
            package_id,
            status=selected_status,
            user_note=user_note,
            draft_response=draft_response,
        )
        return RedirectResponse(url=f"/review-packages/{package.id}", status_code=303)
    except ValueError:
        return RedirectResponse(url="/review-packages", status_code=303)


@web_router.post("/review-packages/{package_id}/correct")
def web_correct_review_package(
    package_id: int,
    correction_type: str = Form(...),
    corrected_value: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        result = apply_review_package_correction(
            db,
            package_id,
            correction_type=correction_type,
            corrected_value=corrected_value,
            notes=notes,
        )
        return RedirectResponse(url=f"/review-packages/{result.package.id}", status_code=303)
    except ValueError:
        return RedirectResponse(url=f"/review-packages/{package_id}", status_code=303)


@web_router.get("/executions")
def executions_index(request: Request, db: Session = Depends(get_db)):
    status_filter = request.query_params.get("status", "pending")
    query = db.query(ExecutionRecord)
    if status_filter == "pending":
        query = query.filter(
            ExecutionRecord.status.in_(
                [
                    ExecutionStatus.PENDING_REVIEW,
                    ExecutionStatus.APPROVED,
                    ExecutionStatus.EXECUTING,
                ]
            )
        )
    elif status_filter == "executed":
        query = query.filter(ExecutionRecord.status == ExecutionStatus.EXECUTED)
    elif status_filter == "failed":
        query = query.filter(ExecutionRecord.status == ExecutionStatus.FAILED)
    elif status_filter in {"cancelled", "blocked"}:
        query = query.filter(ExecutionRecord.status == ExecutionStatus.CANCELLED)
    records = query.order_by(ExecutionRecord.created_at.desc(), ExecutionRecord.id.desc()).limit(200).all()
    all_records = list_execution_records(db)
    execution_counts = {
        "pending": len(
            [
                record
                for record in all_records
                if record.status
                in {
                    ExecutionStatus.PENDING_REVIEW,
                    ExecutionStatus.APPROVED,
                    ExecutionStatus.EXECUTING,
                }
            ]
        ),
        "executed": len([record for record in all_records if record.status == ExecutionStatus.EXECUTED]),
        "failed": len([record for record in all_records if record.status == ExecutionStatus.FAILED]),
        "cancelled": len([record for record in all_records if record.status == ExecutionStatus.CANCELLED]),
        "all": len(all_records),
    }
    return templates.TemplateResponse(
        request,
        "executions.html",
        {"records": records, "status_filter": status_filter, "execution_counts": execution_counts},
    )


@web_router.get("/executions/{execution_id}")
def execution_detail(execution_id: int, request: Request, db: Session = Depends(get_db)):
    import json as _json
    record = db.get(ExecutionRecord, execution_id)
    settings = get_settings()
    _payload: dict = {}
    if record and record.payload_json:
        try:
            _payload = _json.loads(record.payload_json)
        except Exception:
            _payload = {}
    _posture = cleanup_execution_posture(settings) if record else {}
    _cleanup_details = cleanup_execution_details(_payload, _posture) if _payload.get("cleanup_mode") else {}
    return templates.TemplateResponse(
        request,
        "execution_detail.html",
        {
            "record": record,
            "audit": audit_entries_for_execution(db, execution_id) if record else [],
            "attempts": execution_attempt_history(db, record) if record else [],
            "test_readiness": readiness_for_execution(record, settings) if record else None,
            "cleanup_details": _cleanup_details,
        },
        status_code=200 if record else 404,
    )


@web_router.post("/executions/{execution_id}/approve")
def web_approve_execution(execution_id: int, db: Session = Depends(get_db)):
    try:
        approve_execution(db, execution_id, actor="local-user")
    except ValueError:
        pass
    return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)


@web_router.post("/executions/{execution_id}/confirm")
def web_confirm_execution(
    execution_id: int,
    destructive_confirm_token: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        confirm_execution(
            db,
            execution_id,
            actor="local-user",
            destructive_confirm_token=destructive_confirm_token,
        )
    except ValueError:
        pass
    return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)


@web_router.post("/executions/{execution_id}/cancel")
def web_cancel_execution(execution_id: int, db: Session = Depends(get_db)):
    try:
        cancel_execution(db, execution_id, actor="local-user")
    except ValueError:
        pass
    return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)


@web_router.post("/executions/{execution_id}/rerun")
def web_rerun_execution(execution_id: int, db: Session = Depends(get_db)):
    try:
        prepared = rerun_execution(db, execution_id, actor="local-user")
        return RedirectResponse(url=f"/executions/{prepared.record.id}", status_code=303)
    except ValueError:
        return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)


@web_router.post("/executions/{execution_id}/clone")
def web_clone_execution(execution_id: int, db: Session = Depends(get_db)):
    try:
        prepared = clone_execution(db, execution_id, actor="local-user")
        return RedirectResponse(url=f"/executions/{prepared.record.id}", status_code=303)
    except ValueError:
        return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)


@web_router.post("/executions/{execution_id}/prepare-new")
def web_prepare_new_execution(execution_id: int, db: Session = Depends(get_db)):
    try:
        prepared = prepare_new_execution_from_existing(db, execution_id, actor="local-user")
        return RedirectResponse(url=f"/executions/{prepared.record.id}", status_code=303)
    except ValueError:
        return RedirectResponse(url=f"/executions/{execution_id}", status_code=303)
