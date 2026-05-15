from datetime import UTC, datetime

from sqlalchemy import func

from app.connectors.base import NormalizedMessage
from app.models.entities import (
    AttentionItem,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
)
from app.services.contact_service import mark_contact_noise, mark_contact_vip
from app.services.gmail_sync_service import sync_gmail_messages


class FakeConnector:
    def __init__(self, messages=None):
        self.last_limit = None
        self.last_since = None
        self.calls = []
        self.messages = messages or [
            NormalizedMessage(
                source_type="gmail",
                source_message_id="m1",
                source_thread_id="t1",
                sender_display_name="Alice",
                sender_email="alice@example.com",
                received_at=datetime(2026, 1, 1, tzinfo=UTC),
                subject="Status update",
                snippet="FYI only",
                body_text=None,
                has_attachments=False,
                is_unread=True,
                headers={"list-unsubscribe": "<mailto:unsubscribe@example.com>"},
            )
        ]

    def fetch_recent_messages(self, limit: int = 100, since=None):
        self.last_limit = limit
        self.last_since = since
        self.calls.append({"limit": limit, "since": since})
        return self.messages


class FakeSettings:
    gmail_read_max_results = 7
    gmail_account = "me"


def test_sync_passes_headers_to_classification_and_uses_configured_limit(db_session, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    result = sync_gmail_messages(db_session, connector=connector)

    assert result.inserted_count == 1
    assert result.fetched_count == 1
    assert result.skipped_duplicate_count == 0
    assert connector.last_limit == 7

    classification = db_session.query(MessageClassification).one()
    assert classification.is_newsletter is True
    assert "list-unsubscribe header" in (classification.classification_reason or "")


def test_sync_persists_watermark_and_reuses_it_for_incremental_fetch(db_session, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    first = sync_gmail_messages(db_session, connector=connector)
    second = sync_gmail_messages(db_session, connector=connector)

    assert first.high_water_received_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert second.inserted_count == 0
    assert second.skipped_duplicate_count == 1
    assert connector.calls[1]["since"] is not None
    assert connector.calls[1]["since"] < first.high_water_received_at


def test_repeat_sync_does_not_duplicate_messages_or_attention_items(db_session, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    sync_gmail_messages(db_session, connector=connector)
    result = sync_gmail_messages(db_session, connector=connector, force_resync=True)

    assert result.fetched_count == 1
    assert result.inserted_count == 0
    assert result.skipped_duplicate_count == 1
    assert db_session.query(func.count(Message.id)).scalar() == 1
    assert db_session.query(func.count(AttentionItem.id)).scalar() == 1


def test_sync_updates_duplicate_message_and_thread_metadata(db_session, monkeypatch):
    first_connector = FakeConnector(
        [
            NormalizedMessage(
                source_type="gmail",
                source_message_id="m1",
                source_thread_id="t1",
                sender_display_name="Alice",
                sender_email="alice@example.com",
                received_at=datetime(2026, 1, 1, tzinfo=UTC),
                subject="Old subject",
                snippet="old",
                body_text=None,
                has_attachments=False,
                is_unread=True,
            )
        ]
    )
    second_connector = FakeConnector(
        [
            NormalizedMessage(
                source_type="gmail",
                source_message_id="m1",
                source_thread_id="t1",
                sender_display_name="Alice",
                sender_email="alice@example.com",
                received_at=datetime(2026, 1, 1, tzinfo=UTC),
                subject="Old subject updated",
                snippet="updated",
                body_text=None,
                has_attachments=True,
                is_unread=False,
            ),
            NormalizedMessage(
                source_type="gmail",
                source_message_id="m2",
                source_thread_id="t1",
                sender_display_name="Alice",
                sender_email="alice@example.com",
                received_at=datetime(2026, 1, 2, tzinfo=UTC),
                subject="New subject",
                snippet="please reply",
                body_text=None,
                has_attachments=False,
                is_unread=True,
            ),
        ]
    )
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    sync_gmail_messages(db_session, connector=first_connector)
    result = sync_gmail_messages(db_session, connector=second_connector, force_resync=True)

    assert result.inserted_count == 1
    assert result.skipped_duplicate_count == 1
    assert result.updated_thread_count == 1

    original = db_session.query(Message).filter_by(source_message_id="m1").one()
    assert original.is_unread is False
    assert original.has_attachments is True
    assert original.snippet == "updated"

    thread = db_session.query(MessageThread).filter_by(source_thread_id="t1").one()
    assert thread.unread_count == 1
    assert thread.last_message_at.replace(tzinfo=UTC) == datetime(2026, 1, 2, tzinfo=UTC)
    assert thread.normalized_subject == "New subject"
    assert thread.requires_attention_score > 0


def test_marking_contact_vip_and_noise_recalculates_attention(db_session):
    contact = Contact(display_name="Alice", primary_email="alice@example.com", importance_tier=1)
    db_session.add(contact)
    db_session.flush()

    thread = MessageThread(
        source_type="gmail", source_thread_id="t1", contact_id=contact.id, unread_count=1
    )
    db_session.add(thread)
    db_session.flush()

    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="m1",
        sender_email="alice@example.com",
        received_at=datetime.now(UTC),
        subject="Can you review?",
        snippet="Please let me know",
        is_unread=True,
    )
    db_session.add(message)
    db_session.flush()

    classification = MessageClassification(
        message_id=message.id,
        requires_reply=True,
        urgency_level=0,
        is_human_personal=True,
        is_client_work=False,
        is_marketing=False,
        is_newsletter=False,
        is_receipt=False,
        is_group_noise=False,
        is_system_notification=False,
        classification_reason="initial",
    )
    db_session.add(classification)
    db_session.flush()

    item = AttentionItem(
        contact_id=contact.id, thread_id=thread.id, message_id=message.id, attention_score=10
    )
    db_session.add(item)
    db_session.commit()

    before = db_session.get(AttentionItem, item.id).attention_score

    mark_contact_vip(db_session, contact.id)
    boosted = db_session.get(AttentionItem, item.id)
    assert boosted.attention_score > before

    mark_contact_noise(db_session, "alice@example.com")
    lowered = db_session.get(AttentionItem, item.id)
    assert lowered.attention_score <= boosted.attention_score
    assert lowered.status.value == "dismissed"
