from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionItem,
    Contact,
    DraftReply,
    DraftStatus,
    Message,
    MessageClassification,
    VoiceProfile,
)
from app.services.analysis_service import (
    conversation_context_messages,
    feedback_summary,
    latest_review_package_for_message,
)
from app.services.contact_service import contact_status, find_contact_by_sender_email
from app.services.feedback_service import friendly_classification_label, summarize_classification

SHORT_ACK_AUDIENCE = "short_acknowledgement"
SUPPORTED_DRAFT_AUDIENCES = [
    "client",
    "friend",
    "partner",
    "vendor",
    SHORT_ACK_AUDIENCE,
]


@dataclass(frozen=True)
class DraftContext:
    message_id: int
    thread_id: int
    subject: str
    sender_name: str
    sender_email: str
    contact_name: str
    contact_relationship: str
    contact_importance_tier: int | None
    contact_state: str
    classification_label: str
    classification_summary: str
    attention_score: int | None
    attention_reason: str
    recommended_action: str
    feedback_summary: str
    conversation_summary: str
    proposed_action_type: str
    proposed_action_explanation: str
    review_package_draft_response: str
    full_thread_context: str


class DraftProvider(Protocol):
    name: str

    def generate(self, context: DraftContext, voice_profile: VoiceProfile) -> str:
        """Return a local review-only draft suggestion."""


class MockDraftProvider:
    name = "mock"

    def generate(self, context: DraftContext, voice_profile: VoiceProfile) -> str:
        audience = (voice_profile.audience_type or "client").strip().lower()
        recipient = _recipient_name(context)
        subject_line = f"Re: {context.subject}" if context.subject else "Re: your note"

        if context.review_package_draft_response:
            body = context.review_package_draft_response
        elif context.proposed_action_type == "no_response_needed":
            body = (
                "No draft is recommended for this message because the local analysis says "
                "no response is needed. Generate a reply only if you intentionally want to "
                "override that recommendation."
            )
        elif context.proposed_action_type == "ask_clarifying_question":
            body = (
                f"Hi {recipient},\n\n"
                "Can you send me a bit more detail on what you need from me here? Once I have "
                "that, I can give you a clearer answer.\n\n"
                "Thanks"
            )
        elif context.proposed_action_type == "reply":
            detail = _specific_reply_detail(context)
            body = (
                f"Hi {recipient},\n\n"
                f"Thanks for reaching out. I can help with {detail}. I will review the thread "
                "context and come back with clear next steps.\n\n"
                "Best"
            )
        elif audience == "friend":
            body = (
                f"Hey {recipient},\n\n"
                "Thanks for the note. I saw this and wanted to acknowledge it directly. "
                "I will take a closer look and follow up with anything specific.\n\n"
                "Talk soon"
            )
        elif audience == "partner":
            body = (
                f"Hey {recipient},\n\n"
                "I hear you. I will look at this properly and come back with a clear answer "
                "instead of rushing a half-response.\n\n"
                "Love"
            )
        elif audience == "vendor":
            body = (
                f"Hi {recipient},\n\n"
                "Thanks for sending this. Please keep this thread updated with any required "
                "next steps, timing, or outstanding items.\n\n"
                "Regards"
            )
        elif audience == SHORT_ACK_AUDIENCE:
            body = (
                f"Hi {recipient},\n\n"
                "Received, thank you. I will review and follow up if anything else is needed.\n\n"
                "Thanks"
            )
        else:
            body = (
                f"Hi {recipient},\n\n"
                "Thanks for reaching out. I have this on my radar and will review the details. "
                "I will follow up with clear next steps once I have confirmed the path forward.\n\n"
                "Best"
            )

        note = "Review-only draft suggestion. This has not been sent."
        if context.classification_label in {"Newsletter", "Marketing", "Noise"}:
            note += " This message may not need a reply."

        return f"{note}\n\nSubject: {subject_line}\n\n{body}"


