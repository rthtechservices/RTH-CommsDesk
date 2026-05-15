from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.connectors.base import NormalizedMessage
from app.core.database import get_db
from app.main import app
from app.models.entities import (
    AttentionItem,
    Contact,
    ContactAlias,
    Message,
    MessageClassification,
    MessageThread,
    UserFeedback,
)
from app.services.attention_service import calculate_attention_score, upsert_attention_item
from app.services.contact_service import (
    SUPPORTED_RELATIONSHIP_TYPES,
    contact_alias_emails,
    find_contact_by_sender_email,
    update_contact_profile,
)
from app.services.gmail_sync_service import sync_gmail_messages


class FakeSettings:
    gmail_read_max_results = 10
    gmail_account = "me"


class FakeConnector:
    def fetch_recent_messages(self, limit: int = 100, since=None):
        return [
            NormalizedMessage(
                source_type="gmail",
                source_message_id="alias-m1",
                source_thread_id="alias-t1",
                sender_display_name="Work Alias",
                sender_email="alias@example.com",
                received_at=datetime(2026, 2, 1, tzinfo=UTC),
                subject="Client update",
                snippet="Please review this when you can.",
                body_text=None,
                has_attachments=False,
                is_unread=True,
            )
        ]


def _seed_attention_message(db_session, *, sender_email: str):
    thread = MessageThread(source_type="gmail", source_thread_id=f"thread-{sender_email}")
    db_session.add(thread)
    db_session.flush()

    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id=f"msg-{sender_email}",
        sender_email=sender_email,
        received_at=datetime.now(UTC),
        subject="Profile recalculation",
        snippet="Please review",
        is_unread=True,
    )
    db_session.add(message)
    db_session.flush()

    classification = MessageClassification(
        message_id=message.id,
        requires_reply=True,
        urgency_level=1,
        is_human_personal=True,
        classification_reason="initial",
    )
    db_session.add(classification)
    db_session.flush()

    item = upsert_attention_item(db_session, None, thread, message, classification)
    db_session.commit()
    return thread, message, classification, item


def test_supported_relationship_types_affect_scoring_predictably():
    thread = MessageThread(source_type="gmail", source_thread_id="rel", unread_count=1)
    message = Message(
        source_type="gmail",
        source_message_id="rel-msg",
        thread_id=1,
        received_at=datetime.now(UTC),
    )
    classification = MessageClassification(message_id=1, urgency_level=0)

    scores = {}
    for relationship in SUPPORTED_RELATIONSHIP_TYPES:
        contact = Contact(
            importance_tier=2,
            relationship_type=relationship,
            is_vip=False,
            is_noise=False,
        )
        scores[relationship] = calculate_attention_score(contact, thread, message, classification)

    assert scores["partner"] > scores["client"] > scores["prospect"] > scores["unknown"]
    assert scores["close_friend"] > scores["friend"]
    assert scores["newsletter"] < scores["unknown"]
    assert scores["system"] < scores["unknown"]


def test_alias_lookup_reuses_existing_contact_during_sync(db_session, monkeypatch):
    contact = Contact(
        display_name="Primary Person",
        primary_email="primary@example.com",
        relationship_type="client",
        importance_tier=4,
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add(
        ContactAlias(
            contact_id=contact.id,
            source_system="manual",
            source_identifier="alias@example.com",
            email="alias@example.com",
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.services.gmail_sync_service.get_settings", lambda: FakeSettings())

    sync_gmail_messages(db_session, connector=FakeConnector())

    assert db_session.query(Contact).count() == 1
    message = db_session.query(Message).filter_by(source_message_id="alias-m1").one()
    item = db_session.query(AttentionItem).filter_by(message_id=message.id).one()
    assert message.thread.contact_id == contact.id
    assert item.contact_id == contact.id
    assert find_contact_by_sender_email(db_session, "ALIAS@example.com").id == contact.id


def test_contact_profile_update_recalculates_existing_alias_messages(db_session):
    contact = Contact(
        display_name="Important Person",
        primary_email="primary@example.com",
        relationship_type="unknown",
        importance_tier=1,
    )
    db_session.add(contact)
    db_session.flush()
    thread, _message, _classification, item = _seed_attention_message(
        db_session, sender_email="alias@example.com"
    )
    before = item.attention_score

    updated = update_contact_profile(
        db_session,
        contact.id,
        display_name="Important Person",
        primary_email="primary@example.com",
        aliases_text="alias@example.com",
        relationship_type="partner",
        importance_tier=5,
        preferred_channel="gmail",
        notes="High context relationship.",
        status="vip",
    )

    refreshed_item = db_session.get(AttentionItem, item.id)
    refreshed_thread = db_session.get(MessageThread, thread.id)
    assert refreshed_item.contact_id == updated.id
    assert refreshed_thread.contact_id == updated.id
    assert refreshed_item.attention_score > before
    assert contact_alias_emails(db_session, updated) == ["alias@example.com"]

    feedback = db_session.query(UserFeedback).filter_by(contact_id=updated.id).one()
    assert feedback.feedback_type == "contact_profile_update"
    assert "relationship=partner" in (feedback.corrected_value or "")


def test_contact_management_pages_render(db_session):
    contact = Contact(
        display_name="Managed Contact",
        primary_email="managed@example.com",
        relationship_type="friend",
        importance_tier=2,
    )
    db_session.add(contact)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            index_response = client.get("/contacts")
            detail_response = client.get(f"/contacts/{contact.id}")
    finally:
        app.dependency_overrides.clear()

    assert index_response.status_code == 200
    assert "Managed Contact" in index_response.text
    assert detail_response.status_code == 200
    assert "Edit Contact" in detail_response.text
