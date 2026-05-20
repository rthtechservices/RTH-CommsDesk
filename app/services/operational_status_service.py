from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    ExecutionRecord,
    ExecutionActionType,
    ExecutionStatus,
    Message,
    ProposedActionReviewPackage,
    ReviewPackageStatus,
    SourceSyncState,
)
from app.services.provider_status_service import provider_status_rows
from app.services.execution_test_policy import readiness_for_payload
from app.services.mailbox_cleanup_service import cleanup_candidate_summary


SOURCE_FILTERS = ("all", "gmail", "outlook", "notification")


@dataclass(frozen=True)
class SourceOperationalCount:
    key: str
    label: str
    message_count: int
    unreviewed_attention_count: int


@dataclass(frozen=True)
class SyncOperationalStatus:
    key: str
    label: str
    enabled: bool
    configured: bool
    last_successful_sync_at: object | None
    last_fetched_count: int | None
    last_inserted_count: int | None
    last_error: str | None
    next_action: str


def source_filter_label(source: str | None) -> str:
    normalized = (source or "all").strip().lower()
    if normalized == "gmail":
        return "Gmail"
    if normalized == "outlook":
        return "Outlook"
    if normalized == "notification":
        return "Notification-derived"
    return "All sources"


def source_filter_options() -> list[dict[str, str]]:
    return [
        {"value": "all", "label": "All"},
        {"value": "gmail", "label": "Gmail"},
        {"value": "outlook", "label": "Outlook"},
        {"value": "notification", "label": "Notification-derived"},
    ]


def source_operational_counts(db: Session) -> list[SourceOperationalCount]:
    return [
        SourceOperationalCount("all", "All", _message_count(db), _attention_count(db)),
        SourceOperationalCount("gmail", "Gmail", _message_count(db, "gmail"), _attention_count(db, "gmail")),
        SourceOperationalCount(
            "outlook",
            "Outlook",
            _message_count(db, "outlook"),
            _attention_count(db, "outlook"),
        ),
        SourceOperationalCount(
            "notification",
            "Notification-derived",
            _message_count(db, "notification"),
            _attention_count(db, "notification"),
        ),
    ]


def operational_smoke_status(
    db: Session, settings: Settings | None = None
) -> dict[str, object]:
    active = settings or get_settings()
    rows = provider_status_rows(active)
    provider_by_key = {row.key: row for row in rows}
    gmail_read = provider_by_key["gmail_read"]
    graph_auth = provider_by_key["microsoft_graph_delegated_auth"]
    outlook_read = provider_by_key["microsoft_graph_outlook_mail"]
    ai_provider = provider_by_key["ai_provider"]
    execution_blockers = [
        row
        for row in rows
        if row.state in {"missing_configuration", "failed"}
        or (row.state == "dry_run" and row.key != "ai_provider")
    ]
    disabled_boundaries = [
        provider_by_key.get("outlook_draft_create"),
        provider_by_key.get("outlook_send"),
        provider_by_key.get("outlook_mail_modify"),
        provider_by_key.get("outlook_calendar_write"),
        provider_by_key.get("microsoft_graph_teams"),
    ]
    disabled_boundaries = [r for r in disabled_boundaries if r is not None]
    return {
        "source_counts": source_operational_counts(db),
        "sync_statuses": [
            _sync_status(
                db,
                key="gmail",
                label="Gmail read sync",
                source_type="gmail",
                account_identifier=active.gmail_account,
                enabled=True,
                configured=gmail_read.state == "live",
                next_action=gmail_read.next_action,
            ),
            _sync_status(
                db,
                key="outlook",
                label="Outlook delegated Graph sync",
                source_type="outlook",
                account_identifier="microsoft-graph",
                enabled=active.microsoft_graph_outlook_mail_enabled,
                configured=outlook_read.state == "live",
                next_action=outlook_read.next_action,
            ),
        ],
        "gmail_read": gmail_read,
        "graph_auth": graph_auth,
        "outlook_read": outlook_read,
        "ai_provider": ai_provider,
        "execution_provider_mode": active.execution_provider,
        "external_write_dry_run": active.external_write_dry_run,
        "operational_test_mode": active.operational_test_mode,
        "execution_test_email_allowlist_configured": bool(
            active.execution_test_email_allowlist.strip()
        ),
        "test_execution_readiness": {
            "gmail_draft": readiness_for_payload(
                ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
                {"to": _sample_allowlisted_target(active.execution_test_email_allowlist)},
                active,
            ),
            "gmail_send": readiness_for_payload(
                ExecutionActionType.SEND_GMAIL_REPLY,
                {"to": _sample_allowlisted_target(active.execution_test_email_allowlist)},
                active,
            ),
            "google_calendar": readiness_for_payload(
                ExecutionActionType.CREATE_CALENDAR_EVENT,
                {},
                active,
            ),
            "gmail_cleanup": readiness_for_payload(
                ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE,
                {
                    "cleanup_mode": "cleanup_label",
                    "sender_email": "cleanup-smoke@example.com",
                    "source_message_ids": [],
                },
                active,
            ),
        },
        "gmail_write_flags": {
            "GMAIL_WRITE_ENABLED": active.gmail_write_enabled,
            "GMAIL_DRAFT_CREATE_ENABLED": active.gmail_draft_create_enabled,
            "GMAIL_SEND_ENABLED": active.gmail_send_enabled,
            "GMAIL_LABEL_ARCHIVE_ENABLED": active.gmail_label_archive_enabled,
        },
        "google_calendar_write_enabled": active.google_calendar_write_enabled,
        "mailbox_cleanup_summary": cleanup_candidate_summary(db),
        "mailbox_cleanup_execution_posture": cleanup_execution_posture(active),
        "operator_smoke_checklist": _operator_smoke_checklist(active),
        "route_smoke_paths": (
            "/",
            "/assistant-profile",
            "/operational-smoke",
            "/providers",
            "/review-packages",
            "/executions",
            "/bulk-triage",
            "/bulk-triage/mailbox-cleanup",
            "/contacts",
            "/drafts",
            "/voice-calibration",
            "/admin",
            "/healthz",
        ),
        "disabled_boundaries": disabled_boundaries,
        "blockers": execution_blockers,
        "pending_review_packages": _pending_review_package_count(db),
        "ready_execution_records": _ready_execution_count(db),
    }


