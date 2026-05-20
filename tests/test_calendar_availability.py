from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    assert "do not see a time" in result.review_package.draft_response.lower()
    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.action_kind == "tentative_all_day_meeting"
    assert proposal.proposed_start_at is not None
    assert proposal.proposed_start_at.hour == 0
    assert proposal.proposed_end_at is not None
    assert proposal.proposed_end_at - proposal.proposed_start_at == timedelta(days=1)


def test_date_only_meeting_request_does_not_invent_timed_reminder(db_session):
    selected = _seed_single_message(
        db_session,
        subject="Project sync",
        body_text="Can we meet Friday to go over the project?",
        received_at=datetime(2026, 5, 19, 16, 0, tzinfo=UTC),
    )

    result = analyze_message(db_session, selected, calendar_provider=AlwaysFreeProvider())

    assert result.review_package.action_type == ProposedActionType.ASK_CLARIFYING_QUESTION
    assert "what time" in (result.review_package.draft_response or "").lower()
    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.action_kind == "tentative_all_day_meeting"
    assert proposal.reminder_at is None
    assert proposal.proposed_start_at.replace(tzinfo=UTC) == datetime(2026, 5, 22, 0, 0, tzinfo=UTC)
    assert proposal.proposed_end_at.replace(tzinfo=UTC) == datetime(2026, 5, 23, 0, 0, tzinfo=UTC)


def test_relative_this_coming_friday_uses_received_date_and_not_past(db_session):
    selected = _seed_single_message(
        db_session,
        subject="Coffee chat",
        body_text="Are you free this coming Friday at 2 pm to chat?",
        received_at=datetime(2026, 5, 22, 9, 0, tzinfo=UTC),
    )

    result = analyze_message(db_session, selected, calendar_provider=AlwaysFreeProvider())

    proposal = db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).one()
    assert proposal.proposed_start_at.replace(tzinfo=UTC) == datetime(2026, 5, 29, 14, 0, tzinfo=UTC)
    assert proposal.proposed_start_at.replace(tzinfo=UTC) > selected.received_at.replace(tzinfo=UTC)


def test_past_due_date_does_not_generate_past_calendar_candidate(db_session):
    selected = _seed_single_message(
        db_session,
        subject="Old renewal",
        body_text="Your insurance renewal is due on 2026-05-01.",
        received_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )

    result = analyze_message(db_session, selected, calendar_provider=AlwaysFreeProvider())

    assert result.review_package.action_type != ProposedActionType.CREATE_CALENDAR_REMINDER
    assert db_session.query(CalendarActionProposal).filter_by(review_package_id=result.review_package.id).count() == 0


def _seed_single_message(
    db_session,
    *,
    subject: str,
    body_text: str,
    received_at: datetime | None = None,
) -> Message:
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
        received_at=received_at or datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
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
