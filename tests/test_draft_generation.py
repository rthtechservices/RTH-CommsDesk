from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.entities import (
    AttentionItem,
    Contact,
    DraftReply,
    DraftStatus,
    InferenceStatus,
    Message,
    MessageClassification,
    MessageThread,
    UserFeedback,
    VoiceGuidance,
    VoiceProfile,
)
from app.services.draft_service import (
    FallbackDraftProvider,
    OpenAIDraftProvider,
    DraftContext,
    build_draft_context,
    build_draft_prompt,
    create_draft_reply,
)
from app.services.live_ai_client import AIProviderError


class CapturingDraftProvider:
    name = "capture"

    def __init__(self) -> None:
        self.context: DraftContext | None = None
        self.voice_profile: VoiceProfile | None = None

    def generate(self, context: DraftContext, voice_profile: VoiceProfile) -> str:
        self.context = context
        self.voice_profile = voice_profile
        return f"Review-only generated for {voice_profile.audience_type}: {context.subject}"


class FakeDraftJsonClient:
    model = "test-model"

    def __init__(self, payload: dict | None = None, *, fail: bool = False) -> None:
        self.payload = payload or {}
        self.fail = fail
        self.user_prompt = ""

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.user_prompt = user_prompt
        if self.fail:
            raise AIProviderError("simulated failure")
        return self.payload


def test_mock_draft_provider_uses_selected_voice_profile(db_session):
    message, client_voice, friend_voice = _seed_message_with_profiles(db_session)

    client_draft = create_draft_reply(db_session, message, voice_profile_id=client_voice.id)
    friend_draft = create_draft_reply(db_session, message, voice_profile_id=friend_voice.id)

    assert client_draft.status == DraftStatus.GENERATED
    assert client_draft.message_id == message.id
    assert client_draft.thread_id == message.thread_id
    assert client_draft.voice_profile_id == client_voice.id
    assert "Review-only draft suggestion" in client_draft.draft_text
    assert "clear next steps" in client_draft.draft_text
    assert client_draft.provider_name == "mock"

    assert friend_draft.voice_profile_id == friend_voice.id
    assert "Hey Client Contact" in friend_draft.draft_text
    assert friend_draft.draft_text != client_draft.draft_text


def test_draft_context_includes_message_contact_scoring_and_feedback(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)
    provider = CapturingDraftProvider()

    draft = create_draft_reply(
        db_session,
        message,
        voice_profile_id=client_voice.id,
        provider=provider,
    )

    assert draft.draft_text == "Review-only generated for client: Contract question"
    assert draft.provider_name == "capture"
    assert provider.context is not None
    assert provider.context.subject == "Contract question"
    assert provider.context.sender_email == "client@example.com"
    assert provider.context.contact_relationship == "client"
    assert provider.context.contact_importance_tier == 4
    assert provider.context.contact_state == "vip"
    assert provider.context.classification_label == "Needs reply"
    assert provider.context.attention_score == 82
    assert provider.context.attention_reason == "User corrected classification to needs_reply"
    assert provider.context.recommended_action == "Reply"
    assert "classification_correction: needs_reply" in provider.context.feedback_summary
    assert "Private full body" not in provider.context.feedback_summary


def test_mock_provider_supports_required_voice_profiles(db_session):
    message, client_voice, friend_voice = _seed_message_with_profiles(db_session)
    partner_voice = VoiceProfile(name="Partner Voice Test", audience_type="partner")
    vendor_voice = VoiceProfile(name="Vendor Voice Test", audience_type="vendor")
    short_voice = VoiceProfile(
        name="Short Acknowledgement Test", audience_type="short_acknowledgement"
    )
    db_session.add_all([partner_voice, vendor_voice, short_voice])
    db_session.commit()

    expected_phrases = [
        (client_voice, "clear next steps"),
        (friend_voice, "Hey Client Contact"),
        (partner_voice, "I hear you"),
        (vendor_voice, "Please keep this thread updated"),
        (short_voice, "Received, thank you"),
    ]
    for voice, expected_phrase in expected_phrases:
        draft = create_draft_reply(db_session, message, voice_profile_id=voice.id)
        assert expected_phrase in draft.draft_text
        assert "not been sent" in draft.draft_text


def test_web_generate_draft_redirects_to_local_review_page(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/messages/{message.id}/generate-draft",
                data={"voice_profile_id": str(client_voice.id)},
                follow_redirects=False,
            )
            assert response.status_code == 303
            assert "/drafts/" in response.headers["location"]

            review_response = client.get(response.headers["location"])
    finally:
        app.dependency_overrides.clear()

    assert review_response.status_code == 200
    assert "Review-only local suggestion" in review_response.text
    assert "was not created in Gmail" in review_response.text
    assert "Prepare external Gmail draft execution" in review_response.text
    assert "Provider" in review_response.text
    assert db_session.query(DraftReply).count() == 1


