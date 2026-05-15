from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.connectors.base import NormalizedMessage
from app.connectors.gmail.client import GmailConnector
from app.core.config import get_settings
from app.models.entities import (
    BodyStoredMode,
    AttentionItem,
    Message,
    MessageThread,
    SourceSyncState,
)
from app.services.attention_service import upsert_attention_item
from app.services.classification_service import classify_and_persist
from app.services.contact_service import ensure_contact_for_sender

SYNC_OVERLAP_SECONDS = 1


@dataclass
class SyncResult:
    source_type: str
    account_identifier: str
    fetched_count: int = 0
    inserted_count: int = 0
    skipped_duplicate_count: int = 0
    updated_thread_count: int = 0
    errors: list[str] = field(default_factory=list)
    high_water_received_at: datetime | None = None
    high_water_message_id: str | None = None
    since: datetime | None = None
    resync: bool = False

    @property
    def synced(self) -> int:
        return self.inserted_count

    def as_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "account_identifier": self.account_identifier,
            "fetched_count": self.fetched_count,
            "inserted_count": self.inserted_count,
            "skipped_duplicate_count": self.skipped_duplicate_count,
            "updated_thread_count": self.updated_thread_count,
            "errors": self.errors,
            "high_water_received_at": (
                self.high_water_received_at.isoformat() if self.high_water_received_at else None
            ),
            "high_water_message_id": self.high_water_message_id,
            "since": self.since.isoformat() if self.since else None,
            "resync": self.resync,
        }


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_sync_state(
    db: Session, source_type: str = "gmail", account_identifier: str | None = None
) -> SourceSyncState | None:
    account_identifier = account_identifier or get_settings().gmail_account
    return (
        db.query(SourceSyncState)
        .filter_by(source_type=source_type, account_identifier=account_identifier)
        .first()
    )


def _get_or_create_sync_state(
    db: Session, source_type: str, account_identifier: str
) -> SourceSyncState:
    state = get_sync_state(db, source_type=source_type, account_identifier=account_identifier)
    if state:
        return state
    state = SourceSyncState(source_type=source_type, account_identifier=account_identifier)
    db.add(state)
    db.flush()
    return state


def _effective_since(state: SourceSyncState, explicit_since: datetime | None) -> datetime | None:
    if explicit_since:
        return explicit_since
    high_water = _utc(state.high_water_received_at)
    if not high_water:
        return None
    return high_water - timedelta(seconds=SYNC_OVERLAP_SECONDS)


def _update_existing_message(existing: Message, item: NormalizedMessage) -> None:
    existing.sender_display_name = item.sender_display_name
    existing.sender_email = item.sender_email
    existing.received_at = item.received_at or existing.received_at
    existing.subject = item.subject
    existing.snippet = item.snippet
    if item.body_text:
        existing.body_text = item.body_text
        existing.body_stored_mode = BodyStoredMode.FULL_TEXT
    existing.is_unread = item.is_unread
    existing.has_attachments = item.has_attachments


def _refresh_thread_metadata(db: Session, thread_id: int) -> bool:
    thread = db.get(MessageThread, thread_id)
    if not thread:
        return False

    unread_count = (
        db.query(func.count(Message.id))
        .filter(Message.thread_id == thread_id, Message.is_unread.is_(True))
        .scalar()
        or 0
    )
    last_message = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.received_at.desc(), Message.id.desc())
        .first()
    )
    max_attention_score = (
        db.query(func.max(AttentionItem.attention_score))
        .filter(AttentionItem.thread_id == thread_id)
        .scalar()
        or 0
    )

    changed = False
    if thread.unread_count != unread_count:
        thread.unread_count = unread_count
        changed = True
    if last_message:
        if thread.last_message_at != last_message.received_at:
            thread.last_message_at = last_message.received_at
            changed = True
        if last_message.subject and thread.normalized_subject != last_message.subject:
            thread.normalized_subject = last_message.subject
            changed = True
    if thread.requires_attention_score != max_attention_score:
        thread.requires_attention_score = max_attention_score
        changed = True

    return changed