def create_draft_reply(
    db: Session,
    message: Message,
    *,
    voice_profile_id: int | None = None,
    audience_type: str | None = None,
    provider: DraftProvider | None = None,
) -> DraftReply:
    voice_profile = select_voice_profile(
        db, message=message, voice_profile_id=voice_profile_id, audience_type=audience_type
    )
    draft_provider = provider or MockDraftProvider()
    context = build_draft_context(db, message)
    draft = DraftReply(
        thread_id=message.thread_id,
        message_id=message.id,
        voice_profile_id=voice_profile.id if voice_profile else None,
        status=DraftStatus.GENERATED,
        draft_text=draft_provider.generate(context, voice_profile or _fallback_voice_profile()),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def build_draft_context(db: Session, message: Message) -> DraftContext:
    contact = _resolve_contact(db, message)
    classification = db.query(MessageClassification).filter_by(message_id=message.id).first()
    attention = db.query(AttentionItem).filter_by(message_id=message.id).first()
    review_package = latest_review_package_for_message(db, message.id)
    conversation_summary = (
        review_package.conversation_summary.summary_text
        if review_package and review_package.conversation_summary
        else ""
    )
    return DraftContext(
        message_id=message.id,
        thread_id=message.thread_id,
        subject=(message.subject or "").strip(),
        sender_name=(message.sender_display_name or "").strip(),
        sender_email=(message.sender_email or "").strip(),
        contact_name=(
            (contact.display_name or contact.primary_email or "").strip() if contact else ""
        ),
        contact_relationship=(contact.relationship_type or "unknown") if contact else "unknown",
        contact_importance_tier=contact.importance_tier if contact else None,
        contact_state=contact_status(contact),
        classification_label=friendly_classification_label(classification),
        classification_summary=summarize_classification(classification),
        attention_score=attention.attention_score if attention else None,
        attention_reason=(attention.reason or "") if attention else "",
        recommended_action=(attention.recommended_action or "") if attention else "",
        feedback_summary=feedback_summary(db, message, contact),
        conversation_summary=conversation_summary,
        proposed_action_type=(review_package.action_type.value if review_package else ""),
        proposed_action_explanation=(review_package.explanation if review_package else ""),
        review_package_draft_response=(review_package.draft_response if review_package else "") or "",
        full_thread_context=_full_thread_context(db, message),
    )


def select_voice_profile(
    db: Session,
    *,
    message: Message,
    voice_profile_id: int | None = None,
    audience_type: str | None = None,
) -> VoiceProfile | None:
    if voice_profile_id:
        selected = db.get(VoiceProfile, voice_profile_id)
        if selected:
            return selected

    audience = _normalize_audience(audience_type)
    if not audience:
        audience = _infer_audience(db, message)

    if audience:
        profile = (
            db.query(VoiceProfile)
            .filter(VoiceProfile.audience_type == audience)
            .order_by(VoiceProfile.id)
            .first()
        )
        if profile:
            return profile

    return db.query(VoiceProfile).order_by(VoiceProfile.id).first()


def available_voice_profiles(db: Session) -> list[VoiceProfile]:
    return db.query(VoiceProfile).order_by(VoiceProfile.audience_type, VoiceProfile.name).all()


def suggested_voice_profile_id(db: Session, message: Message) -> int | None:
    profile = select_voice_profile(db, message=message)
    return profile.id if profile else None


def recent_drafts_for_message(db: Session, message_id: int, limit: int = 5) -> list[DraftReply]:
    return (
        db.query(DraftReply)
        .filter(DraftReply.message_id == message_id)
        .order_by(DraftReply.created_at.desc(), DraftReply.id.desc())
        .limit(limit)
        .all()
    )


def _resolve_contact(db: Session, message: Message) -> Contact | None:
    if message.thread and message.thread.contact_id:
        return db.get(Contact, message.thread.contact_id)
    if message.sender_email:
        return find_contact_by_sender_email(db, message.sender_email)
    return None


def _infer_audience(db: Session, message: Message) -> str:
    contact = _resolve_contact(db, message)
    relationship = (contact.relationship_type or "unknown").strip().lower() if contact else ""
    if relationship in {"client", "vendor", "partner", "friend"}:
        return relationship
    if relationship in {"close_friend", "family"}:
        return "friend"

    classification = db.query(MessageClassification).filter_by(message_id=message.id).first()
    attention = db.query(AttentionItem).filter_by(message_id=message.id).first()
    if classification and classification.is_client_work:
        return "client"
    if attention and attention.recommended_action == "Reply":
        return "client"
    return SHORT_ACK_AUDIENCE


def _normalize_audience(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    if normalized == "short_ack":
        normalized = SHORT_ACK_AUDIENCE
    return normalized if normalized in SUPPORTED_DRAFT_AUDIENCES else None


def _recipient_name(context: DraftContext) -> str:
    return (
        context.contact_name or context.sender_name or context.sender_email.split("@")[0] or "there"
    )


def _full_thread_context(db: Session, message: Message) -> str:
    parts = []
    for item in conversation_context_messages(db, message.thread_id, message.id):
        sender = item.sender_name or item.sender_email or "Unknown sender"
        marker = "selected" if item.is_selected else "thread"
        text = item.text[:800]
        parts.append(f"[{marker}] {sender}: {text}")
    return "\n".join(parts)[:3000]


def _specific_reply_detail(context: DraftContext) -> str:
    source = context.conversation_summary or context.full_thread_context or context.subject
    source = " ".join(source.split())
    if not source:
        return "this"
    return source[:180]


def _fallback_voice_profile() -> VoiceProfile:
    return VoiceProfile(
        name="Local Mock Client Voice",
        audience_type="client",
        tone_description="direct, warm, concise",
        formality_level=3,
        humor_level=0,
        signoff_style="clear next steps",
    )
