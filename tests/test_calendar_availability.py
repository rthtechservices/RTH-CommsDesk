from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.models.entities import (
    AttentionItem,
    CalendarActionProposal,
    Message,
    MessageClassification,
    MessageThread,
    ProposedActionType,
)
from app.services.analysis_service import analyze_message
from app.services.calendar_availability_service import AvailabilityEvaluation


class AlwaysFreeProvider:
    name = "always-free"

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:
        return AvailabilityEvaluation(
            available=True,
            reason="Calendar is free at the proposed time.",
            conflict_summary=None,
            suggested_windows=(),
        )


class ConflictProvider:
    name = "conflict-provider"

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:
        return AvailabilityEvaluation(
            available=False,
            reason="Requested time conflicts with another event.",
            conflict_summary="Overlap with existing calendar event.",
            suggested_windows=(
                (start_at + timedelta(days=1), end_at + timedelta(days=1)),
                (start_at + timedelta(days=2), end_at + timedelta(days=2)),
            ),
        )


def test_due_date_generates_reminder_calendar_proposal(db_session):
    selected = _seed_single_message(
        db_session,
        subject="ICBC renewal reminder",
        body_text="Your ICBC registration renewal is due on 2026-06-12.",
    )

    result = analyze_message(db_session, selected, calendar_provider=AlwaysFreeProvider())

    assert result.review_package.action_type == ProposedActionType.CREATE_CALENDAR_REMINDER
    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.action_kind == "create_reminder"
    assert proposal.reminder_at is not None
    assert "due date" in (proposal.availability_reasoning or "").lower()


def test_meeting_proposal_offers_availability_when_time_is_free(db_session):
    selected = _seed_single_message(
        db_session,
        subject="Dinner schedule",
        body_text="Can we meet Tuesday at 6 pm to go over this?",
    )

    result = analyze_message(db_session, selected, calendar_provider=AlwaysFreeProvider())

    assert result.review_package.action_type == ProposedActionType.REPLY
    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.action_kind == "offer_availability"
    assert proposal.proposed_start_at is not None
    assert "free" in (proposal.availability_reasoning or "").lower()


def test_meeting_conflict_recommends_time_clarification(db_session):
    selected = _seed_single_message(
        db_session,
        subject="Laptop help",
        body_text="Can we meet Thursday evening to look at my laptop?",
    )

    result = analyze_message(db_session, selected, calendar_provider=ConflictProvider())

    assert result.review_package.action_type == ProposedActionType.ASK_CLARIFYING_QUESTION
    assert result.review_package.draft_response is not None
    assert "conflict" in result.review_package.draft_response.lower()
    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.action_kind == "ask_for_time_clarification"
    assert proposal.conflict_summary is not None
    assert proposal.available_windows is not None


def _seed_single_message(db_session, *, subject: str, body_text: str) -> Message:
    thread = MessageThread(
        source_type="gmail",
        source_thread_id=f"calendar-thread-{subject}",
        normalized_subject=subject,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id=f"calendar-message-{subject}",
        subject=subject,
        snippet=body_text,
        body_text=body_text,
        sender_display_name="Friend",
        sender_email="friend@example.com",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            confidence=Decimal("0.8000"),
            classification_reason="test fixture",
            requires_reply=True,
            is_human_personal=True,
        )
    )
    db_session.add(
        AttentionItem(
            thread_id=thread.id,
            message_id=message.id,
            attention_score=60,
            reason="test fixture",
            recommended_action="Review",
        )
    )
    db_session.commit()
    return message
