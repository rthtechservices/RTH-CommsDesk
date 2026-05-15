from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol

from app.core.config import get_settings
from app.models.entities import ProposedActionType


@dataclass(frozen=True)
class AvailabilityEvaluation:
    available: bool
    reason: str
    conflict_summary: str | None
    suggested_windows: tuple[tuple[datetime, datetime], ...]


@dataclass(frozen=True)
class CalendarRecommendation:
    action_kind: str
    action_type: ProposedActionType
    confidence: float
    availability_reasoning: str
    conflict_summary: str | None = None
    proposed_start_at: datetime | None = None
    proposed_end_at: datetime | None = None
    reminder_at: datetime | None = None
    available_windows: tuple[tuple[datetime, datetime], ...] = ()
    provider_name: str = "mock"


class CalendarAvailabilityProvider(Protocol):
    name: str

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:
        """Return availability for a requested window."""


class MockCalendarAvailabilityProvider:
    name = "mock"

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:
        weekday = start_at.weekday()
        if weekday in {1, 3} and start_at.hour in {18, 19}:
            suggestion_one_start = start_at + timedelta(days=1, hours=1)
            suggestion_one_end = suggestion_one_start + (end_at - start_at)
            suggestion_two_start = start_at + timedelta(days=2)
            suggestion_two_end = suggestion_two_start + (end_at - start_at)
            return AvailabilityEvaluation(
                available=False,
                reason="Requested time conflicts with an existing evening commitment.",
                conflict_summary="Existing event blocks the requested time window.",
                suggested_windows=(
                    (suggestion_one_start, suggestion_one_end),
                    (suggestion_two_start, suggestion_two_end),
                ),
            )
        return AvailabilityEvaluation(
            available=True,
            reason="Requested time appears free based on read-only calendar availability.",
            conflict_summary=None,
            suggested_windows=(),
        )


class GoogleReadOnlyCalendarProvider:
    name = "google-readonly"

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:  # pragma: no cover
        return AvailabilityEvaluation(
            available=True,
            reason="Google Calendar read-only provider is not configured; using optimistic availability.",
            conflict_summary=None,
            suggested_windows=(),
        )


class OutlookReadOnlyCalendarProvider:
    name = "outlook-readonly"

    def evaluate(self, start_at: datetime, end_at: datetime) -> AvailabilityEvaluation:  # pragma: no cover
        return AvailabilityEvaluation(
            available=True,
            reason="Outlook Calendar read-only provider is not configured; using optimistic availability.",
            conflict_summary=None,
            suggested_windows=(),
        )


def get_default_calendar_provider(provider_name: str | None = None) -> CalendarAvailabilityProvider:
    configured = provider_name or get_settings().calendar_provider
    normalized = (configured or "mock").strip().lower()
    if normalized == "google":
        return GoogleReadOnlyCalendarProvider()
    if normalized == "outlook":
        return OutlookReadOnlyCalendarProvider()
    return MockCalendarAvailabilityProvider()


def build_calendar_recommendation(
    text: str,
    *,
    detected_due_date: str | None = None,
    provider: CalendarAvailabilityProvider | None = None,
    now: datetime | None = None,
) -> CalendarRecommendation | None:
    now = now or datetime.now(UTC)
    provider = provider or MockCalendarAvailabilityProvider()
    if detected_due_date:
        due_date = _parse_due_date(detected_due_date)
        if due_date:
            reminder_at = datetime.combine(due_date - timedelta(days=7), time(hour=9), tzinfo=UTC)
            return CalendarRecommendation(
                action_kind="create_reminder",
                action_type=ProposedActionType.CREATE_CALENDAR_REMINDER,
                confidence=0.9,
                availability_reasoning=(
                    f"Detected due date {due_date.isoformat()}. Recommend a reminder one week earlier."
                ),
                reminder_at=reminder_at,
                provider_name=provider.name,
            )

    proposal = _extract_meeting_proposal(text, now=now)
    if not proposal:
        return None
    if proposal[0] is None or proposal[1] is None:
        return CalendarRecommendation(
            action_kind="ask_for_time_clarification",
            action_type=ProposedActionType.ASK_CLARIFYING_QUESTION,
            confidence=0.72,
            availability_reasoning=(
                "Detected a scheduling request but the time window is incomplete or ambiguous."
            ),
            provider_name=provider.name,
        )
    start_at, end_at = proposal
    evaluation = provider.evaluate(start_at, end_at)
    if evaluation.available:
        action_kind = "offer_availability" if _looks_like_offer_availability(text) else "create_meeting"
        action_type = (
            ProposedActionType.REPLY
            if action_kind == "offer_availability"
            else ProposedActionType.SCHEDULE_MEETING
        )
        return CalendarRecommendation(
            action_kind=action_kind,
            action_type=action_type,
            confidence=0.83,
            availability_reasoning=evaluation.reason,
            proposed_start_at=start_at,
            proposed_end_at=end_at,
            provider_name=provider.name,
        )
    return CalendarRecommendation(
        action_kind="ask_for_time_clarification",
        action_type=ProposedActionType.ASK_CLARIFYING_QUESTION,
        confidence=0.79,
        availability_reasoning=evaluation.reason,
        conflict_summary=evaluation.conflict_summary,
        proposed_start_at=start_at,
        proposed_end_at=end_at,
        available_windows=evaluation.suggested_windows,
        provider_name=provider.name,
    )


def _looks_like_offer_availability(text: str) -> bool:
    normalized = text.lower()
    return any(
        token in normalized
        for token in (
            "are you free",
            "are you available",
            "can we meet",
            "does tuesday",
            "does thursday",
            "what time works",
        )
    )


def _extract_meeting_proposal(text: str, *, now: datetime) -> tuple[datetime | None, datetime | None] | None:
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()
    if not normalized:
        return None
    if not any(token in normalized for token in ("meet", "call", "schedule", "available", "free")):
        return None

    day_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    day_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", normalized)
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", normalized)
    evening_match = "evening" in normalized
    if not day_match:
        return None
    target_weekday = day_map[day_match.group(1)]
    day_delta = (target_weekday - now.weekday()) % 7
    day_delta = day_delta or 7
    meeting_date = (now + timedelta(days=day_delta)).date()
    if time_match:
        hour = int(time_match.group(1)) % 12
        minute = int(time_match.group(2) or 0)
        if time_match.group(3) == "pm":
            hour += 12
        start = datetime.combine(meeting_date, time(hour=hour, minute=minute), tzinfo=UTC)
        return start, start + timedelta(hours=1)
    if evening_match:
        start = datetime.combine(meeting_date, time(hour=18), tzinfo=UTC)
        return start, start + timedelta(hours=2)
    return None, None


def _parse_due_date(value: str) -> datetime.date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d", "%b %d, %Y", "%b %d"):
        try:
            parsed = datetime.strptime(value, fmt)
            if "%Y" not in fmt:
                return parsed.replace(year=datetime.now(UTC).year).date()
            return parsed.date()
        except ValueError:
            continue
    return None
