from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    ExecutionRecord,
    ExecutionStatus,
    Message,
    ProposedActionReviewPackage,
    ReviewPackageStatus,
    SourceSyncState,
)
from app.services.provider_status_service import provider_status_rows


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
        provider_by_key["microsoft_graph_outlook_mail_send"],
        provider_by_key["outlook_calendar_read"],
        provider_by_key["microsoft_graph_teams"],
    ]
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
        "gmail_write_flags": {
            "GMAIL_WRITE_ENABLED": active.gmail_write_enabled,
            "GMAIL_DRAFT_CREATE_ENABLED": active.gmail_draft_create_enabled,
            "GMAIL_SEND_ENABLED": active.gmail_send_enabled,
            "GMAIL_LABEL_ARCHIVE_ENABLED": active.gmail_label_archive_enabled,
        },
        "google_calendar_write_enabled": active.google_calendar_write_enabled,
        "disabled_boundaries": disabled_boundaries,
        "blockers": execution_blockers,
        "pending_review_packages": _pending_review_package_count(db),
        "ready_execution_records": _ready_execution_count(db),
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
