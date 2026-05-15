import base64
from datetime import UTC, datetime, timedelta

from app.connectors.base import MessagePage, NormalizedMessage
from app.connectors.gmail.client import GmailConnector
from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    BodyStoredMode,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
)
from app.services.attention_service import build_attention_queue
from app.services.conversation_service import conversation_timeline
from app.services.gmail_sync_service import fetch_full_gmail_conversation, sync_gmail_backfill


def _encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _message(
    source_message_id: str,
    source_thread_id: str = "thread-1",
    sender: str = "alice@example.com",
    received_at: datetime | None = None,
    body_text: str | None = None,
) -> NormalizedMessage:
    return NormalizedMessage(
        source_type="gmail",
        source_message_id=source_message_id,
        source_thread_id=source_thread_id,
        sender_display_name=sender.split("@")[0].title(),
        sender_email=sender,
        recipient_emails=["rohan@example.com"],
        cc_emails=["group@example.com"],
        received_at=received_at or datetime(2026, 1, 1, tzinfo=UTC),
        subject="Dinner",
        snippet=body_text or "snippet",
        body_text=body_text,
        has_attachments=False,
        is_unread=True,
    )


def test_gmail_body_extraction_prefers_plain_text_and_preserves_quotes():
    connector = GmailConnector(service=object())
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {
                    "data": _encoded(
                        "Michael wrote:\n> No worries, thanks for the heads up!\n\nChristian cancelled dinner."
                    )
                },
            },
            {
                "mimeType": "text/html",
                "body": {"data": _encoded("<p>Ignored HTML alternative</p>")},
            },
        ],
    }

    body = connector._extract_body(payload)

    assert "Christian cancelled dinner" in body
    assert "> No worries" in body


def test_gmail_body_extraction_sanitizes_html_fallback():
    connector = GmailConnector(service=object())
    payload = {
        "mimeType": "text/html",
        "body": {
            "data": _encoded(
                "<html><body><p>Christian cancelled dinner.</p>"
                "<script>alert('private')</script><div>Michael acknowledged.</div></body></html>"
            )
        },
    }

    body = connector._extract_body(payload)

    assert "Christian cancelled dinner." in body
    assert "Michael acknowledged." in body
    assert "<p>" not in body
    assert "alert" not in body


class FakePagedConnector:
    def __init__(self):
        self.calls = []

    def fetch_message_page(self, limit=100, since=None, page_token=None):
        self.calls.append({"limit": limit, "page_token": page_token})
        return MessagePage(
            messages=[
                _message(
                    "old-1",
                    received_at=datetime(2025, 12, 1, tzinfo=UTC),
                    body_text=None,
                )
            ],
            next_page_token="older-page",
        )


class FakeSettings:
    gmail_read_max_results = 1
    gmail_account = "me"


def test_historical_backfill_uses_persisted_gmail_page_token(db_session, monkeypatch):
    connector = FakePagedConnector()
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    first = sync_gmail_backfill(db_session, connector=connector)
    second = sync_gmail_backfill(db_session, connector=connector)

    assert first.fetched_count == 1
    assert second.skipped_duplicate_count == 1
    assert connector.calls[0]["page_token"] is None
    assert connector.calls[1]["page_token"] == "older-page"


class FakeThreadConnector:
    def fetch_thread_messages(self, source_thread_id):
        assert source_thread_id == "gmail-thread-1"
        return [
            _message(
                "christian-1",
                "gmail-thread-1",
                sender="christian@example.com",
                received_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
                body_text="Sorry everyone, I need to cancel dinner tonight.",
            ),
            _message(
                "michael-1",
                "gmail-thread-1",
                sender="michael@example.com",
                received_at=datetime(2026, 5, 1, 18, 5, tzinfo=UTC),
                body_text="No worries, thanks for the heads up! <3",
            ),
        ]


def test_full_gmail_conversation_fetch_upserts_thread_messages(db_session, monkeypatch):
    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())
    thread = MessageThread(source_type="gmail", source_thread_id="gmail-thread-1")
    db_session.add(thread)
    db_session.flush()
    selected = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="michael-1",
        sender_email="michael@example.com",
        received_at=datetime(2026, 5, 1, 18, 5, tzinfo=UTC),
        subject="Dinner",
        snippet="No worries",
        body_stored_mode=BodyStoredMode.SNIPPET_ONLY,
    )
    db_session.add(selected)
    db_session.commit()

    result = fetch_full_gmail_conversation(db_session, selected.id, connector=FakeThreadConnector())

    assert result.full_thread_fetched_count == 2
    assert db_session.query(Message).filter_by(thread_id=thread.id).count() == 2
    refreshed = db_session.query(Message).filter_by(source_message_id="michael-1").one()
    assert refreshed.body_stored_mode == BodyStoredMode.FULL_TEXT
    assert "No worries" in refreshed.body_text
    assert db_session.get(MessageThread, thread.id).full_content_fetched_at is not None


def test_conversation_timeline_orders_messages_and_marks_selected(db_session):
    thread = MessageThread(source_type="gmail", source_thread_id="t-order")
    db_session.add(thread)
    db_session.flush()
    later = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="later",
        sender_email="michael@example.com",
        received_at=datetime(2026, 1, 1, 10, 5, tzinfo=UTC),
        subject="Dinner",
        snippet="No worries",
        body_stored_mode=BodyStoredMode.SNIPPET_ONLY,
    )
    earlier = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="earlier",
        sender_email="christian@example.com",
        received_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        subject="Dinner",
        snippet="I need to cancel dinner",
        body_stored_mode=BodyStoredMode.SNIPPET_ONLY,
    )
    db_session.add_all([later, earlier])
    db_session.commit()

    timeline = conversation_timeline(db_session, thread.id, later.id)

    assert [entry.message.source_message_id for entry in timeline] == ["earlier", "later"]
    assert [entry.is_selected for entry in timeline] == [False, True]


def test_reviewed_and_noise_items_do_not_dominate_default_active_queue(db_session):
    contact = Contact(display_name="Noise Sender", primary_email="noise@example.com", is_noise=True)
    db_session.add(contact)
    db_session.flush()
    thread = MessageThread(
        source_type="gmail", source_thread_id="noise-thread", contact_id=contact.id
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="noise-message",
        sender_email="noise@example.com",
        received_at=datetime.now(UTC) - timedelta(hours=1),
        subject="Promo",
        snippet="discount",
        body_stored_mode=BodyStoredMode.SNIPPET_ONLY,
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            is_marketing=True,
            classification_reason="marketing",
        )
    )
    db_session.add_all(
        [
            AttentionItem(
                thread_id=thread.id,
                message_id=message.id,
                contact_id=contact.id,
                attention_score=95,
                status=AttentionStatus.DISMISSED,
            ),
            AttentionItem(thread_id=999, attention_score=50, status=AttentionStatus.REVIEWED),
            AttentionItem(thread_id=998, attention_score=30, status=AttentionStatus.NEW),
        ]
    )
    db_session.commit()

    active = build_attention_queue(db_session)
    noise = build_attention_queue(db_session, status_filter="noise", noise=True)

    assert [item.status for item in active] == [AttentionStatus.NEW]
    assert any(item.status == AttentionStatus.DISMISSED for item in noise)