def test_live_draft_prompt_and_provider_name_are_review_only(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)
    context = build_draft_context(db_session, message)
    system_prompt, user_prompt = build_draft_prompt(context, client_voice)

    assert "Return only a JSON object" in system_prompt
    assert "Full conversation timeline" in user_prompt
    assert "Approved voice guidance" in user_prompt
    assert "Private full body should not be used by draft context" in user_prompt

    client = FakeDraftJsonClient(
        {
            "draft_body": (
                "Hi Client Contact,\n\nI can confirm the next step after reviewing the contract "
                "question.\n\nBest"
            ),
            "caveats": [],
        }
    )
    draft = create_draft_reply(
        db_session,
        message,
        voice_profile_id=client_voice.id,
        provider=OpenAIDraftProvider(client=client),
    )

    assert draft.provider_name == "openai:test-model"
    assert "Review-only draft suggestion" in draft.draft_text
    assert "contract question" in draft.draft_text.lower()


def test_live_draft_provider_falls_back_safely(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)
    provider = FallbackDraftProvider(OpenAIDraftProvider(client=FakeDraftJsonClient(fail=True)))

    draft = create_draft_reply(
        db_session,
        message,
        voice_profile_id=client_voice.id,
        provider=provider,
    )

    assert draft.provider_name == "openai:test-model->mock_fallback"
    assert "mock fallback generated" in draft.draft_text
    assert "Review-only draft suggestion" in draft.draft_text


def test_approved_global_signoff_guidance_is_applied_to_send_ready_draft(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)
    db_session.add(
        VoiceGuidance(
            contact_id=None,
            relationship_type="global_operator",
            tone_notes="concise, professional; preferred sign-off: Cheers,\nRohan.",
            evidence_excerpt="Cheers, Rohan. appears repeatedly in sent mail.",
            status=InferenceStatus.APPROVED,
            is_active=True,
            source="global_sent_inference",
        )
    )
    db_session.commit()

    draft = create_draft_reply(db_session, message, voice_profile_id=client_voice.id)

    assert "Cheers,\nRohan." in draft.send_ready_body
    assert "Best regards" not in draft.send_ready_body
    assert "[Your Name]" not in draft.send_ready_body


def test_generic_placeholders_are_removed_from_live_draft_output(db_session):
    message, client_voice, _ = _seed_message_with_profiles(db_session)
    client = FakeDraftJsonClient(
        {
            "draft_body": (
                "Hi Client Contact,\n\nI can handle this.\n\nBest regards,\n[Your Name]"
            ),
            "caveats": [],
        }
    )

    draft = create_draft_reply(
        db_session,
        message,
        voice_profile_id=client_voice.id,
        provider=OpenAIDraftProvider(client=client),
    )

    assert "[Your Name]" not in draft.send_ready_body
    assert "[signature]" not in draft.send_ready_body
    assert "Hi Client Contact" in draft.send_ready_body


def _seed_message_with_profiles(db_session):
    contact = Contact(
        display_name="Client Contact",
        primary_email="client@example.com",
        relationship_type="client",
        importance_tier=4,
        is_vip=True,
    )
    db_session.add(contact)
    db_session.flush()

    thread = MessageThread(
        source_type="gmail",
        source_thread_id="draft-thread",
        contact_id=contact.id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()

    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="draft-message",
        sender_display_name="Client Contact",
        sender_email="client@example.com",
        subject="Contract question",
        snippet="Can you confirm the next step?",
        body_text="Private full body should not be used by draft context.",
    )
    db_session.add(message)
    db_session.flush()

    classification = MessageClassification(
        message_id=message.id,
        requires_reply=True,
        urgency_level=2,
        is_client_work=True,
        classification_reason="User corrected classification to needs_reply",
    )
    db_session.add(classification)
    db_session.add(
        AttentionItem(
            contact_id=contact.id,
            thread_id=thread.id,
            message_id=message.id,
            attention_score=82,
            reason="User corrected classification to needs_reply",
            recommended_action="Reply",
        )
    )
    db_session.add(
        UserFeedback(
            message_id=message.id,
            contact_id=contact.id,
            feedback_type="classification_correction",
            corrected_label="needs_reply",
            feedback_text="Private full body should stay out of generated context.",
        )
    )

    client_voice = VoiceProfile(
        name="Client Voice Test",
        audience_type="client",
        tone_description="direct and clear",
        signoff_style="clear next steps",
    )
    friend_voice = VoiceProfile(
        name="Friend Voice Test",
        audience_type="friend",
        tone_description="warm and casual",
    )
    db_session.add_all([client_voice, friend_voice])
    db_session.commit()
    return message, client_voice, friend_voice
