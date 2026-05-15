from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.connectors.base import NormalizedMessage
from app.models.entities import (
    Contact,
    InferenceStatus,
    Message,
    MessageClassification,
    MessageThread,
    SentMailLearningRecord,
    UserFeedback,
    VoiceGuidance,
    VoiceProfile,
    VipInferenceCandidate,
)
from app.services.draft_service import create_draft_reply
from app.services.voice_learning_service import run_sent_mail_learning, update_voice_guidance_status


class FakeSentConnector:
    def __init__(self, messages: list[NormalizedMessage]) -> None:
        self.messages = messages

    def fetch_sent_messages(self, limit: int = 100, include_body: bool = True) -> list[NormalizedMessage]:
        return self.messages[:limit]


def test_sent_mail_learning_infers_vip_candidates_and_salutation(db_session):
    michael = Contact(
        display_name="Michael Frolick",
        primary_email="michael@example.com",
        relationship_type="friend",
        importance_tier=3,
    )
    db_session.add(michael)
    db_session.flush()
    db_session.add(
        UserFeedback(
            contact_id=michael.id,
            feedback_type="classification_correction",
            corrected_label="important",
        )
    )
    db_session.commit()

    sent_messages = [
        NormalizedMessage(
            source_type="gmail",
            source_message_id=f"sent-{index}",
            source_thread_id="thread-friend",
            sender_display_name="Rohan",
            sender_email="rohan@example.com",
            recipient_emails=["michael@example.com"],
            cc_emails=[],
            received_at=datetime.now(UTC) - timedelta(days=index),
            subject="Re: Dinner plans",
            snippet="Hey Mike, sounds good.",
            body_text="Hey Mike,\n\nSounds good. Let's keep it simple.\n\nThanks",
            has_attachments=False,
            is_unread=False,
        )
        for index in range(1, 6)
    ]
    connector = FakeSentConnector(sent_messages)

    result = run_sent_mail_learning(db_session, connector=connector)

    assert result.fetched_count == 5
    assert db_session.query(SentMailLearningRecord).count() == 5
    candidate = (
        db_session.query(VipInferenceCandidate)
        .join(Contact, VipInferenceCandidate.contact_id == Contact.id)
        .filter(Contact.primary_email == "michael@example.com")
        .one()
    )
    assert candidate.score > 40
    guidance = (
        db_session.query(VoiceGuidance)
        .filter(VoiceGuidance.contact_id == michael.id)
        .order_by(VoiceGuidance.updated_at.desc())
        .first()
    )
    assert guidance is not None
    assert guidance.salutation_style in {"first_name", "nickname"}
    assert guidance.preferred_name == "Mike"
    assert "avoid corporate filler" in (guidance.tone_notes or "")


def test_approved_friend_guidance_is_used_in_generated_drafts(db_session):
    contact = Contact(
        display_name="Michael Frolick",
        primary_email="michael@example.com",
        relationship_type="friend",
        importance_tier=3,
    )
    db_session.add(contact)
    db_session.flush()
    guidance = VoiceGuidance(
        contact_id=contact.id,
        relationship_type="friend",
        salutation_style="first_name",
        preferred_name="Mike",
        tone_notes="casual, warm, concise; avoid corporate filler",
        status=InferenceStatus.PENDING,
    )
    db_session.add(guidance)
    db_session.flush()
    update_voice_guidance_status(
        db_session,
        guidance.id,
        status=InferenceStatus.APPROVED,
        salutation_style="first_name",
        preferred_name="Mike",
        tone_notes="casual, warm, concise; avoid corporate filler",
    )
    thread = MessageThread(
        source_type="gmail",
        source_thread_id="friend-thread",
        contact_id=contact.id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="friend-message",
        sender_display_name="Michael Frolick",
        sender_email="michael@example.com",
        subject="Dinner update",
        snippet="No worries, thanks for the heads up.",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            requires_reply=True,
            is_human_personal=True,
            classification_reason="test",
        )
    )
    voice = VoiceProfile(name="Friend Voice Test", audience_type="friend")
    db_session.add(voice)
    db_session.commit()

    draft = create_draft_reply(db_session, message, voice_profile_id=voice.id)

    assert "Hey Mike," in draft.draft_text
    assert "I wanted to acknowledge this directly" not in draft.draft_text


def test_approved_client_guidance_uses_formal_salutation(db_session):
    contact = Contact(
        display_name="Jordan Client",
        primary_email="jordan@client.example",
        relationship_type="client",
        importance_tier=4,
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add(
        VoiceGuidance(
            contact_id=contact.id,
            relationship_type="client",
            salutation_style="formal",
            preferred_name="Jordan Client",
            tone_notes="concise, professional, clear next steps",
            status=InferenceStatus.APPROVED,
            is_active=True,
        )
    )
    thread = MessageThread(
        source_type="gmail",
        source_thread_id="client-thread",
        contact_id=contact.id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="client-message",
        sender_display_name="Jordan Client",
        sender_email="jordan@client.example",
        subject="Proposal request",
        snippet="Can you send the revised proposal?",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            requires_reply=True,
            is_client_work=True,
            classification_reason="test",
        )
    )
    voice = VoiceProfile(name="Client Voice Test", audience_type="client")
    db_session.add(voice)
    db_session.commit()

    draft = create_draft_reply(db_session, message, voice_profile_id=voice.id)

    assert "Dear Jordan Client," in draft.draft_text