def cleanup_execution_posture(settings: Settings | None = None) -> dict[str, object]:
    active = settings or get_settings()
    gmail_write = active.gmail_write_enabled
    label_archive = active.gmail_label_archive_enabled
    dry_run = active.external_write_dry_run
    provider = (active.execution_provider or "mock").strip().lower()
    is_external = provider in {"external", "live", "google"}

    if not gmail_write or not label_archive:
        missing = []
        if not gmail_write:
            missing.append("GMAIL_WRITE_ENABLED")
        if not label_archive:
            missing.append("GMAIL_LABEL_ARCHIVE_ENABLED")
        return {
            "posture": "blocked",
            "label": "Blocked — feature flags disabled",
            "detail": f"Set {', '.join(missing)} to enable Gmail cleanup execution.",
            "can_prepare": False,
            "can_execute_live": False,
            "dry_run": False,
        }
    if not is_external:
        return {
            "posture": "mock",
            "label": "Mock provider — local-only execution",
            "detail": "Set EXECUTION_PROVIDER=external to enable live Gmail cleanup.",
            "can_prepare": True,
            "can_execute_live": False,
            "dry_run": False,
        }
    if dry_run:
        return {
            "posture": "dry_run",
            "label": "Dry-run — Gmail capable but writes simulated",
            "detail": "Set EXTERNAL_WRITE_DRY_RUN=false to allow live Gmail label/archive.",
            "can_prepare": True,
            "can_execute_live": False,
            "dry_run": True,
        }
    return {
        "posture": "live",
        "label": "Live — Gmail label/archive capable",
        "detail": "Gmail mutations occur only after prepare, approve, and final confirm.",
        "can_prepare": True,
        "can_execute_live": True,
        "dry_run": False,
    }


def _sync_status(
    db: Session,
    *,
    key: str,
    label: str,
    source_type: str,
    account_identifier: str,
    enabled: bool,
    configured: bool,
    next_action: str,
) -> SyncOperationalStatus:
    state = (
        db.query(SourceSyncState)
        .filter_by(source_type=source_type, account_identifier=account_identifier)
        .first()
    )
    return SyncOperationalStatus(
        key=key,
        label=label,
        enabled=enabled,
        configured=configured,
        last_successful_sync_at=state.last_successful_sync_at if state else None,
        last_fetched_count=state.last_fetched_count if state else None,
        last_inserted_count=state.last_inserted_count if state else None,
        last_error=state.last_error if state else None,
        next_action=next_action,
    )


