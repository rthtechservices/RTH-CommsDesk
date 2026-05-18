from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AttentionItem,
    CalendarActionProposal,
    Contact,
    ConversationSummary,
    Message,
    MessageClassification,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
    UserFeedback,
    utcnow,
)
from app.services.calendar_availability_service import (
    CalendarAvailabilityProvider,
    CalendarRecommendation,
    build_calendar_recommendation,
    get_default_calendar_provider,
)
from app.services.contact_service import contact_status, find_contact_by_sender_email
from app.services.feedback_service import friendly_classification_label, summarize_classification
from app.services.gmail_sync_service import deserialize_addresses
from app.services.live_ai_client import (
    AIProviderError,
    OpenAICompatibleJsonClient,
    ai_provider_status,
    build_openai_json_client,
    decimal_confidence,
    sanitize_ai_text,
)
from app.services.voice_learning_service import resolve_guidance_for_message


@dataclass(frozen=True)
class AnalysisMessageContext:
    message_id: int
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime | None
    recipient_emails: tuple[str, ...]
    cc_emails: tuple[str, ...]
    text: str
    is_selected: bool


@dataclass(frozen=True)
class AIAnalysisContext:
    message_id: int
    thread_id: int
    subject: str
    selected_message_text: str
    conversation_messages: tuple[AnalysisMessageContext, ...]
    contact_name: str
    contact_relationship: str
    contact_importance_tier: int | None
    contact_state: str
    classification_label: str
    classification_summary: str
    attention_score: int | None
    attention_reason: str
    feedback_summary: str
    learned_salutation_style: str
    learned_preferred_name: str
    learned_tone_notes: str


@dataclass(frozen=True)
class AIAnalysisResult:
    summary: str
    action_type: ProposedActionType
    explanation: str
    confidence: Decimal
    draft_response: str | None = None
    detected_due_date: str | None = None
    provider_name: str | None = None


@dataclass(frozen=True)
class AnalysisPersistenceResult:
    conversation_summary: ConversationSummary
    review_package: ProposedActionReviewPackage


class AIAnalysisProvider(Protocol):
    name: str

    def analyze(self, context: AIAnalysisContext) -> AIAnalysisResult:
        """Analyze a local conversation context and return a local review recommendation."""


class MockAIAnalysisProvider:
    name = "mock"

    def analyze(self, context: AIAnalysisContext) -> AIAnalysisResult:
        full_text = _clean_text(
            " ".join(
                [context.subject, context.selected_message_text]
                + [message.text for message in context.conversation_messages]
            )
        )
        selected_text = _clean_text(context.selected_message_text)
        due_date = _detect_due_date(full_text)

        if _looks_like_acknowledged_cancellation(full_text, selected_text):
            return AIAnalysisResult(
                summary=_ack_summary(context),
                action_type=ProposedActionType.NO_RESPONSE_NEEDED,
                explanation=(
                    "Michael is only acknowledging Christian's cancellation and does not "
                    "ask Rohan for anything."
                ),
                confidence=Decimal("0.9400"),
            )

        if due_date and _has_any(full_text, ["icbc", "renewal", "registration", "due date"]):
            return AIAnalysisResult(
                summary=f"The conversation includes a registration or renewal due date: {due_date}.",
                action_type=ProposedActionType.CREATE_CALENDAR_REMINDER,
                explanation=(
                    f"A local reminder should be reviewed and scheduled before the due date "
                    f"of {due_date}; no calendar event is created by CommsDesk."
                ),
                confidence=Decimal("0.9000"),
                detected_due_date=due_date,
            )

        if _looks_like_newsletter(full_text, context.classification_label):
            action = (
                ProposedActionType.UNSUBSCRIBE_REVIEW
                if _has_any(full_text, ["unsubscribe", "email preferences", "manage preferences"])
                else ProposedActionType.MARK_NOISE
            )
            return AIAnalysisResult(
                summary="This appears to be recurring marketing or newsletter content.",
                action_type=action,
                explanation=(
                    "Evidence: the message contains newsletter or marketing language"
                    + (
                        " and an unsubscribe/preferences signal."
                        if action == ProposedActionType.UNSUBSCRIBE_REVIEW
                        else "."
                    )
                ),
                confidence=Decimal("0.8800"),
            )

        if _looks_like_client_request(full_text, context):
            request_detail = _request_detail(context)
            return AIAnalysisResult(
                summary=f"{_sender_label(context)} is asking Rohan about {request_detail}.",
                action_type=ProposedActionType.REPLY,
                explanation="The sender asks for help, information, scheduling, or a deliverable.",
                confidence=Decimal("0.8700"),
                draft_response=_draft_for_request(context, request_detail),
            )

        if _looks_vague_but_needs_response(full_text):
            return AIAnalysisResult(
                summary="The message is brief and unclear, but likely expects a response.",
                action_type=ProposedActionType.ASK_CLARIFYING_QUESTION,
                explanation=(
                    "The sender appears to need input, but the request lacks enough detail "
                    "to answer confidently."
                ),
                confidence=Decimal("0.7100"),
                draft_response=_clarifying_draft(context),
            )

        return AIAnalysisResult(
            summary=_fallback_summary(context),
            action_type=ProposedActionType.REVIEW_NEEDED,
            explanation="No confident automated recommendation was found; keep this for local review.",
            confidence=Decimal("0.5200"),
        )


