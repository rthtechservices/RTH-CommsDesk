from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.connectors.notifications.webhook import normalize_notification_payload
from app.connectors.outlook.client import OutlookConnector
from app.connectors.teams.client import TeamsConnector
from app.services.gmail_sync_service import (
    SyncResult,
    _get_or_create_sync_state,
    _upsert_messages,
)


def sync_outlook_messages(
    db: Session,
    *,
    connector: OutlookConnector | None = None,
    limit: int = 100,
    since: datetime | None = None,
) -> SyncResult:
    source_type = "outlook"
    account_identifier = "microsoft-graph"
    return _sync_messages(
        db,
        source_type=source_type,
        account_identifier=account_identifier,
        fetcher=lambda: (connector or OutlookConnector()).fetch_recent_messages(limit=limit, since=since),
    )


def sync_teams_messages(
    db: Session,
    *,
    connector: TeamsConnector | None = None,
    limit: int = 100,
    since: datetime | None = None,
) -> SyncResult:
    source_type = "teams"
    account_identifier = "microsoft-graph"
    return _sync_messages(
        db,
        source_type=source_type,
        account_identifier=account_identifier,
        fetcher=lambda: (connector or TeamsConnector()).fetch_recent_messages(limit=limit, since=since),
    )


def ingest_notification_summary(
    db: Session,
    payload: dict,
) -> SyncResult:
    normalized = normalize_notification_payload(payload)
    return _sync_messages(
        db,
        source_type=normalized.source_type,
        account_identifier="notification-webhook",
        fetcher=lambda: [normalized],
    )


def _sync_messages(
    db: Session,
    *,
    source_type: str,
    account_identifier: str,
    fetcher,
) -> SyncResult:
    state = _get_or_create_sync_state(db, source_type, account_identifier)
    state.last_started_at = datetime.now(UTC)
    state.last_finished_at = None
    state.last_error = None
    db.commit()

    result = SyncResult(source_type=source_type, account_identifier=account_identifier)
    try:
        messages = fetcher()
    except Exception as exc:
        db.rollback()
        state = _get_or_create_sync_state(db, source_type, account_identifier)
        state.last_finished_at = datetime.now(UTC)
        state.last_error = str(exc)
        db.commit()
        raise
    result.fetched_count = len(messages)
    try:
        _upsert_messages(db, messages, result)
        state = _get_or_create_sync_state(db, source_type, account_identifier)
        state.last_finished_at = datetime.now(UTC)
        state.last_successful_sync_at = state.last_finished_at
        state.last_fetched_count = result.fetched_count
        state.last_inserted_count = result.inserted_count
        state.last_skipped_duplicate_count = result.skipped_duplicate_count
        state.last_updated_thread_count = result.updated_thread_count
        state.last_error = None
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        state = _get_or_create_sync_state(db, source_type, account_identifier)
        state.last_finished_at = datetime.now(UTC)
        state.last_fetched_count = result.fetched_count
        state.last_inserted_count = result.inserted_count
        state.last_skipped_duplicate_count = result.skipped_duplicate_count
        state.last_updated_thread_count = result.updated_thread_count
        state.last_error = str(exc)
        db.commit()
        result.errors.append(str(exc))
        raise
