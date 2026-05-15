from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.models.entities import (
    BodyStoredMode,
    ExecutionActionType,
    ExecutionAuditLog,
    ExecutionRecord,
    Message,
    MessageThread,
    SentMailLearningRecord,
)
from app.services.admin_service import clear_cached_content, run_retention_cleanup


def test_run_retention_cleanup_clears_old_records(monkeypatch, db_session):
    monkeypatch.setenv("RETENTION_MESSAGE_BODY_DAYS", "30")
    monkeypatch.setenv("RETENTION_SENT_LEARNING_DAYS", "60")
    monkeypatch.setenv("RETENTION_EXECUTION_AUDIT_DAYS", "90")
    get_settings.cache_clear()

    now = datetime(2026, 5, 15, 15, 0, tzinfo=UTC)

    thread = MessageThread(source_type="gmail", source_thread_id="retention-thread")
    db_session.add(thread)
    db_session.flush()

    old_message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="old-message",
        sender_email="old@example.com",
        snippet="old snippet",
        body_text="old body",
        body_stored_mode=BodyStoredMode.FULL_TEXT,
        received_at=now - timedelta(days=45),
    )
    new_message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="new-message",
        sender_email="new@example.com",
        snippet="new snippet",
        body_text="new body",
        body_stored_mode=BodyStoredMode.FULL_TEXT,
        received_at=now - timedelta(days=5),
    )
    db_session.add_all([old_message, new_message])

    old_sent = SentMailLearningRecord(
        source_type="gmail",
        source_message_id="old-sent",
        recipient_email="recipient@example.com",
        sent_at=now - timedelta(days=70),
        snippet_excerpt="old sent snippet",
        body_excerpt="old sent body",
    )
    new_sent = SentMailLearningRecord(
        source_type="gmail",
        source_message_id="new-sent",
        recipient_email="recipient2@example.com",
        sent_at=now - timedelta(days=10),
        snippet_excerpt="new sent snippet",
        body_excerpt="new sent body",
    )
    db_session.add_all([old_sent, new_sent])

    execution = ExecutionRecord(
        action_type=ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
        payload_json="{}",
    )
    db_session.add(execution)
    db_session.flush()
    db_session.add_all(
        [
            ExecutionAuditLog(
                execution_record_id=execution.id,
                event_type="old",
                created_at=now - timedelta(days=120),
            ),
            ExecutionAuditLog(
                execution_record_id=execution.id,
                event_type="new",
                created_at=now - timedelta(days=3),
            ),
        ]
    )
    db_session.commit()

    result = run_retention_cleanup(db_session, now=now)

    assert result.message_bodies_cleared == 1
    assert result.sent_learning_excerpts_cleared == 1
    assert result.execution_audit_rows_deleted == 1

    db_session.refresh(old_message)
    db_session.refresh(new_message)
    db_session.refresh(old_sent)
    db_session.refresh(new_sent)
    assert old_message.body_text is None
    assert old_message.body_stored_mode == BodyStoredMode.SNIPPET_ONLY
    assert new_message.body_text == "new body"
    assert old_sent.body_excerpt is None
    assert old_sent.snippet_excerpt is None
    assert new_sent.body_excerpt == "new sent body"

    get_settings.cache_clear()


def test_clear_cached_content_respects_selected_flags(db_session):
    thread = MessageThread(source_type="gmail", source_thread_id="cache-thread")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="cache-message",
        sender_email="cache@example.com",
        snippet="summary",
        body_text="cached body",
        body_stored_mode=BodyStoredMode.FULL_TEXT,
    )
    sent = SentMailLearningRecord(
        source_type="gmail",
        source_message_id="cache-sent",
        recipient_email="recipient@example.com",
        snippet_excerpt="sent snippet",
        body_excerpt="sent body",
    )
    db_session.add_all([message, sent])
    db_session.commit()

    message_only = clear_cached_content(
        db_session,
        clear_message_bodies=True,
        clear_sent_learning_excerpts=False,
    )
    assert message_only.message_bodies_cleared == 1
    assert message_only.sent_learning_excerpts_cleared == 0
    db_session.refresh(message)
    db_session.refresh(sent)
    assert message.body_text is None
    assert sent.body_excerpt == "sent body"

    sent_only = clear_cached_content(
        db_session,
        clear_message_bodies=False,
        clear_sent_learning_excerpts=True,
    )
    assert sent_only.message_bodies_cleared == 0
    assert sent_only.sent_learning_excerpts_cleared == 1
    db_session.refresh(sent)
    assert sent.body_excerpt is None
