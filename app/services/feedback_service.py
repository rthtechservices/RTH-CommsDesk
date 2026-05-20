from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    Contact,
    Message,
    MessageClassification,
    ProposedActionReviewPackage,
    ProposedActionType,
    UserFeedback,
    utcnow,
)
from app.services.attention_service import upsert_attention_item
from app.services.contact_service import find_contact_by_sender_email


CORRECTION_LABELS = [
    "important",
    "needs_reply",
    "personal",
    "client_work",
    "job_alert",
    "newsletter",
    "receipt",
    "system_notice",
    "marketing",
    "noise",
    "ignore",
]

REVIEW_PACKAGE_CORRECTION_TYPES = [
    "correct_action_type",
    "needs_reply",
    "does_not_need_reply",
    "better_summary",
    "better_draft_instruction",
    "correct_calendar_interpretation",
    "mark_noise",
    "mark_not_noise",
]


@dataclass(frozen=True)
class CorrectionResult:
    feedback: UserFeedback
    classification: MessageClassification
    attention_item: AttentionItem


@dataclass(frozen=True)
class ReviewPackageCorrectionResult:
    feedback: UserFeedback
    package: ProposedActionReviewPackage


def summarize_classification(classification: MessageClassification | None) -> str:
    if not classification:
        return "No classification"

    flags = []
    if classification.requires_reply:
        flags.append("requires_reply")
    if classification.is_human_personal:
        flags.append("personal")
    if classification.is_client_work:
        flags.append("client_work")
    if classification.is_marketing:
        flags.append("marketing")
    if classification.is_newsletter:
        flags.append("newsletter")
    if classification.is_receipt:
        flags.append("receipt")
    if classification.is_group_noise:
        flags.append("noise")
    if classification.is_system_notification:
        flags.append("system")

    flag_summary = ", ".join(flags) if flags else "no flags"
    return (
        f"urgency={classification.urgency_level}; "
        f"{flag_summary}; "
        f"reason={classification.classification_reason or 'none'}"
    )[:500]


def friendly_classification_label(classification: MessageClassification | None) -> str:
    if not classification:
        return "Unclassified"
    if classification.requires_reply:
        return "Needs reply"
    if classification.is_client_work:
        return "Client/work"
    if classification.is_human_personal:
        return "Personal"
    if classification.is_newsletter:
        return "Newsletter"
    if classification.is_receipt:
        return "Receipt"
    if classification.is_marketing:
        return "Marketing"
    if classification.is_system_notification:
        return "System notice"
    if classification.is_group_noise:
        return "Noise"
    return "Review"


def classification_tags(classification: MessageClassification | None) -> list[str]:
    if not classification:
        return []
    tags = []
    if classification.requires_reply:
        tags.append("Reply")
    if classification.urgency_level >= 2:
        tags.append("Time sensitive")
    if classification.is_client_work:
        tags.append("Work")
    if classification.is_human_personal:
        tags.append("Personal")
    if classification.is_newsletter:
        tags.append("Newsletter")
    if classification.is_receipt:
        tags.append("Receipt")
    if classification.is_marketing:
        tags.append("Marketing")
    if classification.is_system_notification:
        tags.append("System")
    if classification.is_group_noise:
        tags.append("Noise")
    return tags


def apply_message_correction(
    db: Session,
    message_id: int,
    corrected_label: str,
    corrected_importance: int | None = None,
    notes: str | None = None,
) -> CorrectionResult:
    corrected_label = corrected_label.strip().lower()
    if corrected_label not in CORRECTION_LABELS:
        raise ValueError("Unsupported correction label")

    message = db.get(Message, message_id)
    if not message:
        raise ValueError("Message not found")

    classification = db.query(MessageClassification).filter_by(message_id=message_id).first()
    if not classification:
        classification = MessageClassification(message_id=message.id)
        db.add(classification)
        db.flush()

    contact = _resolve_contact(db, message)
    original_summary = summarize_classification(classification)

    _apply_label_to_classification(classification, corrected_label, corrected_importance)

    feedback = UserFeedback(
        message_id=message.id,
        contact_id=contact.id if contact else None,
        feedback_type="classification_correction",
        feedback_text=notes,
        original_value=original_summary,
        corrected_value=corrected_label,
        original_classification_summary=original_summary,
        corrected_label=corrected_label,
        corrected_importance=corrected_importance,
        corrected_requires_reply=classification.requires_reply,
        corrected_is_noise=classification.is_group_noise,
        corrected_is_newsletter=classification.is_newsletter,
        corrected_is_client_work=classification.is_client_work,
    )
    db.add(feedback)

    item = upsert_attention_item(db, contact, message.thread, message, classification)
    if corrected_label in {"noise", "ignore"}:
        item.status = AttentionStatus.DISMISSED
    else:
        item.status = AttentionStatus.NEW

    db.commit()
    db.refresh(feedback)
    db.refresh(classification)
    db.refresh(item)
    return CorrectionResult(feedback=feedback, classification=classification, attention_item=item)