def _source_predicate(source: str | None):
    normalized = (source or "all").strip().lower()
    if normalized == "notification":
        return Message.source_type.like("notification_%")
    if normalized in {"gmail", "outlook"}:
        return Message.source_type == normalized
    return None


def _message_count(db: Session, source: str | None = None) -> int:
    query = db.query(func.count(Message.id))
    predicate = _source_predicate(source)
    if predicate is not None:
        query = query.filter(predicate)
    return query.scalar() or 0


def _attention_count(db: Session, source: str | None = None) -> int:
    query = db.query(func.count(AttentionItem.id)).join(Message, AttentionItem.message_id == Message.id)
    query = query.filter(AttentionItem.status == AttentionStatus.NEW)
    predicate = _source_predicate(source)
    if predicate is not None:
        query = query.filter(predicate)
    return query.scalar() or 0


def _pending_review_package_count(db: Session) -> int:
    return (
        db.query(func.count(ProposedActionReviewPackage.id))
        .filter(ProposedActionReviewPackage.status == ReviewPackageStatus.PENDING)
        .scalar()
        or 0
    )


def _ready_execution_count(db: Session) -> int:
    return (
        db.query(func.count(ExecutionRecord.id))
        .filter(
            or_(
                ExecutionRecord.status == ExecutionStatus.PENDING_REVIEW,
                ExecutionRecord.status == ExecutionStatus.APPROVED,
            )
        )
        .scalar()
        or 0
    )


def _sample_allowlisted_target(raw_allowlist: str | None) -> str:
    first = next((item.strip() for item in (raw_allowlist or "").split(",") if item.strip()), "")
    if first.startswith("@"):
        return f"test{first}"
    return first


def _operator_smoke_checklist(settings: Settings) -> tuple[dict[str, object], ...]:
    return (
        {
            "name": "Route smoke",
            "provider": "local app",
            "state": "manual",
            "detail": "Open each route listed below or run the documented route smoke command.",
            "external_write_performed": False,
        },
        {
            "name": "Azure/OpenAI AI test",
            "provider": settings.ai_provider,
            "state": "ready" if settings.ai_provider != "mock" else "mock",
            "detail": "Run POST /api/ai/test; output is sanitized and should not include keys.",
            "external_write_performed": False,
        },
        {
            "name": "Microsoft Graph delegated test",
            "provider": "microsoft_graph",
            "state": "ready" if settings.microsoft_graph_enabled else "disabled",
            "detail": "Run POST /api/graph/test before Outlook sync.",
            "external_write_performed": False,
        },
        {
            "name": "Outlook sync readiness",
            "provider": "outlook_mail_read",
            "state": "ready" if settings.microsoft_graph_outlook_mail_enabled else "disabled",
            "detail": "Outlook read only; no Graph write calls are wired.",
            "external_write_performed": False,
        },
        {
            "name": "Mailbox cleanup readiness",
            "provider": "gmail_cleanup",
            "state": "ready"
            if settings.gmail_write_enabled and settings.gmail_label_archive_enabled
            else "blocked",
            "detail": "Cleanup remains gated through execution_service; no direct Gmail mutation from cleanup pages.",
            "external_write_performed": False,
        },
        {
            "name": "Gmail draft dry-run readiness",
            "provider": "gmail",
            "state": "ready"
            if settings.external_write_dry_run
            and settings.gmail_write_enabled
            and settings.gmail_draft_create_enabled
            else "blocked",
            "detail": "Requires operational test mode, allowlist, external provider, write flag, draft flag, and dry-run.",
            "external_write_performed": False,
        },
        {
            "name": "Gmail draft live readiness",
            "provider": "gmail",
            "state": "ready"
            if not settings.external_write_dry_run
            and settings.gmail_write_enabled
            and settings.gmail_draft_create_enabled
            else "blocked",
            "detail": "Only after OAuth write scopes, allowlist, approval, and final confirmation are reviewed.",
            "external_write_performed": not settings.external_write_dry_run,
        },
        {
            "name": "Google Calendar dry-run/live readiness",
            "provider": "google_calendar",
            "state": "ready" if settings.google_calendar_write_enabled else "blocked",
            "detail": "Calendar execution still requires prepare, approve, confirm, and Phase 19 test mode.",
            "external_write_performed": settings.google_calendar_write_enabled
            and not settings.external_write_dry_run,
        },
        {
            "name": "Execution audit check",
            "provider": "local database",
            "state": "manual",
            "detail": "Open /executions after a dry-run/live test and verify audit history.",
            "external_write_performed": False,
        },
    )
