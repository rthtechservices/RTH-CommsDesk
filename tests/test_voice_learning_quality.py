from __future__ import annotations

from datetime import UTC, datetime

from app.models.entities import Contact, InferenceStatus, SentMailLearningRecord
from app.services.voice_learning_service import infer_voice_guidance, update_voice_guidance_status


def test_sent_mail_learning_infers_recurring_operator_signoff(db_session):
    contact = Contact(
        display_name="Client",
        primary_email="client@example.com",
        relationship_type="client",
        importance_tier=4,
    )
    db_session.add(contact)
    db_session.flush()
    for index in range(3):
        db_session.add(
            SentMailLearningRecord(
                source_type="gmail",
                source_message_id=f"sent-{index}",
                contact_id=contact.id,
                recipient_email="client@example.com",
                sent_at=datetime(2026, 5, 10 + index, 10, 0, tzinfo=UTC),
                body_excerpt=(
                    "Hi Alex,\n\n"
                    "I will take care of this and follow up with the next step.\n\n"
                    "Cheers,\n"
                    "Rohan."
                ),
                is_reply=True,
            )
        )
    db_session.commit()

    infer_voice_guidance(db_session)

    global_guidance = _global_guidance(db_session)
    assert global_guidance is not None
    assert "preferred sign-off: Cheers,\nRohan." in (global_guidance.tone_notes or "")
    assert global_guidance.status == InferenceStatus.PENDING

    update_voice_guidance_status(
        db_session,
        global_guidance.id,
        status=InferenceStatus.APPROVED,
        tone_notes=global_guidance.tone_notes,
    )
    db_session.refresh(global_guidance)

    assert global_guidance.is_active is True


def _global_guidance(db_session):
    from app.models.entities import VoiceGuidance

    return (
        db_session.query(VoiceGuidance)
        .filter_by(contact_id=None, relationship_type="global_operator")
        .one_or_none()
    )