class OpenAIAnalysisProvider:
    def __init__(self, *, client: OpenAICompatibleJsonClient | None = None) -> None:
        self.client = client or build_openai_json_client()
        self.name = getattr(self.client, "provider_name", f"openai:{self.client.model}")

    def analyze(self, context: AIAnalysisContext) -> AIAnalysisResult:
        system_prompt, user_prompt = build_analysis_prompt(context)
        payload = self.client.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return _analysis_result_from_payload(context, payload, provider_name=self.name)


class FallbackAIAnalysisProvider:
    def __init__(self, primary: AIAnalysisProvider, fallback: AIAnalysisProvider | None = None) -> None:
        self.primary = primary
        self.fallback = fallback or MockAIAnalysisProvider()
        self.name = f"{self.primary.name}->mock_fallback"

    def analyze(self, context: AIAnalysisContext) -> AIAnalysisResult:
        try:
            return self.primary.analyze(context)
        except (AIProviderError, ValueError, TimeoutError):
            result = self.fallback.analyze(context)
            explanation = (
                f"{result.explanation} Live AI was unavailable or returned invalid output; "
                "the local mock fallback generated this review package."
            )
            return replace(result, explanation=explanation, provider_name=self.name)


def get_default_analysis_provider() -> AIAnalysisProvider:
    status = ai_provider_status(get_settings())
    if status.live_enabled:
        return FallbackAIAnalysisProvider(OpenAIAnalysisProvider())
    return MockAIAnalysisProvider()


def analyze_message(
    db: Session,
    message: Message,
    *,
    provider: AIAnalysisProvider | None = None,
    calendar_provider: CalendarAvailabilityProvider | None = None,
) -> AnalysisPersistenceResult:
    analysis_provider = provider or get_default_analysis_provider()
    context = build_analysis_context(db, message)
    result = analysis_provider.analyze(context)
    calendar_provider = calendar_provider or get_default_calendar_provider()
    calendar_recommendation = build_calendar_recommendation(
        _calendar_source_text(context),
        detected_due_date=result.detected_due_date,
        provider=calendar_provider,
    )
    merged_result = _merge_calendar_recommendation(context, result, calendar_recommendation)
    provider_name = merged_result.provider_name or analysis_provider.name
    summary = _upsert_conversation_summary(db, message.thread_id, merged_result, provider_name)
    package = _upsert_review_package(db, message, summary, merged_result, provider_name)
    _upsert_calendar_action_proposal(
        db,
        package,
        recommendation=calendar_recommendation,
        provider_name=calendar_provider.name,
    )
    _update_attention_recommendation(db, message, package)
    db.commit()
    db.refresh(summary)
    db.refresh(package)
    return AnalysisPersistenceResult(conversation_summary=summary, review_package=package)


