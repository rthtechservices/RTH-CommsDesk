from datetime import UTC, datetime

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
    def __init__(self):
        self.last_limit = None
        self.last_since = None

    def fetch_recent_messages(self, limit: int = 100, since=None):
        self.last_limit = limit
        self.last_since = since
        return [
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


class FakeSettings:
    gmail_read_max_results = 7


def test_sync_passes_headers_to_classification_and_uses_configured_limit(db_session, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    synced = sync_gmail_messages(db_session, connector=connector)

    assert synced == 1
    assert connector.last_limit == 7

    classification = db_session.query(MessageClassification).one()
    assert classification.is_newsletter is True
    assert "list-unsubscribe header" in (classification.classification_reason or "")


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