def sync_gmail_messages(
    db: Session,
    since: datetime | None = None,
    connector: GmailConnector | None = None,
    force_resync: bool = False,
) -> SyncResult:
    connector = connector or GmailConnector()
    settings = get_settings()
    account_identifier = settings.gmail_account
    state = _get_or_create_sync_state(db, "gmail", account_identifier)
    effective_since = None if force_resync else _effective_since(state, since)
    started_at = datetime.now(UTC)
    state.last_started_at = started_at
    state.last_finished_at = None
    state.last_error = None
    db.commit()

    result = SyncResult(
        source_type="gmail",
        account_identifier=account_identifier,
        since=effective_since,
        resync=force_resync,
        high_water_received_at=_utc(state.high_water_received_at),
        high_water_message_id=state.high_water_message_id,
    )

    try:
        messages = connector.fetch_recent_messages(
            limit=settings.gmail_read_max_results, since=effective_since
        )
    except Exception as exc:
        db.rollback()
        state = _get_or_create_sync_state(db, "gmail", account_identifier)
        state.last_started_at = started_at
        state.last_finished_at = datetime.now(UTC)
        state.last_error = str(exc)
        db.commit()
        raise

    result.fetched_count = len(messages)
    touched_thread_ids: set[int] = set()
    newest_message = _newest_message(messages)

    try:
        for item in messages:
            contact = ensure_contact_for_sender(db, item.sender_email, item.sender_display_name)

            thread = (
                db.query(MessageThread)
                .filter_by(source_type=item.source_type, source_thread_id=item.source_thread_id)
                .first()
            )
            if not thread:
                thread = MessageThread(
                    source_type=item.source_type,
                    source_thread_id=item.source_thread_id,
                    normalized_subject=item.subject,
                    contact_id=contact.id if contact else None,
                    unread_count=0,
                    last_message_at=item.received_at,
                )
                db.add(thread)
                db.flush()
            elif contact and thread.contact_id is None:
                thread.contact_id = contact.id

            existing = (
                db.query(Message)
                .filter_by(source_type=item.source_type, source_message_id=item.source_message_id)
                .first()
            )
            if existing:
                _update_existing_message(existing, item)
                touched_thread_ids.add(existing.thread_id)
                result.skipped_duplicate_count += 1
                continue

            message = Message(
                thread_id=thread.id,
                source_type=item.source_type,
                source_message_id=item.source_message_id,
                sender_display_name=item.sender_display_name,
                sender_email=item.sender_email,
                received_at=item.received_at or datetime.now(UTC),
                subject=item.subject,
                snippet=item.snippet,
                body_text=item.body_text,
                body_stored_mode=(
                    BodyStoredMode.FULL_TEXT if item.body_text else BodyStoredMode.SNIPPET_ONLY
                ),
                is_unread=item.is_unread,
                has_attachments=item.has_attachments,
            )
            db.add(message)
            db.flush()

            classification = classify_and_persist(message, headers=item.headers)
            db.add(classification)
            db.flush()

            upsert_attention_item(db, contact, thread, message, classification)
            touched_thread_ids.add(thread.id)
            result.inserted_count += 1

        for thread_id in touched_thread_ids:
            if _refresh_thread_metadata(db, thread_id):
                result.updated_thread_count += 1

        state = _get_or_create_sync_state(db, "gmail", account_identifier)
        state.last_finished_at = datetime.now(UTC)
        state.last_successful_sync_at = state.last_finished_at
        state.last_fetched_count = result.fetched_count
        state.last_inserted_count = result.inserted_count
        state.last_skipped_duplicate_count = result.skipped_duplicate_count
        state.last_updated_thread_count = result.updated_thread_count
        state.last_error = None

        if newest_message:
            newest_received_at = _utc(newest_message.received_at)
            current_high_water = _utc(state.high_water_received_at)
            if newest_received_at and (
                current_high_water is None or newest_received_at >= current_high_water
            ):
                state.high_water_received_at = newest_received_at
                state.high_water_message_id = newest_message.source_message_id
                result.high_water_received_at = newest_received_at
                result.high_water_message_id = newest_message.source_message_id

        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        state = _get_or_create_sync_state(db, "gmail", account_identifier)
        state.last_started_at = started_at
        state.last_finished_at = datetime.now(UTC)
        state.last_fetched_count = result.fetched_count
        state.last_inserted_count = result.inserted_count
        state.last_skipped_duplicate_count = result.skipped_duplicate_count
        state.last_updated_thread_count = result.updated_thread_count
        state.last_error = str(exc)
        db.commit()
        result.errors.append(str(exc))
        raise


def _newest_message(messages: list[NormalizedMessage]) -> NormalizedMessage | None:
    dated_messages = [message for message in messages if message.received_at]
    if not dated_messages:
        return None
    return max(dated_messages, key=lambda message: _utc(message.received_at) or datetime.min)