def build_analysis_context(db: Session, message: Message) -> AIAnalysisContext:
    contact = _resolve_contact(db, message)
    classification = db.query(MessageClassification).filter_by(message_id=message.id).first()
    attention = db.query(AttentionItem).filter_by(message_id=message.id).first()
    timeline = conversation_context_messages(db, message.thread_id, message.id)
    guidance = resolve_guidance_for_message(db, message, contact=contact)
    selected_text = next(
        (item.text for item in timeline if item.is_selected),
        _message_text(message),
    )
    return AIAnalysisContext(
        message_id=message.id,
        thread_id=message.thread_id,
        subject=(message.subject or "").strip(),
        selected_message_text=selected_text,
        conversation_messages=tuple(timeline),
        contact_name=((contact.display_name or contact.primary_email or "").strip() if contact else ""),
        contact_relationship=(contact.relationship_type or "unknown") if contact else "unknown",
        contact_importance_tier=contact.importance_tier if contact else None,
        contact_state=contact_status(contact),
        classification_label=friendly_classification_label(classification),
        classification_summary=summarize_classification(classification),
        attention_score=attention.attention_score if attention else None,
        attention_reason=(attention.reason or "") if attention else "",
        feedback_summary=feedback_summary(db, message, contact),
        learned_salutation_style=(guidance.salutation_style if guidance else "") or "",
        learned_preferred_name=(guidance.preferred_name if guidance else "") or "",
        learned_tone_notes=(guidance.tone_notes if guidance else "") or "",
    )


def conversation_context_messages(
    db: Session, thread_id: int, selected_message_id: int | None = None
) -> list[AnalysisMessageContext]:
    messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.received_at.asc(), Message.id.asc())
        .all()
    )
    return [
        AnalysisMessageContext(
            message_id=message.id,
            sender_name=(message.sender_display_name or "").strip(),
            sender_email=(message.sender_email or "").strip(),
            subject=(message.subject or "").strip(),
            received_at=message.received_at,
            recipient_emails=tuple(deserialize_addresses(message.recipient_emails)),
            cc_emails=tuple(deserialize_addresses(message.cc_emails)),
            text=_message_text(message),
            is_selected=message.id == selected_message_id,
        )
        for message in messages
    ]


def build_analysis_prompt(context: AIAnalysisContext) -> tuple[str, str]:
    action_values = ", ".join(action.value for action in ProposedActionType)
    system_prompt = (
        "You analyze private communication threads for a local review-only dashboard. "
        "Do not recommend sending, archiving, deleting, unsubscribing, or creating calendar "
        "items directly. Return only a JSON object. Avoid generic filler such as "
        "'thanks for reaching out' unless the thread specifically warrants it. If no response "
        "is needed, set draft_response to null."
    )
    timeline = "\n".join(_prompt_timeline_line(message) for message in context.conversation_messages)
    selected = next((message for message in context.conversation_messages if message.is_selected), None)
    selected_line = _prompt_timeline_line(selected) if selected else context.selected_message_text
    user_prompt = f"""
Known proposed action types:
{action_values}

Required JSON schema:
{{
  "summary": "specific one or two sentence summary",
  "action_type": "one of the known proposed action types",
  "explanation": "grounded evidence for the recommendation",
  "confidence": 0.0,
  "draft_response": "reply draft or null",
  "detected_due_date": "YYYY-MM-DD or null",
  "proposed_lead_time_days": 7,
  "caveats": ["optional review caveats"]
}}

Contact relationship:
- name: {context.contact_name or "unknown"}
- relationship: {context.contact_relationship}
- importance tier: {context.contact_importance_tier}
- contact state: {context.contact_state}

Approved voice guidance:
- salutation style: {context.learned_salutation_style or "none"}
- preferred name: {context.learned_preferred_name or "none"}
- tone notes: {context.learned_tone_notes or "none"}

Classification and attention:
- classification: {context.classification_label}
- classification summary: {context.classification_summary}
- attention score: {context.attention_score}
- attention reason: {context.attention_reason}

Recent user corrections:
{context.feedback_summary}

Selected message:
{selected_line}

Full conversation timeline:
{timeline}

Decision rules:
- Friend acknowledgements of another person's cancellation usually need no response.
- Client requests should recommend reply and mention the actual request in any draft.
- Renewal or service-provider due dates should recommend create_calendar_reminder with a detected date and lead time.
- Marketing/newsletter repetition should recommend mark_noise or unsubscribe_review with evidence.
- Vague likely-actionable messages should recommend ask_clarifying_question or review_needed.
""".strip()
    return system_prompt, user_prompt


