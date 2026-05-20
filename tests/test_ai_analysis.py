from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.entities import (
    AttentionItem,
    Contact,
    DraftReply,
    Message,
    MessageClassification,
    MessageThread,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
    UserFeedback,
)
from app.services.analysis_service import (
    FallbackAIAnalysisProvider,
    OpenAIAnalysisProvider,
    analyze_message,
    build_analysis_context,
    build_analysis_prompt,
)
from app.services.feedback_service import apply_review_package_correction
from app.services.live_ai_client import AIProviderError
from app.services.draft_service import DraftContext, create_draft_reply


class CapturingProvider:
    name = "capture"

    def __init__(self) -> None:
        self.context: DraftContext | None = None

    def generate(self, context: DraftContext, voice_profile) -> str:
        self.context = context
        return "captured draft"


class FakeJsonClient:
    model = "test-model"

    def __init__(self, payload: dict | None = None, *, fail: bool = False) -> None:
        self.payload = payload or {}
        self.fail = fail
        self.system_prompt = ""
        self.user_prompt = ""

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        if self.fail:
            raise AIProviderError("simulated failure")
        return self.payload


def test_prompt_quality_fixture_examples_produce_specific_actions(db_session):
    fixture_path = Path(__file__).parent / "fixtures" / "prompt_quality_cases.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    for case in cases:
        contact_id = None
        relationship = case.get("relationship_type")
        if relationship:
            contact = Contact(
                display_name="Client Contact",
                primary_email=case["messages"][-1]["sender_email"],
                relationship_type=relationship,
                importance_tier=4,
            )
            db_session.add(contact)
            db_session.flush()
            contact_id = contact.id
        _, selected = _seed_thread(
            db_session,
            case["messages"],
            subject=f"{case['subject']} {case['name']}",
            contact_id=contact_id,
            classification_kwargs=case.get("classification"),
        )

        result = analyze_message(db_session, selected)
        action = result.review_package.action_type.value

        if "expected_action" in case:
            assert action == case["expected_action"], case["name"]
        else:
            assert action in case["expected_action_any"], case["name"]
        if case.get("expected_due_date"):
            assert result.conversation_summary.detected_due_date == case["expected_due_date"]
        if case.get("expected_text"):
            combined = " ".join(
                [
                    result.conversation_summary.summary_text,
                    result.review_package.explanation,
                    result.review_package.draft_response or "",
                ]
            ).lower()
            assert case["expected_text"].lower() in combined
        for term in case.get("forbidden_draft_terms", []):
            assert term.lower() not in (result.review_package.draft_response or "").lower()


def test_dinner_cancellation_acknowledgement_needs_no_response(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Christian",
                "sender_email": "christian@example.com",
                "body_text": "I need to cancel dinner tonight. Sorry for the late notice.",
            },
            {
                "sender_display_name": "Michael",
                "sender_email": "michael@example.com",
                "body_text": "No worries, thanks for the heads up! <3",
            },
        ],
        subject="Dinner tonight",
    )

    result = analyze_message(db_session, selected)

    assert result.review_package.action_type == ProposedActionType.NO_RESPONSE_NEEDED
    assert result.conversation_summary.summary_text == "Michael acknowledged Christian's cancellation."
    assert (
        "Michael is only acknowledging Christian's cancellation"
        in result.review_package.explanation
    )
    assert "does not ask Rohan for anything" in result.review_package.explanation
    assert result.review_package.draft_response is None
    assert db_session.query(DraftReply).count() == 0


def test_icbc_renewal_creates_local_calendar_reminder_candidate(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "ICBC",
                "sender_email": "renewals@icbc.example",
                "body_text": "Your vehicle registration renewal is due on 2026-06-12.",
            }
        ],
        subject="ICBC renewal notice",
    )

    result = analyze_message(db_session, selected)

    assert result.review_package.action_type == ProposedActionType.CREATE_CALENDAR_REMINDER
    assert "2026-06-12" in result.conversation_summary.summary_text
    assert result.conversation_summary.detected_due_date == "2026-06-12"
    assert "before the due date" in result.review_package.explanation
    assert "Reminder candidate" in result.conversation_summary.summary_text
    assert result.review_package.is_external_action is False


