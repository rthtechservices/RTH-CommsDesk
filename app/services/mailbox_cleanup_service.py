"""Mailbox cleanup service — sender/domain rollup analysis and cleanup workflow.

Analyzes synced messages to build sender-level cleanup candidates with:
- Classification mix (marketing, newsletter, noise, requires-reply, etc.)
- Protection rules (VIP, client/partner/vendor, requires-reply, human-personal)
- Confidence scoring and action recommendations
- Execution record preparation for label/archive operations

All external Gmail operations must go through execution_service, not direct calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    ExecutionActionType,
    ExecutionRecord,
    ExecutionStatus,
    MailboxCleanupAction,
    MailboxCleanupActionLog,
    MailboxCleanupCandidate,
    MailboxCleanupStatus,
    Message,
    MessageClassification,
    utcnow,
)
from app.services.contact_service import find_contact_by_sender_email, mark_contact_noise

# ─── constants ───────────────────────────────────────────────────────────────

PREFERRED_CLEANUP_LABELS: dict[str, str] = {
    "noise": "RTH-Cleanup/Noise",
    "marketing": "RTH-Cleanup/Marketing",
    "newsletter": "RTH-Cleanup/Newsletter",
    "delete_candidate": "RTH-Cleanup/Delete Candidate",
}

# Relationship types that require explicit human review before cleanup
PROTECTED_RELATIONSHIP_TYPES = frozenset(
    {
        "client",
        "partner",
        "vendor",
        "professional",
        "vip",
        "important",
        "employer",
        "employee",
        "colleague",
    }
)

_UNSUBSCRIBE_RE = re.compile(
    r"\bunsubscribe\b|\bmanage preferences\b|\bopt.?out\b|\bemail preferences\b",
    re.IGNORECASE,
)

RECENT_PERSONAL_DAYS = 120
HIGH_CONFIDENCE_THRESHOLD = Decimal("0.8000")
DELETE_CANDIDATE_MIN_CONFIDENCE = Decimal("0.8500")
DELETE_CANDIDATE_MIN_MESSAGES = 5


# ─── public dataclasses ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class CleanupDashboardStats:
    total_candidates: int
    high_confidence_count: int
    protected_count: int
    pending_execution_count: int


@dataclass(frozen=True)
class CleanupCandidateSummary:
    total_cleanup_candidates: int
    high_confidence_candidates: int
    protected_candidates: int
    gmail_label_capable_candidates: int
    gmail_archive_capable_candidates: int
    delete_candidates: int
    blocked_candidates: int


# ─── public functions ─────────────────────────────────────────────────────────


def build_cleanup_rollups(db: Session) -> int:
    """Scan synced messages and upsert MailboxCleanupCandidate rollups per sender.

    Returns the number of candidates created or updated.
    """
    rows = (
        db.query(Message, MessageClassification)
        .join(MessageClassification, MessageClassification.message_id == Message.id)
        .filter(
            Message.sender_email.is_not(None),
            Message.source_type == "gmail",
        )
        .order_by(Message.sender_email, Message.received_at)
        .all()
    )

    # Group by normalized sender email
    from app.services.contact_service import normalize_email

    buckets: dict[str, list[tuple[Message, MessageClassification]]] = {}
    for msg, cls in rows:
        key = normalize_email(msg.sender_email) or msg.sender_email or ""
        if not key:
            continue
        buckets.setdefault(key, []).append((msg, cls))

    changed = 0
    for sender_key, items in buckets.items():
        candidate = _build_candidate_from_items(db, sender_key, items)
        existing = (
            db.query(MailboxCleanupCandidate)
            .filter(MailboxCleanupCandidate.sender_key == sender_key)
            .first()
        )
        if existing:
            # Only update rollup fields; preserve status/protection set by operator
            _update_candidate_fields(existing, candidate)
            changed += 1
        else:
            db.add(candidate)
            changed += 1

    db.commit()
    return changed


def get_cleanup_candidates(
    db: Session,
    *,
    status_filter: str | None = None,
    limit: int = 200,
) -> list[MailboxCleanupCandidate]:
    """Return cleanup candidates ordered by confidence descending."""
    query = db.query(MailboxCleanupCandidate)
    if status_filter == "pending":
        query = query.filter(MailboxCleanupCandidate.status == MailboxCleanupStatus.PENDING)
    elif status_filter == "protected":
        query = query.filter(MailboxCleanupCandidate.status == MailboxCleanupStatus.PROTECTED)
    elif status_filter == "all":
        pass
    else:
        # Default: show pending + approved (actionable)
        query = query.filter(
            MailboxCleanupCandidate.status.in_(
                [MailboxCleanupStatus.PENDING, MailboxCleanupStatus.APPROVED]
            )
        )
    return (
        query.order_by(
            MailboxCleanupCandidate.confidence_score.desc(),
            MailboxCleanupCandidate.total_message_count.desc(),
            MailboxCleanupCandidate.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )


def get_cleanup_candidate(db: Session, candidate_id: int) -> MailboxCleanupCandidate | None:
    return db.get(MailboxCleanupCandidate, candidate_id)


def mark_sender_noise_local(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> MailboxCleanupCandidate:
    """Mark a cleanup candidate's sender as noise locally and update contact status."""
    candidate = _require_candidate(db, candidate_id)
    _require_not_protected(candidate)

    previous_status = candidate.status.value

    # Update contact record
    if candidate.sender_email:
        try:
            mark_contact_noise(db, candidate.sender_email)
        except ValueError:
            pass  # contact could not be created — non-fatal

    # Update candidate
    candidate.status = MailboxCleanupStatus.APPROVED
    candidate.recommended_action = MailboxCleanupAction.MARK_SENDER_NOISE_LOCAL
    candidate.is_protected = False
    _log_action(
        db,
        candidate,
        action="mark_sender_noise_local",
        actor=actor,
        previous_status=previous_status,
        new_status=MailboxCleanupStatus.APPROVED.value,
        note="Sender marked as local noise. Contact status updated.",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def mark_sender_protected(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> MailboxCleanupCandidate:
    """Mark a cleanup candidate as protected. Suppresses future noise recommendations."""
    candidate = _require_candidate(db, candidate_id)
    previous_status = candidate.status.value

    candidate.status = MailboxCleanupStatus.PROTECTED
    candidate.is_protected = True
    candidate.recommended_action = MailboxCleanupAction.SKIP_PROTECTED_SENDER

    # If there is a contact, ensure it is not marked as noise
    if candidate.sender_email:
        contact = find_contact_by_sender_email(db, candidate.sender_email)
        if contact and contact.is_noise:
            contact.is_noise = False
            db.add(contact)

    _log_action(
        db,
        candidate,
        action="mark_sender_protected",
        actor=actor,
        previous_status=previous_status,
        new_status=MailboxCleanupStatus.PROTECTED.value,
        note="Sender marked as protected. Future cleanup recommendations suppressed.",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def mark_sender_not_noise(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> MailboxCleanupCandidate:
    """Reset a cleanup candidate to pending review (undo noise/protected decision)."""
    candidate = _require_candidate(db, candidate_id)
    previous_status = candidate.status.value

    candidate.status = MailboxCleanupStatus.PENDING
    candidate.is_protected = False
    _log_action(
        db,
        candidate,
        action="mark_sender_not_noise",
        actor=actor,
        previous_status=previous_status,
        new_status=MailboxCleanupStatus.PENDING.value,
        note="Sender cleanup decision reset to pending.",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def prepare_cleanup_label_execution(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> ExecutionRecord:
    """Prepare an execution record to apply a cleanup label to all sender messages."""
    candidate = _require_candidate(db, candidate_id)
    _require_not_protected(candidate)
    label = candidate.recommended_gmail_label or PREFERRED_CLEANUP_LABELS["noise"]
    message_ids = _get_source_message_ids(db, candidate)
    payload = _cleanup_payload(candidate, "cleanup_label", label, message_ids)
    record = _make_execution_record(db, candidate, payload, actor)
    candidate.last_execution_record_id = record.id
    candidate.status = MailboxCleanupStatus.APPROVED
    _log_action(
        db,
        candidate,
        action="prepare_cleanup_label_execution",
        actor=actor,
        previous_status=MailboxCleanupStatus.PENDING.value,
        new_status=MailboxCleanupStatus.APPROVED.value,
        note=f"Prepared label execution. Label: {label}. Messages: {len(message_ids)}.",
        execution_record_id=record.id,
    )
    db.commit()
    db.refresh(record)
    return record


def prepare_cleanup_archive_execution(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> ExecutionRecord:
    """Prepare an execution record to archive all sender messages."""
    candidate = _require_candidate(db, candidate_id)
    _require_not_protected(candidate)
    message_ids = _get_source_message_ids(db, candidate)
    payload = _cleanup_payload(candidate, "cleanup_archive", None, message_ids)
    record = _make_execution_record(db, candidate, payload, actor)
    candidate.last_execution_record_id = record.id
    candidate.status = MailboxCleanupStatus.APPROVED
    _log_action(
        db,
        candidate,
        action="prepare_cleanup_archive_execution",
        actor=actor,
        previous_status=MailboxCleanupStatus.PENDING.value,
        new_status=MailboxCleanupStatus.APPROVED.value,
        note=f"Prepared archive execution. Messages: {len(message_ids)}.",
        execution_record_id=record.id,
    )
    db.commit()
    db.refresh(record)
    return record


def prepare_cleanup_label_and_archive_execution(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> ExecutionRecord:
    """Prepare an execution record to label and archive all sender messages."""
    candidate = _require_candidate(db, candidate_id)
    _require_not_protected(candidate)
    label = candidate.recommended_gmail_label or PREFERRED_CLEANUP_LABELS["noise"]
    message_ids = _get_source_message_ids(db, candidate)
    payload = _cleanup_payload(candidate, "cleanup_label_and_archive", label, message_ids)
    record = _make_execution_record(db, candidate, payload, actor)
    candidate.last_execution_record_id = record.id
    candidate.status = MailboxCleanupStatus.APPROVED
    _log_action(
        db,
        candidate,
        action="prepare_cleanup_label_and_archive_execution",
        actor=actor,
        previous_status=MailboxCleanupStatus.PENDING.value,
        new_status=MailboxCleanupStatus.APPROVED.value,
        note=f"Prepared label+archive execution. Label: {label}. Messages: {len(message_ids)}.",
        execution_record_id=record.id,
    )
    db.commit()
    db.refresh(record)
    return record


def mark_delete_candidate_local(
    db: Session,
    candidate_id: int,
    *,
    actor: str = "local-user",
) -> MailboxCleanupCandidate:
    """Mark a candidate as a delete candidate (local/review only — no Gmail mutation)."""
    candidate = _require_candidate(db, candidate_id)
    _require_not_protected(candidate)
    if (candidate.confidence_score or Decimal("0.0")) < DELETE_CANDIDATE_MIN_CONFIDENCE:
        raise ValueError(
            "Delete candidate is blocked until confidence is very high. "
            "Use label/archive review first."
        )
    if candidate.total_message_count < DELETE_CANDIDATE_MIN_MESSAGES:
        raise ValueError(
            "Delete candidate is blocked for low-volume senders. "
            "Require repeated low-value evidence first."
        )
    previous_status = candidate.status.value
    candidate.recommended_action = MailboxCleanupAction.PREPARE_DELETE_CANDIDATE
    candidate.recommended_gmail_label = PREFERRED_CLEANUP_LABELS["delete_candidate"]
    # Promote to label-and-archive with delete-candidate label as the closest safe action
    # Direct delete/trash is NOT executed here — it is review-only
    _log_action(
        db,
        candidate,
        action="mark_delete_candidate_local",
        actor=actor,
        previous_status=previous_status,
        new_status=candidate.status.value,
        note=(
            "Marked as delete candidate (local review only). "
            "Use prepare_label to apply RTH-Cleanup/Delete Candidate label when ready."
        ),
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def cleanup_dashboard_stats(db: Session) -> CleanupDashboardStats:
    """Return lightweight counts for the dashboard card."""
    total = db.query(func.count(MailboxCleanupCandidate.id)).scalar() or 0
    high_conf = (
        db.query(func.count(MailboxCleanupCandidate.id))
        .filter(
            MailboxCleanupCandidate.confidence_score >= HIGH_CONFIDENCE_THRESHOLD,
            MailboxCleanupCandidate.status == MailboxCleanupStatus.PENDING,
            MailboxCleanupCandidate.is_protected.is_(False),
        )
        .scalar()
        or 0
    )
    protected = (
        db.query(func.count(MailboxCleanupCandidate.id))
        .filter(MailboxCleanupCandidate.status == MailboxCleanupStatus.PROTECTED)
        .scalar()
        or 0
    )
    pending_exec = (
        db.query(func.count(MailboxCleanupCandidate.id))
        .filter(
            MailboxCleanupCandidate.last_execution_record_id.is_not(None),
            MailboxCleanupCandidate.status == MailboxCleanupStatus.APPROVED,
        )
        .scalar()
        or 0
    )
    return CleanupDashboardStats(
        total_candidates=total,
        high_confidence_count=high_conf,
        protected_count=protected,
        pending_execution_count=pending_exec,
    )


def cleanup_candidate_summary(db: Session) -> CleanupCandidateSummary:
    """Return sender-rollup counts used by smoke scripts and readiness checks."""
    candidates = db.query(MailboxCleanupCandidate).all()
    total = len(candidates)
    blocked = [
        c
        for c in candidates
        if c.is_protected or c.status in {MailboxCleanupStatus.PROTECTED, MailboxCleanupStatus.FAILED}
    ]
    actionable = [c for c in candidates if c not in blocked]
    return CleanupCandidateSummary(
        total_cleanup_candidates=total,
        high_confidence_candidates=len(
            [
                c
                for c in actionable
                if (c.confidence_score or Decimal("0.0")) >= HIGH_CONFIDENCE_THRESHOLD
            ]
        ),
        protected_candidates=len(
            [c for c in candidates if c.status == MailboxCleanupStatus.PROTECTED]
        ),
        gmail_label_capable_candidates=len(
            [
                c
                for c in actionable
                if c.recommended_action
                in {
                    MailboxCleanupAction.APPLY_GMAIL_LABEL,
                    MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
                }
            ]
        ),
        gmail_archive_capable_candidates=len(
            [
                c
                for c in actionable
                if c.recommended_action
                in {
                    MailboxCleanupAction.ARCHIVE_GMAIL,
                    MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
                }
            ]
        ),
        delete_candidates=len(
            [
                c
                for c in candidates
                if c.recommended_action == MailboxCleanupAction.PREPARE_DELETE_CANDIDATE
            ]
        ),
        blocked_candidates=len(blocked),
    )


def action_logs_for_candidate(
    db: Session, candidate_id: int
) -> list[MailboxCleanupActionLog]:
    return (
        db.query(MailboxCleanupActionLog)
        .filter(MailboxCleanupActionLog.candidate_id == candidate_id)
        .order_by(MailboxCleanupActionLog.created_at.desc())
        .all()
    )


LARGE_BATCH_THRESHOLD = 50  # Extra confirmation copy shown above this message count


def cleanup_execution_details(payload: dict | None, settings_or_posture: "dict | None" = None) -> dict:
    """Return operator-facing confirmation details for a cleanup execution payload.

    Used by execution_detail template to show exactly what will happen before
    approve/confirm, including recovery guidance.

    Args:
        payload: The execution record's parsed payload_json dict.
        settings_or_posture: Optional posture dict from cleanup_execution_posture().
            If omitted, details still show what is in the payload.

    Returns a dict with keys:
        sender_email, sender_domain, message_count, cleanup_mode, label_name,
        archive, permanent_delete, dry_run_mode, posture_label, feature_flags,
        protection_status, large_batch_warning, audit_statement, recovery_guidance
    """
    if not payload:
        return {}

    mode = payload.get("cleanup_mode", "")
    if not mode:
        return {}
    label_name = payload.get("cleanup_label_name") or None
    sender_email = payload.get("sender_email") or payload.get("sender_key") or "-"
    sender_domain = payload.get("sender_domain") or (
        sender_email.split("@")[1] if "@" in sender_email else "-"
    )
    message_count = len(payload.get("source_message_ids") or [])
    is_label = mode in {"cleanup_label", "cleanup_label_and_archive"}
    is_archive = mode in {"cleanup_archive", "cleanup_label_and_archive"}

    posture = settings_or_posture or {}
    dry_run_mode = posture.get("dry_run", False)
    posture_label = posture.get("label", "Unknown posture")

    large_batch_warning = message_count > LARGE_BATCH_THRESHOLD

    # Use a local variable so the label can be safely embedded in f-strings
    _label_for_search = label_name or "RTH-Cleanup"

    # Recovery guidance varies by mode
    if mode == "cleanup_label":
        recovery = (
            f"Recovery: In Gmail, search for 'label:{_label_for_search}' "
            f"to find labelled messages from {sender_email}. "
            "Select all → Remove label. Messages remain in your inbox."
        )
    elif mode == "cleanup_archive":
        recovery = (
            f"Recovery: In Gmail, search 'from:{sender_email} in:archive' "
            "to find archived messages. Select all → Move to inbox."
        )
    elif mode == "cleanup_label_and_archive":
        recovery = (
            f"Recovery: In Gmail, search 'label:{_label_for_search} from:{sender_email}' "
            "to find labelled archived messages. "
            "The label makes finding them easier. "
            "Select all → Move to inbox → Remove label."
        )
    else:
        recovery = "Recovery path unavailable for this cleanup mode."

    _write_note = "Dry-run: no external Gmail write will occur." if dry_run_mode else "Live: Gmail will be modified after confirmation."
    audit_statement = (
        f"This execution will be recorded in the audit trail. "
        f"Mode: {mode}. Messages: {message_count}. Sender: {sender_email}. "
        f"Permanent delete: no. {_write_note}"
    )

    return {
        "sender_email": sender_email,
        "sender_domain": sender_domain,
        "message_count": message_count,
        "cleanup_mode": mode,
        "label_name": label_name,
        "archive": is_archive,
        "permanent_delete": False,
        "dry_run_mode": dry_run_mode,
        "posture_label": posture_label,
        "large_batch_warning": large_batch_warning,
        "audit_statement": audit_statement,
        "recovery_guidance": recovery,
        "is_label": is_label,
        "is_archive": is_archive,
    }


# ─── private helpers ──────────────────────────────────────────────────────────


def _build_candidate_from_items(
    db: Session,
    sender_key: str,
    items: list[tuple[Message, MessageClassification]],
) -> MailboxCleanupCandidate:
    """Build a MailboxCleanupCandidate from a list of (Message, Classification) tuples."""
    messages = [m for m, _ in items]
    classifications = [c for _, c in items]

    sender_email = messages[0].sender_email
    sender_display_name = next(
        (m.sender_display_name for m in messages if m.sender_display_name), None
    )
    sender_domain = _extract_domain(sender_email)

    total = len(messages)
    unread = sum(1 for m in messages if m.is_unread)
    oldest = min((m.received_at for m in messages if m.received_at), default=None)
    newest = max((m.received_at for m in messages if m.received_at), default=None)

    marketing = sum(1 for c in classifications if c.is_marketing)
    newsletter = sum(1 for c in classifications if c.is_newsletter)
    group_noise = sum(1 for c in classifications if c.is_group_noise)
    system_notif = sum(1 for c in classifications if c.is_system_notification)
    requires_reply = sum(1 for c in classifications if c.requires_reply)
    human_personal = sum(1 for c in classifications if c.is_human_personal)
    client_work = sum(1 for c in classifications if c.is_client_work)

    recent_cutoff = datetime.now(UTC) - timedelta(days=RECENT_PERSONAL_DAYS)

    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    recent_human_personal = sum(
        1
        for m, c in items
        if c.is_human_personal
        and (received_at := _as_utc(m.received_at))
        and received_at >= recent_cutoff
    )

    unsubscribe_count = 0
    for m in messages:
        text = f"{m.subject or ''} {m.snippet or ''} {m.body_text or ''}".lower()
        if _UNSUBSCRIBE_RE.search(text):
            unsubscribe_count += 1

    # Contact lookup
    contact = find_contact_by_sender_email(db, sender_email)
    is_vip = bool(contact and contact.is_vip)
    is_noise_contact = bool(contact and contact.is_noise)
    relationship = (contact.relationship_type or "unknown") if contact else "unknown"
    is_protected_relationship = relationship.lower() in PROTECTED_RELATIONSHIP_TYPES

    vip_count = 1 if is_vip else 0

    # Protection rules
    is_protected = (
        is_vip
        or is_protected_relationship
        or client_work > 0
        or requires_reply > 0
        or recent_human_personal > 0
    )

    # Scoring
    confidence, recommended_action, label = _score_candidate(
        total=total,
        marketing=marketing,
        newsletter=newsletter,
        group_noise=group_noise,
        system_notif=system_notif,
        unsubscribe_count=unsubscribe_count,
        requires_reply=requires_reply,
        human_personal=human_personal,
        client_work=client_work,
        recent_human_personal=recent_human_personal,
        is_vip=is_vip,
        is_protected_relationship=is_protected_relationship,
        is_noise_contact=is_noise_contact,
    )

    if is_protected:
        recommended_action = MailboxCleanupAction.SKIP_PROTECTED_SENDER
        confidence = Decimal("0.0")
        label = None

    # Sample subjects
    sample_subjects = list(
        dict.fromkeys(
            s for s in (m.subject for m in reversed(messages)) if s
        )
    )[:5]

    evidence = _build_evidence_summary(
        total=total,
        unread=unread,
        marketing=marketing,
        newsletter=newsletter,
        group_noise=group_noise,
        system_notif=system_notif,
        unsubscribe_count=unsubscribe_count,
        requires_reply=requires_reply,
        human_personal=human_personal,
        client_work=client_work,
        recent_human_personal=recent_human_personal,
        is_vip=is_vip,
        is_protected_relationship=is_protected_relationship,
        is_noise_contact=is_noise_contact,
    )

    return MailboxCleanupCandidate(
        sender_key=sender_key,
        sender_email=sender_email,
        sender_display_name=sender_display_name,
        sender_domain=sender_domain,
        source_type="gmail",
        total_message_count=total,
        unread_count=unread,
        oldest_received_at=oldest,
        newest_received_at=newest,
        marketing_count=marketing,
        newsletter_count=newsletter,
        group_noise_count=group_noise,
        system_notification_count=system_notif,
        unsubscribe_language_count=unsubscribe_count,
        requires_reply_count=requires_reply,
        human_personal_count=human_personal,
        vip_contact_count=vip_count,
        is_protected=is_protected,
        contact_id=contact.id if contact else None,
        existing_contact_is_vip=is_vip,
        existing_contact_is_noise=is_noise_contact,
        existing_contact_relationship=relationship,
        confidence_score=confidence,
        recommended_action=recommended_action,
        recommended_gmail_label=label,
        evidence_summary=evidence,
        sample_subjects_json=json.dumps(sample_subjects),
        status=MailboxCleanupStatus.PROTECTED if is_protected else MailboxCleanupStatus.PENDING,
    )


def _update_candidate_fields(
    existing: MailboxCleanupCandidate,
    fresh: MailboxCleanupCandidate,
) -> None:
    """Update rollup fields on an existing candidate, preserving operator decisions."""
    existing.sender_display_name = fresh.sender_display_name
    existing.sender_domain = fresh.sender_domain
    existing.total_message_count = fresh.total_message_count
    existing.unread_count = fresh.unread_count
    existing.oldest_received_at = fresh.oldest_received_at
    existing.newest_received_at = fresh.newest_received_at
    existing.marketing_count = fresh.marketing_count
    existing.newsletter_count = fresh.newsletter_count
    existing.group_noise_count = fresh.group_noise_count
    existing.system_notification_count = fresh.system_notification_count
    existing.unsubscribe_language_count = fresh.unsubscribe_language_count
    existing.requires_reply_count = fresh.requires_reply_count
    existing.human_personal_count = fresh.human_personal_count
    existing.vip_contact_count = fresh.vip_contact_count
    existing.contact_id = fresh.contact_id
    existing.existing_contact_is_vip = fresh.existing_contact_is_vip
    existing.existing_contact_is_noise = fresh.existing_contact_is_noise
    existing.existing_contact_relationship = fresh.existing_contact_relationship
    existing.evidence_summary = fresh.evidence_summary
    existing.sample_subjects_json = fresh.sample_subjects_json

    # Only update protection/confidence/recommendation if not already operator-set
    if existing.status == MailboxCleanupStatus.PENDING:
        existing.confidence_score = fresh.confidence_score
        existing.recommended_action = fresh.recommended_action
        existing.recommended_gmail_label = fresh.recommended_gmail_label
        existing.is_protected = fresh.is_protected
        if fresh.is_protected:
            existing.status = MailboxCleanupStatus.PROTECTED


def _score_candidate(
    *,
    total: int,
    marketing: int,
    newsletter: int,
    group_noise: int,
    system_notif: int,
    unsubscribe_count: int,
    requires_reply: int,
    human_personal: int,
    client_work: int,
    recent_human_personal: int,
    is_vip: bool,
    is_protected_relationship: bool,
    is_noise_contact: bool,
) -> tuple[Decimal, MailboxCleanupAction, str | None]:
    """Return (confidence_score, recommended_action, gmail_label)."""
    # Hard blockers
    if (
        is_vip
        or is_protected_relationship
        or client_work > 0
        or requires_reply > 0
        or recent_human_personal > 0
    ):
        return Decimal("0.0"), MailboxCleanupAction.SKIP_PROTECTED_SENDER, None

    if total < 2:
        return Decimal("0.1"), MailboxCleanupAction.REVIEW_ONLY, None

    noise_count = marketing + newsletter + group_noise + system_notif
    noise_ratio = noise_count / total if total else 0.0

    # Already marked noise
    if is_noise_contact:
        if total >= 5 and unsubscribe_count >= 1 and noise_ratio >= 0.75:
            return (
                Decimal("0.9500"),
                MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
                _pick_label(marketing, newsletter, group_noise, system_notif),
            )
        return (
            Decimal("0.8500"),
            MailboxCleanupAction.APPLY_GMAIL_LABEL,
            _pick_label(marketing, newsletter, group_noise, system_notif),
        )

    # High confidence requires repeated low-value evidence, not one-off noise.
    if total >= 6 and noise_ratio >= 0.85 and unsubscribe_count >= 2:
        return (
            Decimal("0.9300"),
            MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
            _pick_label(marketing, newsletter, group_noise, system_notif),
        )
    if total >= 5 and noise_ratio >= 0.75 and unsubscribe_count >= 1:
        return (
            Decimal("0.8200"),
            MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
            _pick_label(marketing, newsletter, group_noise, system_notif),
        )
    # Moderate confidence prefers label-only.
    if total >= 3 and noise_ratio >= 0.65:
        return (
            Decimal("0.7400"),
            MailboxCleanupAction.APPLY_GMAIL_LABEL,
            _pick_label(marketing, newsletter, group_noise, system_notif),
        )
    if total >= 2 and noise_ratio >= 0.5:
        return (
            Decimal("0.5800"),
            MailboxCleanupAction.APPLY_GMAIL_LABEL,
            _pick_label(marketing, newsletter, group_noise, system_notif),
        )
    if noise_ratio >= 0.3:
        return (
            Decimal("0.3500"),
            MailboxCleanupAction.MARK_SENDER_NOISE_LOCAL,
            None,
        )

    return Decimal("0.1500"), MailboxCleanupAction.REVIEW_ONLY, None


def _pick_label(marketing: int, newsletter: int, group_noise: int, system_notif: int) -> str:
    if newsletter >= marketing and newsletter >= group_noise and newsletter >= system_notif:
        return PREFERRED_CLEANUP_LABELS["newsletter"]
    if marketing >= group_noise and marketing >= system_notif:
        return PREFERRED_CLEANUP_LABELS["marketing"]
    return PREFERRED_CLEANUP_LABELS["noise"]


def _build_evidence_summary(
    *,
    total: int,
    unread: int,
    marketing: int,
    newsletter: int,
    group_noise: int,
    system_notif: int,
    unsubscribe_count: int,
    requires_reply: int,
    human_personal: int,
    client_work: int,
    recent_human_personal: int,
    is_vip: bool,
    is_protected_relationship: bool,
    is_noise_contact: bool,
) -> str:
    parts = [f"{total} total messages"]
    if unread:
        parts.append(f"{unread} unread")
    noise_parts = []
    if marketing:
        noise_parts.append(f"{marketing} marketing")
    if newsletter:
        noise_parts.append(f"{newsletter} newsletter")
    if group_noise:
        noise_parts.append(f"{group_noise} group-noise")
    if system_notif:
        noise_parts.append(f"{system_notif} system-notification")
    if noise_parts:
        parts.append("noise classifications: " + ", ".join(noise_parts))
    if unsubscribe_count:
        parts.append(f"unsubscribe language detected in {unsubscribe_count} messages")
    blockers = []
    if is_vip:
        blockers.append("VIP contact")
    if is_protected_relationship:
        blockers.append("protected relationship type")
    if client_work:
        blockers.append(f"{client_work} client-work messages")
    if requires_reply:
        blockers.append(f"{requires_reply} messages require reply")
    if recent_human_personal:
        blockers.append(f"{recent_human_personal} recent human-personal messages")
    elif human_personal:
        parts.append(f"historical human-personal messages: {human_personal}")
    if is_noise_contact:
        parts.append("contact already marked noise")
    if blockers:
        parts.append("BLOCKED: " + "; ".join(blockers))
    return " | ".join(parts)


def _extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower()


def _get_source_message_ids(db: Session, candidate: MailboxCleanupCandidate) -> list[str]:
    if not candidate.sender_email:
        return []
    messages = (
        db.query(Message.source_message_id)
        .filter(
            Message.source_type == "gmail",
            func.lower(Message.sender_email) == (candidate.sender_email or "").lower(),
            Message.source_message_id.is_not(None),
        )
        .order_by(Message.received_at.desc())
        .limit(500)
        .all()
    )
    return [row[0] for row in messages if row[0]]


def _cleanup_payload(
    candidate: MailboxCleanupCandidate,
    operation: str,
    label_name: str | None,
    message_ids: list[str],
) -> dict:
    return {
        "cleanup_mode": operation,
        "sender_email": candidate.sender_email,
        "sender_key": candidate.sender_key,
        "cleanup_candidate_id": candidate.id,
        "cleanup_label_name": label_name,
        "source_message_ids": message_ids,
        "message_count": len(message_ids),
        # Legacy field for execution_test_policy — label/archive actions are not email targets
        "operation": operation,
    }


def _make_execution_record(
    db: Session,
    candidate: MailboxCleanupCandidate,
    payload: dict,
    actor: str,
) -> ExecutionRecord:
    import json as _json

    record = ExecutionRecord(
        action_type=ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE,
        attempt_number=1,
        status=ExecutionStatus.PENDING_REVIEW,
        created_by=actor,
        payload_json=_json.dumps(payload),
        provider_name="mock",
    )
    db.add(record)
    db.flush()

    # Audit entry
    from app.models.entities import ExecutionAuditLog

    db.add(
        ExecutionAuditLog(
            execution_record_id=record.id,
            event_type="prepared",
            actor=actor,
            details=_json.dumps({"cleanup_candidate_id": candidate.id, "operation": payload.get("cleanup_mode")}),
        )
    )
    return record


def _log_action(
    db: Session,
    candidate: MailboxCleanupCandidate,
    *,
    action: str,
    actor: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    note: str | None = None,
    execution_record_id: int | None = None,
) -> None:
    db.add(
        MailboxCleanupActionLog(
            candidate_id=candidate.id,
            action=action,
            actor=actor,
            note=note,
            previous_status=previous_status,
            new_status=new_status,
            execution_record_id=execution_record_id,
            created_at=utcnow(),
        )
    )


def _require_candidate(db: Session, candidate_id: int) -> MailboxCleanupCandidate:
    candidate = db.get(MailboxCleanupCandidate, candidate_id)
    if not candidate:
        raise ValueError(f"Cleanup candidate {candidate_id} not found")
    return candidate


def _require_not_protected(candidate: MailboxCleanupCandidate) -> None:
    if candidate.status == MailboxCleanupStatus.PROTECTED:
        raise ValueError(
            f"Sender {candidate.sender_email!r} is marked protected. "
            "Use mark_sender_not_noise to reset before applying cleanup actions."
        )