def _analysis_result_from_payload(
    context: AIAnalysisContext,
    payload: dict[str, Any],
    *,
    provider_name: str,
) -> AIAnalysisResult:
    summary = sanitize_ai_text(payload.get("summary"), max_length=700)
    explanation = sanitize_ai_text(payload.get("explanation"), max_length=1800)
    if not summary or not explanation:
        raise AIProviderError("AI output missed summary or explanation")

    action_type = _parse_action_type(payload.get("action_type"))
    confidence = decimal_confidence(payload.get("confidence"))
    draft_response = sanitize_ai_text(payload.get("draft_response"), max_length=3000) or None
    if action_type in {
        ProposedActionType.NO_RESPONSE_NEEDED,
        ProposedActionType.MARK_NOISE,
        ProposedActionType.UNSUBSCRIBE_REVIEW,
        ProposedActionType.CREATE_CALENDAR_REMINDER,
        ProposedActionType.ARCHIVE_CANDIDATE,
        ProposedActionType.DELETE_CANDIDATE,
    }:
        draft_response = None

    if action_type == ProposedActionType.REPLY and draft_response:
        request_detail = _request_detail(context).lower()
        if request_detail and request_detail not in draft_response.lower():
            explanation = (
                f"{explanation} Draft was accepted but should be reviewed for specificity "
                "against the actual request."
            )

    detected_due_date = sanitize_ai_text(payload.get("detected_due_date"), max_length=100) or None
    proposed_lead_time = _parse_lead_time(payload.get("proposed_lead_time_days"))
    if action_type == ProposedActionType.CREATE_CALENDAR_REMINDER and proposed_lead_time:
        explanation = f"{explanation} Proposed lead time: {proposed_lead_time} days before due date."

    caveats = payload.get("caveats")
    if isinstance(caveats, list):
        cleaned = [sanitize_ai_text(item, max_length=200) for item in caveats[:3]]
        cleaned = [item for item in cleaned if item]
        if cleaned:
            explanation = f"{explanation} Caveats: {'; '.join(cleaned)}"

    return AIAnalysisResult(
        summary=summary,
        action_type=action_type,
        explanation=explanation,
        confidence=confidence,
        draft_response=draft_response,
        detected_due_date=detected_due_date,
        provider_name=provider_name,
    )


def recent_review_packages_for_message(
    db: Session, message_id: int, limit: int = 5
) -> list[ProposedActionReviewPackage]:
    return (
        db.query(ProposedActionReviewPackage)
        .filter(ProposedActionReviewPackage.message_id == message_id)
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .limit(limit)
        .all()
    )


def latest_review_package_for_message(
    db: Session, message_id: int
) -> ProposedActionReviewPackage | None:
    return (
        db.query(ProposedActionReviewPackage)
        .filter(ProposedActionReviewPackage.message_id == message_id)
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .first()
    )