def apply_review_package_correction(
    db: Session,
    package_id: int,
    *,
    correction_type: str,
    corrected_value: str | None = None,
    notes: str | None = None,
) -> ReviewPackageCorrectionResult:
    correction_type = correction_type.strip().lower()
    if correction_type not in REVIEW_PACKAGE_CORRECTION_TYPES:
        raise ValueError("Unsupported review package correction")
    package = db.get(ProposedActionReviewPackage, package_id)
    if not package:
        raise ValueError("Review package not found")

    original_value = _package_correction_original(package, correction_type)
    cleaned_value = (corrected_value or "").strip() or None
    freeform_value = cleaned_value or (notes or "").strip() or None
    if correction_type == "correct_action_type" and cleaned_value:
        package.action_type = ProposedActionType(cleaned_value)
    elif correction_type == "needs_reply":
        package.action_type = ProposedActionType.REPLY
    elif correction_type == "does_not_need_reply":
        package.action_type = ProposedActionType.NO_RESPONSE_NEEDED
        package.draft_response = None
    elif correction_type == "better_summary" and freeform_value and package.conversation_summary:
        package.conversation_summary.summary_text = freeform_value[:1000]
    elif correction_type == "better_draft_instruction" and freeform_value:
        package.draft_response = freeform_value[:3000]
    elif correction_type == "correct_calendar_interpretation" and freeform_value:
        package.explanation = f"{package.explanation}\nCorrection: {freeform_value[:700]}"
    elif correction_type == "mark_noise":
        package.action_type = ProposedActionType.MARK_NOISE
        package.draft_response = None
    elif correction_type == "mark_not_noise" and package.action_type == ProposedActionType.MARK_NOISE:
        package.action_type = ProposedActionType.REVIEW_NEEDED

    package.status = package.status
    package.user_note = _combine_notes(package.user_note, notes)
    package.updated_at = utcnow()
    feedback = UserFeedback(
        message_id=package.message_id,
        contact_id=package.message.thread.contact_id if package.message and package.message.thread else None,
        feedback_type=f"review_package_{correction_type}",
        feedback_text=(notes or "").strip() or None,
        original_value=original_value,
        corrected_value=freeform_value or _package_correction_original(package, correction_type),
        corrected_label=correction_type,
        corrected_requires_reply=package.action_type in {
            ProposedActionType.REPLY,
            ProposedActionType.ASK_CLARIFYING_QUESTION,
        },
        corrected_is_noise=package.action_type in {
            ProposedActionType.MARK_NOISE,
            ProposedActionType.UNSUBSCRIBE_REVIEW,
            ProposedActionType.ARCHIVE_CANDIDATE,
            ProposedActionType.DELETE_CANDIDATE,
        },
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    db.refresh(package)
    return ReviewPackageCorrectionResult(feedback=feedback, package=package)


def _resolve_contact(db: Session, message: Message) -> Contact | None:
    if message.thread and message.thread.contact_id:
        return db.get(Contact, message.thread.contact_id)
    if message.sender_email:
        return find_contact_by_sender_email(db, message.sender_email)
    return None


def _apply_label_to_classification(
    classification: MessageClassification, corrected_label: str, corrected_importance: int | None
) -> None:
    reason = f"User corrected classification to {corrected_label}"

    if corrected_label == "important":
        classification.urgency_level = max(classification.urgency_level, corrected_importance or 3)
        classification.is_marketing = False
        classification.is_newsletter = False
        classification.is_group_noise = False
        classification.classification_reason = reason
        return

    if corrected_label == "needs_reply":
        classification.requires_reply = True
        classification.urgency_level = max(classification.urgency_level, corrected_importance or 1)
        classification.is_marketing = False
        classification.is_newsletter = False
        classification.is_group_noise = False
        classification.classification_reason = reason
        return

    if corrected_label == "personal":
        classification.is_human_personal = True
        classification.is_client_work = False
        classification.is_marketing = False
        classification.is_newsletter = False
        classification.is_group_noise = False
        classification.classification_reason = reason
        return

    if corrected_label == "client_work":
        classification.is_client_work = True
        classification.is_human_personal = False
        classification.is_marketing = False
        classification.is_newsletter = False
        classification.is_group_noise = False
        classification.urgency_level = max(classification.urgency_level, corrected_importance or 1)
        classification.classification_reason = reason
        return

    if corrected_label == "job_alert":
        classification.requires_reply = False
        classification.urgency_level = min(classification.urgency_level, corrected_importance or 1)
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_marketing = True
        classification.is_newsletter = True
        classification.is_group_noise = True
        classification.is_system_notification = True
        classification.classification_reason = reason
        return

    if corrected_label == "newsletter":
        classification.requires_reply = False
        classification.urgency_level = corrected_importance or 0
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_marketing = True
        classification.is_newsletter = True
        classification.is_group_noise = True
        classification.classification_reason = reason
        return

    if corrected_label == "receipt":
        classification.requires_reply = False
        classification.urgency_level = corrected_importance or 0
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_marketing = False
        classification.is_newsletter = False
        classification.is_receipt = True
        classification.is_group_noise = True
        classification.classification_reason = reason
        return

    if corrected_label == "system_notice":
        classification.requires_reply = False
        classification.urgency_level = corrected_importance or 0
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_system_notification = True
        classification.is_group_noise = True
        classification.classification_reason = reason
        return

    if corrected_label == "marketing":
        classification.requires_reply = False
        classification.urgency_level = corrected_importance or 0
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_marketing = True
        classification.is_group_noise = True
        classification.classification_reason = reason
        return

    if corrected_label in {"noise", "ignore"}:
        classification.requires_reply = False
        classification.urgency_level = 0
        classification.is_client_work = False
        classification.is_human_personal = False
        classification.is_marketing = True
        classification.is_newsletter = corrected_label == "noise" or classification.is_newsletter
        classification.is_group_noise = True
        classification.classification_reason = reason


def _package_correction_original(
    package: ProposedActionReviewPackage, correction_type: str
) -> str | None:
    if correction_type == "better_summary":
        return package.conversation_summary.summary_text if package.conversation_summary else None
    if correction_type == "better_draft_instruction":
        return package.draft_response
    if correction_type == "correct_calendar_interpretation":
        return package.explanation
    return package.action_type.value


def _combine_notes(existing: str | None, new_note: str | None) -> str | None:
    cleaned = (new_note or "").strip()
    if not cleaned:
        return existing
    if not existing:
        return cleaned[:1000]
    return f"{existing}\n{cleaned}"[:1000]
