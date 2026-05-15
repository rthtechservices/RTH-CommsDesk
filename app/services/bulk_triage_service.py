from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    AutomationCandidate,
    BulkTriageActionLog,
    BulkTriageActionLogItem,
    CandidateStatus,
    Contact,
    Message,
    MessageClassification,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
)
from app.services.contact_service import (
    SUPPORTED_RELATIONSHIP_TYPES,
    find_contact_by_sender_email,
    normalize_email,
)

@dataclass(frozen=True)
class BulkBacklogPage:
    items: list[AttentionItem]
    total_count: int
    page: int
    page_size: int
    reviewed_count: int
    dismissed_count: int


def get_bulk_backlog_page(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 100,
    queue_filter: str = "unreviewed",
) -> BulkBacklogPage:
    page = max(page, 1)
    page_size = min(max(page_size, 10), 250)
    query = (
        db.query(AttentionItem)
        .outerjoin(Message, AttentionItem.message_id == Message.id)
        .outerjoin(MessageClassification, MessageClassification.message_id == Message.id)
    )
    query = _apply_queue_filter(db, query, queue_filter)
    total_count = query.count()
    rows = (
        query.order_by(
            AttentionItem.updated_at.desc(),
            AttentionItem.attention_score.desc(),
            AttentionItem.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    reviewed_count = (
        db.query(func.count(AttentionItem.id))
        .filter(AttentionItem.status == AttentionStatus.REVIEWED)
        .scalar()
        or 0
    )
    dismissed_count = (
        db.query(func.count(AttentionItem.id))
        .filter(AttentionItem.status == AttentionStatus.DISMISSED)
        .scalar()
        or 0
    )
    return BulkBacklogPage(
        items=rows,
        total_count=total_count,
        page=page,
        page_size=page_size,
        reviewed_count=reviewed_count,
        dismissed_count=dismissed_count,
    )


def refresh_automation_candidates(db: Session) -> int:
    rows = (
        db.query(Message, MessageClassification, AttentionItem)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .outerjoin(AttentionItem, AttentionItem.message_id == Message.id)
        .order_by(Message.received_at.desc(), Message.id.desc())
        .all()
    )
    low_value_sender_counts: dict[str, int] = {}
    for message, classification, _ in rows:
        sender = normalize_email(message.sender_email)
        if not sender:
            continue
        if (
            classification.is_newsletter
            or classification.is_marketing
            or classification.is_group_noise
            or classification.is_system_notification
        ):
            low_value_sender_counts[sender] = low_value_sender_counts.get(sender, 0) + 1

    changed = 0
    for message, classification, attention in rows:
        sender = normalize_email(message.sender_email)
        sender_repeat = low_value_sender_counts.get(sender or "", 0)
        text = f"{message.subject or ''} {message.snippet or ''} {message.body_text or ''}".lower()
        has_unsubscribe = bool(
            re.search(r"\bunsubscribe\b|\bmanage preferences\b|\bopt out\b|\bemail preferences\b", text)
        )
        is_noisey = (
            classification.is_newsletter
            or classification.is_marketing
            or classification.is_group_noise
            or classification.is_system_notification
        )
        if is_noisey and sender_repeat >= 3:
            changed += _upsert_candidate(
                db,
                message=message,
                candidate_type=ProposedActionType.MARK_NOISE,
                confidence=Decimal("0.8400"),
                reason=f"Sender appears repeatedly low-value ({sender_repeat} matching messages).",
            )
        if is_noisey and has_unsubscribe:
            changed += _upsert_candidate(
                db,
                message=message,
                candidate_type=ProposedActionType.UNSUBSCRIBE_REVIEW,
                confidence=Decimal("0.9100"),
                reason="Stored message text contains unsubscribe or preference-management language.",
            )
        stale_days = _message_age_days(message)
        low_engagement = message.is_unread and stale_days >= 30 and not classification.requires_reply
        if low_engagement and (attention.attention_score if attention else 0) <= 35:
            changed += _upsert_candidate(
                db,
                message=message,
                candidate_type=ProposedActionType.ARCHIVE_CANDIDATE,
                confidence=Decimal("0.7300"),
                reason=(
                    "Message appears low-engagement (unread, older than 30 days, and low attention)."
                ),
            )
        if low_engagement and stale_days >= 120 and is_noisey:
            changed += _upsert_candidate(
                db,
                message=message,
                candidate_type=ProposedActionType.DELETE_CANDIDATE,
                confidence=Decimal("0.6800"),
                reason=(
                    "Message appears stale low-value backlog (noise-like and older than 120 days)."
                ),
            )

    db.commit()
    return changed


def automation_candidates_for_dashboard(db: Session, *, limit: int = 200) -> list[AutomationCandidate]:
    return (
        db.query(AutomationCandidate)
        .filter(AutomationCandidate.status == CandidateStatus.PENDING)
        .order_by(AutomationCandidate.confidence.desc(), AutomationCandidate.updated_at.desc())
        .limit(limit)
        .all()
    )


def apply_bulk_action(
    db: Session,
    *,
    attention_ids: list[int],
    action_type: str,
    queue_filter: str | None = None,
    relationship_type: str | None = None,
) -> BulkTriageActionLog:
    if not attention_ids:
        raise ValueError("No attention items selected")
    action = action_type.strip().lower()
    if action not in {
        "mark_reviewed",
        "mark_noise",
        "mark_important",
        "assign_relationship",
        "approve_no_response_needed",
    }:
        raise ValueError("Unsupported bulk action")
    if action == "assign_relationship":
        normalized_relationship = (relationship_type or "").strip().lower()
        if normalized_relationship not in SUPPORTED_RELATIONSHIP_TYPES:
            raise ValueError("Unsupported relationship type")

    action_log = BulkTriageActionLog(
        action_type=action,
        queue_filter=queue_filter,
        item_count=0,
    )
    db.add(action_log)
    db.flush()

    items = db.query(AttentionItem).filter(AttentionItem.id.in_(attention_ids)).all()
    changed = 0
    for item in items:
        if action in {"mark_reviewed", "mark_noise", "mark_important"}:
            changed += _apply_status_bulk_action(db, action_log, item, action)
        elif action == "assign_relationship":
            changed += _apply_relationship_bulk_action(db, action_log, item, relationship_type or "unknown")
        elif action == "approve_no_response_needed":
            changed += _apply_no_response_approval(db, action_log, item)

    action_log.item_count = changed
    db.commit()
    db.refresh(action_log)
    return action_log


def undo_bulk_action(db: Session, action_log_id: int) -> BulkTriageActionLog:
    action_log = db.get(BulkTriageActionLog, action_log_id)
    if not action_log:
        raise ValueError("Bulk action log not found")
    if action_log.is_undone:
        raise ValueError("Bulk action has already been undone")

    entries = (
        db.query(BulkTriageActionLogItem)
        .filter(BulkTriageActionLogItem.action_log_id == action_log_id)
        .order_by(BulkTriageActionLogItem.id.desc())
        .all()
    )
    for entry in entries:
        previous = json.loads(entry.previous_value) if entry.previous_value else {}
        if entry.entity_type == "attention_item":
            item = db.get(AttentionItem, entry.entity_id)
            if not item:
                continue
            if "status" in previous:
                item.status = AttentionStatus(previous["status"])
            if "attention_score" in previous:
                item.attention_score = int(previous["attention_score"])
        elif entry.entity_type == "contact":
            contact = db.get(Contact, entry.entity_id)
            if contact and "relationship_type" in previous:
                contact.relationship_type = previous["relationship_type"]
        elif entry.entity_type == "review_package":
            package = db.get(ProposedActionReviewPackage, entry.entity_id)
            if package and "status" in previous:
                package.status = ReviewPackageStatus(previous["status"])
    action_log.is_undone = True
    db.commit()
    db.refresh(action_log)
    return action_log


def _apply_queue_filter(db: Session, query, queue_filter: str):
    normalized = (queue_filter or "unreviewed").strip().lower()
    if normalized in {"unreviewed", "active"}:
        return query.filter(AttentionItem.status == AttentionStatus.NEW)
    if normalized == "needs_reply":
        return query.filter(
            AttentionItem.status == AttentionStatus.NEW,
            MessageClassification.requires_reply.is_(True),
        )
    if normalized == "important":
        return query.filter(
            AttentionItem.status == AttentionStatus.NEW,
            or_(AttentionItem.attention_score >= 60, MessageClassification.urgency_level >= 2),
        )
    if normalized == "reviewed":
        return query.filter(AttentionItem.status == AttentionStatus.REVIEWED)
    if normalized == "proposed_actions":
        return query.join(
            ProposedActionReviewPackage,
            ProposedActionReviewPackage.message_id == AttentionItem.message_id,
        ).filter(ProposedActionReviewPackage.status == ReviewPackageStatus.PENDING)
    if normalized in {"noise_candidates", "unsubscribe_candidates"}:
        candidate_type = (
            ProposedActionType.UNSUBSCRIBE_REVIEW
            if normalized == "unsubscribe_candidates"
            else ProposedActionType.MARK_NOISE
        )
        return query.join(
            AutomationCandidate,
            AutomationCandidate.message_id == AttentionItem.message_id,
        ).filter(
            AutomationCandidate.candidate_type == candidate_type,
            AutomationCandidate.status == CandidateStatus.PENDING,
        )
    return query.filter(AttentionItem.status == AttentionStatus.NEW)


def _upsert_candidate(
    db: Session,
    *,
    message: Message,
    candidate_type: ProposedActionType,
    confidence: Decimal,
    reason: str,
) -> int:
    candidate = (
        db.query(AutomationCandidate)
        .filter(
            AutomationCandidate.message_id == message.id,
            AutomationCandidate.candidate_type == candidate_type,
        )
        .first()
    )
    if not candidate:
        candidate = AutomationCandidate(
            message_id=message.id,
            thread_id=message.thread_id,
            contact_id=message.thread.contact_id if message.thread else None,
            candidate_type=candidate_type,
            reason=reason,
            confidence=confidence,
            status=CandidateStatus.PENDING,
        )
        db.add(candidate)
        return 1
    candidate.reason = reason
    candidate.confidence = confidence
    candidate.updated_at = datetime.now(UTC)
    if candidate.status == CandidateStatus.UNDONE:
        candidate.status = CandidateStatus.PENDING
    return 1


def _message_age_days(message: Message) -> int:
    received_at = message.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - received_at).days, 0)