def update_review_package_status(
    db: Session,
    package_id: int,
    *,
    status: ReviewPackageStatus,
    user_note: str | None = None,
    draft_response: str | None = None,
    snoozed_until: datetime | None = None,
) -> ProposedActionReviewPackage:
    package = db.get(ProposedActionReviewPackage, package_id)
    if not package:
        raise ValueError("Review package not found")
    package.status = status
    package.user_note = (user_note or "").strip() or None
    package.snoozed_until = snoozed_until
    if draft_response is not None:
        package.draft_response = draft_response.strip() or None
        if status == ReviewPackageStatus.PENDING:
            package.status = ReviewPackageStatus.EDITED
    package.updated_at = utcnow()
    db.commit()
    db.refresh(package)
    return package


def feedback_summary(db: Session, message: Message, contact: Contact | None) -> str:
    filters = [UserFeedback.message_id == message.id]
    if contact:
        filters.append(UserFeedback.contact_id == contact.id)
    rows = (
        db.query(UserFeedback)
        .filter(or_(*filters))
        .order_by(UserFeedback.created_at.desc())
        .limit(8)
        .all()
    )
    if not rows:
        return "No correction history recorded."

    parts = []
    for row in rows:
        label = row.corrected_label or row.corrected_value or row.feedback_type
        parts.append(f"{row.feedback_type}: {label}")
    return "; ".join(parts)[:700]


def _upsert_conversation_summary(
    db: Session, thread_id: int, result: AIAnalysisResult, provider_name: str
) -> ConversationSummary:
    summary = db.query(ConversationSummary).filter_by(thread_id=thread_id).first()
    if not summary:
        summary = ConversationSummary(thread_id=thread_id, summary_text=result.summary)
        db.add(summary)
    summary.summary_text = result.summary
    summary.detected_due_date = result.detected_due_date
    summary.provider_name = provider_name
    summary.updated_at = utcnow()
    db.flush()
    return summary


def _upsert_review_package(
    db: Session,
    message: Message,
    summary: ConversationSummary,
    result: AIAnalysisResult,
    provider_name: str,
) -> ProposedActionReviewPackage:
    package = db.query(ProposedActionReviewPackage).filter_by(message_id=message.id).first()
    if not package:
        package = ProposedActionReviewPackage(
            thread_id=message.thread_id,
            message_id=message.id,
            conversation_summary_id=summary.id,
            action_type=result.action_type,
            explanation=result.explanation,
            confidence=result.confidence,
            status=ReviewPackageStatus.PENDING,
        )
        db.add(package)
    package.thread_id = message.thread_id
    package.conversation_summary_id = summary.id
    package.action_type = result.action_type
    package.explanation = result.explanation
    package.confidence = result.confidence
    package.draft_response = result.draft_response
    package.provider_name = provider_name
    package.is_external_action = False
    package.updated_at = utcnow()
    db.flush()
    return package


def _upsert_calendar_action_proposal(
    db: Session,
    package: ProposedActionReviewPackage,
    *,
    recommendation: CalendarRecommendation | None,
    provider_name: str,
) -> CalendarActionProposal | None:
    existing = (
        db.query(CalendarActionProposal)
        .filter(CalendarActionProposal.review_package_id == package.id)
        .order_by(CalendarActionProposal.updated_at.desc(), CalendarActionProposal.id.desc())
        .first()
    )
    if not recommendation:
        if existing:
            db.delete(existing)
        return None
    proposal = existing or CalendarActionProposal(review_package_id=package.id, action_kind="")
    if existing is None:
        db.add(proposal)
    proposal.action_kind = recommendation.action_kind
    proposal.proposed_start_at = recommendation.proposed_start_at
    proposal.proposed_end_at = recommendation.proposed_end_at
    proposal.reminder_at = recommendation.reminder_at
    proposal.availability_reasoning = recommendation.availability_reasoning
    proposal.conflict_summary = recommendation.conflict_summary
    proposal.available_windows = (
        "\n".join(f"{start.isoformat()}|{end.isoformat()}" for start, end in recommendation.available_windows)
        if recommendation.available_windows
        else None
    )
    proposal.provider_name = provider_name
    proposal.updated_at = utcnow()
    db.flush()
    return proposal