def test_newsletter_recommends_noise_or_unsubscribe_with_evidence(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Marketing List",
                "sender_email": "news@example.com",
                "body_text": (
                    "Weekly newsletter: limited time promotion. "
                    "Click unsubscribe to stop receiving these emails."
                ),
            }
        ],
        subject="Weekly deals",
        classification_kwargs={"is_newsletter": True, "is_marketing": True},
    )

    result = analyze_message(db_session, selected)

    assert result.review_package.action_type in {
        ProposedActionType.MARK_NOISE,
        ProposedActionType.UNSUBSCRIBE_REVIEW,
    }
    assert "Evidence:" in result.review_package.explanation
    assert "unsubscribe" in result.review_package.explanation.lower()


def test_client_request_recommends_specific_reply_candidate(db_session):
    contact = Contact(
        display_name="Client Contact",
        primary_email="client@example.com",
        relationship_type="client",
        importance_tier=4,
    )
    db_session.add(contact)
    db_session.flush()
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Can you send the revised proposal by Friday?",
            }
        ],
        subject="Revised proposal",
        contact_id=contact.id,
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )

    result = analyze_message(db_session, selected)

    assert result.review_package.action_type == ProposedActionType.REPLY
    assert "revised proposal by Friday" in result.review_package.draft_response
    assert "generic" not in result.review_package.draft_response.lower()


def test_vague_message_asks_clarifying_question(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Someone",
                "sender_email": "person@example.com",
                "body_text": "Can we talk? Need your input.",
            }
        ],
        subject="Question",
    )

    result = analyze_message(db_session, selected)

    assert result.review_package.action_type == ProposedActionType.ASK_CLARIFYING_QUESTION
    assert result.review_package.draft_response is not None


def test_draft_context_uses_review_package_summary_action_and_thread(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "The full thread says the deliverable is a budget forecast.",
            }
        ],
        subject="Budget forecast",
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )
    db_session.add(
        UserFeedback(
            message_id=selected.id,
            feedback_type="classification_correction",
            corrected_label="needs_reply",
        )
    )
    db_session.commit()
    analyze_message(db_session, selected)
    provider = CapturingProvider()

    create_draft_reply(db_session, selected, provider=provider)

    assert provider.context is not None
    assert "budget forecast" in provider.context.conversation_summary.lower()
    assert provider.context.proposed_action_type == "reply"
    assert "full thread says" in provider.context.full_thread_context
    assert "classification_correction: needs_reply" in provider.context.feedback_summary


def test_analysis_prompt_includes_required_context(db_session):
    contact = Contact(
        display_name="Client Contact",
        primary_email="client@example.com",
        relationship_type="client",
        importance_tier=4,
    )
    db_session.add(contact)
    db_session.flush()
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Can you help with the access issue?",
                "recipient_emails": "rohan@example.com",
            }
        ],
        subject="Access issue",
        contact_id=contact.id,
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )

    context = build_analysis_context(db_session, selected)
    system_prompt, user_prompt = build_analysis_prompt(context)

    assert "Return only a JSON object" in system_prompt
    assert "Known proposed action types" in user_prompt
    assert "Full conversation timeline" in user_prompt
    assert "Selected message" in user_prompt
    assert "relationship: client" in user_prompt
    assert "To: rohan@example.com" in user_prompt
    assert "avoid generic filler" in system_prompt.lower()


def test_openai_analysis_provider_validates_structured_output(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Can you send the support checklist?",
            }
        ],
        subject="Support checklist",
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )
    client = FakeJsonClient(
        {
            "summary": "Client Contact asked for the support checklist.",
            "action_type": "reply",
            "explanation": "The selected message asks for a specific checklist.",
            "confidence": 0.86,
            "draft_response": "Hi Client Contact,\n\nI can send the support checklist today.\n\nBest",
            "detected_due_date": None,
            "caveats": [],
        }
    )

    result = analyze_message(db_session, selected, provider=OpenAIAnalysisProvider(client=client))

    assert result.review_package.provider_name == "openai:test-model"
    assert result.review_package.action_type == ProposedActionType.REPLY
    assert "support checklist" in result.review_package.draft_response
    assert "support checklist" in client.user_prompt


