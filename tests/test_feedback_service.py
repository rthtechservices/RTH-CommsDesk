from datetime import UTC, datetime

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
    UserFeedback,
)
from app.services.attention_service import upsert_attention_item
from app.services.feedback_service import apply_message_correction


def _seed_message(db_session, *, sender_email="sender@example.com", newsletter=False):
    contact = Contact(display_name="Sender", primary_email=sender_email, importance_tier=1)
    db_session.add(contact)
    db_session.flush()

    thread = MessageThread(
        source_type="gmail",
        source_thread_id=f"thread-{sender_email}",
        contact_id=contact.id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()

    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id=f"msg-{sender_email}",
        sender_display_name="Sender",
        sender_email=sender_email,
        received_at=datetime.now(UTC),
        subject="General update",
        snippet="Here is an update",
        is_unread=True,
    )
    db_session.add(message)
    db_session.flush()

    classification = MessageClassification(
        message_id=message.id,
        requires_reply=False,
        urgency_level=0,
        is_human_personal=not newsletter,
        is_client_work=False,
        is_marketing=newsletter,
        is_newsletter=newsletter,
        is_receipt=False,
        is_group_noise=newsletter,
        is_system_notification=False,
        classification_reason="initial",
    )
    db_session.add(classification)
    db_session.flush()

    item = upsert_attention_item(db_session, contact, thread, message, classification)
    db_session.commit()
    return contact, thread, message, classification, item


def test_correcting_message_as_important_increases_score(db_session):
    _, _, message, _, item = _seed_message(db_session, newsletter=True)
    before = item.attention_score

    result = apply_message_correction(
        db_session, message.id, corrected_label="important", corrected_importance=3
    )

    assert result.attention_item.attention_score > before
    assert result.classification.urgency_level == 3
    assert result.classification.is_newsletter is False


def test_correcting_message_as_needs_reply_sets_reply_action(db_session):
    _, _, message, _, _ = _seed_message(db_session)

    result = apply_message_correction(db_session, message.id, corrected_label="needs_reply")

    assert result.classification.requires_reply is True
    assert result.attention_item.recommended_action == "Reply"


def test_correcting_message_as_noise_lowers_and_dismisses_item(db_session):
    _, _, message, _, item = _seed_message(db_session)
    before = item.attention_score

    result = apply_message_correction(db_session, message.id, corrected_label="noise")

    assert result.attention_item.attention_score < before
    assert result.attention_item.status == AttentionStatus.DISMISSED
    assert result.classification.is_group_noise is True


def test_structured_feedback_persists(db_session):
    _, _, message, _, _ = _seed_message(db_session)

    apply_message_correction(
        db_session,
        message.id,
        corrected_label="client_work",
        corrected_importance=2,
        notes="This is a real client thread.",
    )

    feedback = db_session.query(UserFeedback).one()
    assert feedback.message_id == message.id
    assert feedback.corrected_label == "client_work"
    assert feedback.corrected_importance == 2
    assert feedback.corrected_is_client_work is True
    assert feedback.feedback_text == "This is a real client thread."