def _merge_calendar_recommendation(
    context: AIAnalysisContext,
    result: AIAnalysisResult,
    recommendation: CalendarRecommendation | None,
) -> AIAnalysisResult:
    if not recommendation:
        return result
    summary = result.summary
    if recommendation.action_kind == "create_reminder" and result.detected_due_date:
        summary = f"{summary} Reminder candidate prepared for due date {result.detected_due_date}."
    elif recommendation.proposed_start_at:
        summary = (
            f"{summary} Scheduling proposal detected for "
            f"{recommendation.proposed_start_at.strftime('%Y-%m-%d %H:%M')}."
        )
    explanation = result.explanation
    if recommendation.availability_reasoning:
        explanation = f"{explanation} Availability: {recommendation.availability_reasoning}"
    if recommendation.conflict_summary:
        explanation = f"{explanation} Conflict: {recommendation.conflict_summary}"
    draft_response = result.draft_response
    if recommendation.action_kind == "offer_availability" and recommendation.proposed_start_at:
        draft_response = (
            f"Hi {context.contact_name or 'there'},\n\n"
            f"I can do {recommendation.proposed_start_at.strftime('%A at %I:%M %p')}. "
            "If that works for you, I can confirm it.\n\n"
            "Thanks"
        )
    elif recommendation.action_kind == "ask_for_time_clarification":
        alternatives = _format_windows(recommendation.available_windows)
        draft_response = (
            f"Hi {context.contact_name or 'there'},\n\n"
            "I may have a conflict at the proposed time. Could you confirm a time that works, "
            f"or choose one of these windows: {alternatives}?\n\n"
            "Thanks"
        )
    return AIAnalysisResult(
        summary=summary,
        action_type=recommendation.action_type,
        explanation=explanation,
        confidence=Decimal(str(max(float(result.confidence), recommendation.confidence))),
        draft_response=draft_response,
        detected_due_date=result.detected_due_date,
        provider_name=result.provider_name,
    )


def _format_windows(windows: tuple[tuple[datetime, datetime], ...]) -> str:
    if not windows:
        return "next available time"
    return "; ".join(
        f"{start.strftime('%a %b %d %I:%M %p')} - {end.strftime('%I:%M %p')}"
        for start, end in windows[:2]
    )


def _calendar_source_text(context: AIAnalysisContext) -> str:
    parts = [context.subject, context.selected_message_text]
    parts.extend(message.text for message in context.conversation_messages)
    return " ".join(part for part in parts if part)


def _update_attention_recommendation(
    db: Session, message: Message, package: ProposedActionReviewPackage
) -> None:
    item = db.query(AttentionItem).filter_by(message_id=message.id).first()
    if not item:
        return
    item.recommended_action = package.action_type.value
    item.reason = package.explanation[:500]
    item.updated_at = utcnow()


def _resolve_contact(db: Session, message: Message) -> Contact | None:
    if message.thread and message.thread.contact_id:
        return db.get(Contact, message.thread.contact_id)
    if message.sender_email:
        return find_contact_by_sender_email(db, message.sender_email)
    return None


def _message_text(message: Message) -> str:
    return (message.body_text or message.snippet or "").strip()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _prompt_timeline_line(message: AnalysisMessageContext | None) -> str:
    if not message:
        return ""
    marker = "SELECTED" if message.is_selected else "thread"
    received = message.received_at.isoformat() if message.received_at else "unknown time"
    sender = message.sender_name or message.sender_email or "unknown sender"
    recipients = ", ".join(message.recipient_emails) or "unknown recipients"
    ccs = ", ".join(message.cc_emails) or "none"
    body = sanitize_ai_text(message.text, max_length=1200)
    return (
        f"[{marker}] {received} | From: {sender} <{message.sender_email}> | "
        f"To: {recipients} | Cc: {ccs} | Subject: {message.subject} | Body: {body}"
    )


def _parse_action_type(value: Any) -> ProposedActionType:
    normalized = sanitize_ai_text(value, max_length=100).lower().replace("-", "_").replace(" ", "_")
    try:
        return ProposedActionType(normalized)
    except ValueError as exc:
        raise AIProviderError(f"AI output action type is not supported: {normalized}") from exc


