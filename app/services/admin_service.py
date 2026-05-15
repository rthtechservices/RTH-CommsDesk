from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    BodyStoredMode,
    ExecutionAuditLog,
    Message,
    SentMailLearningRecord,
)


@dataclass
class RetentionCleanupResult:
    message_bodies_cleared: int = 0
    sent_learning_excerpts_cleared: int = 0
    execution_audit_rows_deleted: int = 0

    def as_dict(self) -> dict:
        return {
            "message_bodies_cleared": self.message_bodies_cleared,
            "sent_learning_excerpts_cleared": self.sent_learning_excerpts_cleared,
            "execution_audit_rows_deleted": self.execution_audit_rows_deleted,
        }


@dataclass
class CacheClearResult:
    message_bodies_cleared: int = 0
    sent_learning_excerpts_cleared: int = 0

    def as_dict(self) -> dict:
        return {
            "message_bodies_cleared": self.message_bodies_cleared,
            "sent_learning_excerpts_cleared": self.sent_learning_excerpts_cleared,
        }


def run_retention_cleanup(db: Session, *, now: datetime | None = None) -> RetentionCleanupResult:
    settings = get_settings()
    now = now or datetime.now(UTC)

    result = RetentionCleanupResult()

    message_cutoff = _cutoff(now, settings.retention_message_body_days)
    if message_cutoff:
        result.message_bodies_cleared = _clear_message_bodies_before(db, message_cutoff)

    sent_cutoff = _cutoff(now, settings.retention_sent_learning_days)
    if sent_cutoff:
        result.sent_learning_excerpts_cleared = _clear_sent_learning_excerpts_before(db, sent_cutoff)

    audit_cutoff = _cutoff(now, settings.retention_execution_audit_days)
    if audit_cutoff:
        result.execution_audit_rows_deleted = (
            db.query(ExecutionAuditLog)
            .filter(ExecutionAuditLog.created_at < audit_cutoff)
            .delete(synchronize_session=False)
        )

    db.commit()
    return result


def clear_cached_content(
    db: Session,
    *,
    clear_message_bodies: bool = True,
    clear_sent_learning_excerpts: bool = True,
) -> CacheClearResult:
    result = CacheClearResult()

    if clear_message_bodies:
        result.message_bodies_cleared = _clear_all_message_bodies(db)
    if clear_sent_learning_excerpts:
        result.sent_learning_excerpts_cleared = _clear_all_sent_learning_excerpts(db)

    db.commit()
    return result


def _cutoff(now: datetime, retention_days: int) -> datetime | None:
    if retention_days < 1:
        return None
    return now - timedelta(days=retention_days)


def _clear_message_bodies_before(db: Session, cutoff: datetime) -> int:
    rows = (
        db.query(Message)
        .filter(Message.received_at < cutoff)
        .filter(Message.body_text.is_not(None))
        .all()
    )
    for message in rows:
        _clear_message_body(message)
    return len(rows)


def _clear_all_message_bodies(db: Session) -> int:
    rows = db.query(Message).filter(Message.body_text.is_not(None)).all()
    for message in rows:
        _clear_message_body(message)
    return len(rows)


def _clear_message_body(message: Message) -> None:
    message.body_text = None
    message.body_stored_mode = (
        BodyStoredMode.SNIPPET_ONLY if message.snippet else BodyStoredMode.METADATA_ONLY
    )


def _clear_sent_learning_excerpts_before(db: Session, cutoff: datetime) -> int:
    rows = (
        db.query(SentMailLearningRecord)
        .filter(SentMailLearningRecord.sent_at < cutoff)
        .filter(
            or_(
                SentMailLearningRecord.body_excerpt.is_not(None),
                SentMailLearningRecord.snippet_excerpt.is_not(None),
            )
        )
        .all()
    )
    for row in rows:
        row.body_excerpt = None
        row.snippet_excerpt = None
    return len(rows)


def _clear_all_sent_learning_excerpts(db: Session) -> int:
    rows = (
        db.query(SentMailLearningRecord)
        .filter(
            or_(
                SentMailLearningRecord.body_excerpt.is_not(None),
                SentMailLearningRecord.snippet_excerpt.is_not(None),
            )
        )
        .all()
    )
    for row in rows:
        row.body_excerpt = None
        row.snippet_excerpt = None
    return len(rows)
