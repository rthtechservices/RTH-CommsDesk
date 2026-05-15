from __future__ import annotations

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
from app.services.analysis_service import analyze_message
from app.services.draft_service import DraftContext, create_draft_reply


class CapturingProvider:
    name = "capture"

    def __init__(self) -> None:
        self.context: DraftContext | None = None

    def generate(self, context: DraftContext, voice_profile) -> str:
        self.context = context
        return "captured draft"


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
