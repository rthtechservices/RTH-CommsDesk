from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.base import NormalizedMessage
from app.models.entities import Message
from app.services.external_connectors_service import (
    ingest_notification_summary,
    sync_outlook_messages,
    sync_teams_messages,
)


class FakeOutlookConnector:
    def fetch_recent_messages(self, limit: int = 100, since=None):
        return [
            NormalizedMessage(
                source_type="outlook",
                source_message_id="outlook-1",
                source_thread_id="outlook-thread-1",
                sender_display_name="Client",
                sender_email="client@outlook.example",
                recipient_emails=["rohan@example.com"],
                cc_emails=[],
                received_at=datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
                subject="Outlook update",
                snippet="Please review",
                body_text="Please review the latest draft.",
                has_attachments=False,
                is_unread=True,
                source_channel="email",
                source_confidence=0.95,
            )
        ]


class FakeTeamsConnector:
    def fetch_recent_messages(self, limit: int = 100, since=None):
        return [
            NormalizedMessage(
                source_type="teams",
                source_message_id="teams-1",
                source_thread_id="chat-1",
                sender_display_name="Teammate",
                sender_email="teammate@example.com",
                recipient_emails=[],
                cc_emails=[],
                received_at=datetime(2026, 5, 15, 13, 0, tzinfo=UTC),
                subject="Teams message from Teammate",
                snippet="Can we sync later?",
                body_text="Can we sync later?",
                has_attachments=False,
                is_unread=False,
                source_channel="teams",
                source_confidence=0.85,
            )
        ]


def test_outlook_sync_ingests_normalized_messages(db_session):
    result = sync_outlook_messages(db_session, connector=FakeOutlookConnector())

    assert result.inserted_count == 1
    message = db_session.query(Message).filter_by(source_message_id="outlook-1").one()
    assert message.source_type == "outlook"
    assert message.source_channel == "email"
    assert float(message.source_confidence) == 0.95


def test_teams_sync_ingests_normalized_messages(db_session):
    result = sync_teams_messages(db_session, connector=FakeTeamsConnector())

    assert result.inserted_count == 1
    message = db_session.query(Message).filter_by(source_message_id="teams-1").one()
    assert message.source_type == "teams"
    assert message.source_channel == "teams"
    assert float(message.source_confidence) == 0.85


def test_notification_webhook_ingestion_is_duplicate_safe(db_session):
    payload = {
        "notification_id": "notif-1",
        "channel": "whatsapp",
        "sender": "+16045550100",
        "sender_name": "SMS Contact",
        "summary": "Meeting moved to Friday.",
        "created_at": "2026-05-15T10:00:00Z",
        "source_confidence": 0.42,
    }

    first = ingest_notification_summary(db_session, payload)
    second = ingest_notification_summary(db_session, payload)

    assert first.inserted_count == 1
    assert second.skipped_duplicate_count == 1
    message = db_session.query(Message).filter_by(source_message_id="notif-1").one()
    assert message.source_type == "notification_whatsapp"
    assert float(message.source_confidence) == 0.42