def _log_action_item(
    db: Session,
    *,
    action_log: BulkTriageActionLog,
    entity_type: str,
    entity_id: int,
    previous_value: dict,
    new_value: dict,
) -> None:
    db.add(
        BulkTriageActionLogItem(
            action_log_id=action_log.id,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_value=json.dumps(previous_value),
            new_value=json.dumps(new_value),
        )
    )


def _apply_status_bulk_action(
    db: Session,
    action_log: BulkTriageActionLog,
    item: AttentionItem,
    action: str,
) -> int:
    previous = {"status": item.status.value, "attention_score": item.attention_score}
    if action == "mark_reviewed":
        item.status = AttentionStatus.REVIEWED
    elif action == "mark_noise":
        item.status = AttentionStatus.DISMISSED
    elif action == "mark_important":
        item.status = AttentionStatus.NEW
        item.attention_score = max(item.attention_score, 70)
    else:
        return 0
    new_value = {"status": item.status.value, "attention_score": item.attention_score}
    _log_action_item(
        db,
        action_log=action_log,
        entity_type="attention_item",
        entity_id=item.id,
        previous_value=previous,
        new_value=new_value,
    )
    return 1


def _apply_relationship_bulk_action(
    db: Session,
    action_log: BulkTriageActionLog,
    item: AttentionItem,
    relationship_type: str,
) -> int:
    message = item.message
    if not message:
        return 0
    contact = message.thread.contact if message.thread and message.thread.contact else None
    if contact is None and message.sender_email:
        contact = find_contact_by_sender_email(db, message.sender_email)
    if not contact:
        return 0
    previous = {"relationship_type": contact.relationship_type or "unknown"}
    contact.relationship_type = relationship_type
    new_value = {"relationship_type": contact.relationship_type}
    _log_action_item(
        db,
        action_log=action_log,
        entity_type="contact",
        entity_id=contact.id,
        previous_value=previous,
        new_value=new_value,
    )
    return 1


def _apply_no_response_approval(
    db: Session,
    action_log: BulkTriageActionLog,
    item: AttentionItem,
) -> int:
    if not item.message_id:
        return 0
    package = (
        db.query(ProposedActionReviewPackage)
        .filter(
            ProposedActionReviewPackage.message_id == item.message_id,
            ProposedActionReviewPackage.action_type == ProposedActionType.NO_RESPONSE_NEEDED,
        )
        .order_by(ProposedActionReviewPackage.updated_at.desc(), ProposedActionReviewPackage.id.desc())
        .first()
    )
    if not package:
        return 0
    previous = {"status": package.status.value}
    package.status = ReviewPackageStatus.APPROVED
    new_value = {"status": package.status.value}
    _log_action_item(
        db,
        action_log=action_log,
        entity_type="review_package",
        entity_id=package.id,
        previous_value=previous,
        new_value=new_value,
    )
    return 1