def test_live_analysis_provider_falls_back_safely_on_failure(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Marketing List",
                "sender_email": "news@example.com",
                "body_text": "Newsletter promotion. Click unsubscribe.",
            }
        ],
        subject="Deals",
        classification_kwargs={"is_newsletter": True, "is_marketing": True},
    )
    provider = FallbackAIAnalysisProvider(OpenAIAnalysisProvider(client=FakeJsonClient(fail=True)))

    result = analyze_message(db_session, selected, provider=provider)

    assert result.review_package.provider_name == "openai:test-model->mock_fallback"
    assert result.review_package.action_type in {
        ProposedActionType.MARK_NOISE,
        ProposedActionType.UNSUBSCRIBE_REVIEW,
    }
    assert "mock fallback" in result.review_package.explanation


def test_review_package_web_flow_is_local_only(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Please send the support summary.",
            }
        ],
        subject="Support summary",
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(f"/messages/{selected.id}/analyze", follow_redirects=False)
            assert response.status_code == 303
            detail = client.get(response.headers["location"])
            assert detail.status_code == 200
            assert "Local recommendation only" in detail.text
            assert "does not modify Gmail or any calendar" in detail.text
            package = db_session.query(ProposedActionReviewPackage).one()
            status_response = client.post(
                f"/review-packages/{package.id}/status",
                data={"status": "approved", "user_note": "Looks right."},
                follow_redirects=False,
            )
    finally:
        app.dependency_overrides.clear()

    assert status_response.status_code == 303
    db_session.refresh(package)
    assert package.status == ReviewPackageStatus.APPROVED
    assert package.is_external_action is False


def test_review_package_correction_persists_and_updates_prompt_context(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Please send the support summary.",
            }
        ],
        subject="Support summary",
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )
    result = analyze_message(db_session, selected)

    correction = apply_review_package_correction(
        db_session,
        result.review_package.id,
        correction_type="does_not_need_reply",
        notes="Latest message was FYI only.",
    )

    assert correction.package.action_type == ProposedActionType.NO_RESPONSE_NEEDED
    assert correction.feedback.feedback_type == "review_package_does_not_need_reply"
    context = build_analysis_context(db_session, selected)
    assert "review_package_does_not_need_reply" in context.feedback_summary


def test_review_package_detail_renders_evidence_and_correction_controls(db_session):
    _, selected = _seed_thread(
        db_session,
        [
            {
                "sender_display_name": "Client Contact",
                "sender_email": "client@example.com",
                "body_text": "Can you send the revised proposal by Friday?",
            }
        ],
        subject="Proposal",
        classification_kwargs={"requires_reply": True, "is_client_work": True},
    )
    result = analyze_message(db_session, selected)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/review-packages/{result.review_package.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Recommendation Evidence" in response.text
    assert "Plain-language reason" in response.text
    assert "If prepared" in response.text
    assert "Teach This Recommendation" in response.text
    assert "Correct action type" in response.text
    assert "This does need reply" in response.text
    assert "Correct calendar interpretation" in response.text


def _seed_thread(
    db_session,
    messages: list[dict],
    *,
    subject: str,
    contact_id: int | None = None,
    classification_kwargs: dict | None = None,
) -> tuple[MessageThread, Message]:
    thread = MessageThread(
        source_type="gmail",
        source_thread_id=f"thread-{subject}",
        normalized_subject=subject,
        contact_id=contact_id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()

    created = []
    for index, payload in enumerate(messages, start=1):
        message = Message(
            thread_id=thread.id,
            source_type="gmail",
            source_message_id=f"{thread.source_thread_id}-{index}",
            subject=subject,
            snippet=payload.get("snippet") or payload.get("body_text"),
            sender_display_name=payload.get("sender_display_name"),
            sender_email=payload.get("sender_email"),
            recipient_emails=payload.get("recipient_emails"),
            cc_emails=payload.get("cc_emails"),
            body_text=payload.get("body_text"),
        )
        db_session.add(message)
        db_session.flush()
        created.append(message)

    selected = created[-1]
    kwargs = classification_kwargs or {}
    classification = MessageClassification(
        message_id=selected.id,
        confidence=Decimal("0.8000"),
        classification_reason="test fixture",
        **kwargs,
    )
    db_session.add(classification)
    db_session.add(
        AttentionItem(
            contact_id=contact_id,
            thread_id=thread.id,
            message_id=selected.id,
            attention_score=72,
            reason="test fixture",
            recommended_action="Review",
        )
    )
    db_session.commit()
    return thread, selected