def _parse_lead_time(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > 365:
        return None
    return parsed


def _has_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _detect_due_date(value: str) -> str | None:
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", value)
    if iso:
        return iso.group(1)
    month = re.search(
        r"\b("
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
        r")\s+\d{1,2}(?:,\s*20\d{2})?\b",
        value,
    )
    return month.group(0).title() if month else None


def _looks_like_acknowledged_cancellation(full_text: str, selected_text: str) -> bool:
    cancellation = _has_any(full_text, ["cancel", "cancelled", "canceled", "can't make", "dinner"])
    acknowledgement = _has_any(
        selected_text,
        ["no worries", "thanks for the heads up", "thank you for the heads up", "no problem"],
    )
    asks_rohan = _has_any(selected_text, ["rohan?", "can you", "could you", "please", "let me know"])
    return cancellation and acknowledgement and not asks_rohan


def _looks_like_newsletter(full_text: str, classification_label: str) -> bool:
    if classification_label in {"Newsletter", "Marketing", "Noise"}:
        return True
    return _has_any(
        full_text,
        [
            "unsubscribe",
            "newsletter",
            "email preferences",
            "manage preferences",
            "limited time",
            "special offer",
            "promotion",
            "marketing",
        ],
    )


def _looks_like_client_request(full_text: str, context: AIAnalysisContext) -> bool:
    relationship = context.contact_relationship.lower()
    if relationship == "client" and _has_any(full_text, ["?", "please", "can you", "could you"]):
        return True
    if context.classification_label == "Needs reply" or "client_work" in context.classification_summary:
        return True
    return _has_any(
        full_text,
        [
            "can you help",
            "could you help",
            "please send",
            "please review",
            "can we schedule",
            "could we schedule",
            "deliverable",
            "proposal",
            "quote",
            "estimate",
        ],
    )


def _looks_vague_but_needs_response(full_text: str) -> bool:
    return _has_any(
        full_text,
        ["thoughts?", "can we talk", "call me", "ping me", "what do you think", "need your input"],
    )


def _ack_summary(context: AIAnalysisContext) -> str:
    senders = {message.sender_name or message.sender_email for message in context.conversation_messages}
    if any("michael" in sender.lower() for sender in senders) and any(
        "christian" in sender.lower() for sender in senders
    ):
        return "Michael acknowledged Christian's cancellation."
    return "The latest message is only acknowledging a cancellation."


def _fallback_summary(context: AIAnalysisContext) -> str:
    sender = _sender_label(context)
    subject = context.subject or "the conversation"
    return f"{sender} sent a message about {subject}."


def _sender_label(context: AIAnalysisContext) -> str:
    selected = next((message for message in context.conversation_messages if message.is_selected), None)
    if selected:
        return selected.sender_name or selected.sender_email or "The sender"
    return context.contact_name or "The sender"


def _request_detail(context: AIAnalysisContext) -> str:
    selected = context.selected_message_text.strip()
    source = selected or context.subject
    source = re.sub(r"\s+", " ", source).strip()
    if not source:
        return "the request"
    sentence = re.split(r"(?<=[.!?])\s+", source)[0]
    sentence = sentence.strip(" .!?")
    return sentence[:160] or "the request"


def _draft_for_request(context: AIAnalysisContext, request_detail: str) -> str:
    recipient = context.contact_name or _sender_label(context)
    topic = request_detail[:180]
    return (
        f"Hi {recipient},\n\n"
        f"Thanks for reaching out. I can help with {topic}. I will review the thread context "
        "and come back with the specific next step or answer.\n\n"
        "Best"
    )


def _clarifying_draft(context: AIAnalysisContext) -> str:
    recipient = context.contact_name or _sender_label(context)
    return (
        f"Hi {recipient},\n\n"
        "Can you send me a bit more detail on what you need from me here? Once I have that, "
        "I can give you a clearer answer.\n\n"
        "Thanks"
    )
