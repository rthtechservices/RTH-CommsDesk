"""Productivity stats service — life-to-date statistics and hours-saved estimate.

All stats are read-only except for the admin go-live baseline action.
Stats are persisted in the ``app_stat_records`` table and survive upgrades.

Hours-saved is a transparent, configurable estimate — not a fake precision stat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import (
    AppStatRecord,
    AttentionItem,
    AttentionStatus,
    BulkTriageActionLog,
    Contact,
    ConversationSummary,
    DraftReply,
    DraftStatus,
    ExecutionAuditLog,
    ProposedActionReviewPackage,
    utcnow,
)

# ---------------------------------------------------------------------------
# Configurable time-estimate assumptions (all in seconds unless noted)
# ---------------------------------------------------------------------------

MANUAL_REVIEW_SECONDS_PER_EMAIL: float = 12.0
MANUAL_BULK_CLEANUP_SETUP_SECONDS: float = 45.0
MANUAL_BULK_CLEANUP_SECONDS_PER_EMAIL: float = 3.0
MANUAL_BROWSER_OPEN_THREAD_SECONDS: float = 8.0
READING_WORDS_PER_MINUTE: float = 225.0
TYPING_WORDS_PER_MINUTE: float = 40.0
MANUAL_SEND_OVERHEAD_SECONDS: float = 20.0
AI_REVIEW_OVERHEAD_SECONDS: float = 10.0

# Stat keys used in the app_stat_records table
STAT_EMAILS_PROCESSED = "emails_processed"
STAT_EMAILS_DRAFTED = "emails_drafted"
STAT_EMAILS_DELETED = "emails_deleted"
STAT_SENDERS_NOISE = "senders_noise"
STAT_VIP_CONTACTS = "vip_contacts"
STAT_AI_CONTENT_ITEMS = "ai_content_items"
STAT_HOURS_SAVED = "hours_saved"

ALL_STAT_KEYS = [
    STAT_EMAILS_PROCESSED,
    STAT_EMAILS_DRAFTED,
    STAT_EMAILS_DELETED,
    STAT_SENDERS_NOISE,
    STAT_VIP_CONTACTS,
    STAT_AI_CONTENT_ITEMS,
    STAT_HOURS_SAVED,
]


@dataclass
class LifetimeStats:
    emails_processed: int = 0
    emails_drafted: int = 0
    emails_deleted: int = 0
    senders_noise: int = 0
    vip_contacts: int = 0
    ai_content_items: int = 0
    hours_saved: float = 0.0
    go_live_at: Optional[datetime] = None
    last_recalculated_at: Optional[datetime] = None
    hours_saved_breakdown: dict = field(default_factory=dict)
    missing_data_keys: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "emails_processed": self.emails_processed,
            "emails_drafted": self.emails_drafted,
            "emails_deleted": self.emails_deleted,
            "senders_noise": self.senders_noise,
            "vip_contacts": self.vip_contacts,
            "ai_content_items": self.ai_content_items,
            "hours_saved": round(self.hours_saved, 1),
            "go_live_at": self.go_live_at.isoformat() if self.go_live_at else None,
            "last_recalculated_at": (
                self.last_recalculated_at.isoformat() if self.last_recalculated_at else None
            ),
            "hours_saved_breakdown": self.hours_saved_breakdown,
            "missing_data_keys": self.missing_data_keys,
        }


def _go_live_dt(settings: Settings) -> Optional[datetime]:
    """Parse the go-live timestamp from settings, or return None."""
    raw = (settings.app_stats_go_live_at or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _words(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))


def compute_lifetime_stats(db: Session, settings: Settings | None = None) -> LifetimeStats:
    """Calculate life-to-date stats from audited DB records.

    All queries respect the go-live baseline if configured.
    """
    active = settings or get_settings()
    go_live_at = _go_live_dt(active)
    now = utcnow()

    # -----------------------------------------------------------------------
    # 1. Emails Processed — distinct messages that have been reviewed/dismissed
    # -----------------------------------------------------------------------
    reviewed_q = db.query(func.count(AttentionItem.id)).filter(
        AttentionItem.status.in_([AttentionStatus.REVIEWED, AttentionStatus.DISMISSED])
    )
    if go_live_at:
        reviewed_q = reviewed_q.filter(AttentionItem.updated_at >= go_live_at)
    emails_processed = reviewed_q.scalar() or 0

    # -----------------------------------------------------------------------
    # 2. Emails Drafted — approved or edited draft replies (not cancelled/deleted)
    # -----------------------------------------------------------------------
    drafted_q = db.query(func.count(DraftReply.id)).filter(
        DraftReply.status.in_([DraftStatus.GENERATED, DraftStatus.EDITED, DraftStatus.APPROVED])
    )
    if go_live_at:
        drafted_q = drafted_q.filter(DraftReply.created_at >= go_live_at)
    emails_drafted = drafted_q.scalar() or 0

    # -----------------------------------------------------------------------
    # 3. Emails Deleted — execution audit events with delete action executed
    # -----------------------------------------------------------------------
    deleted_q = db.query(func.count(ExecutionAuditLog.id)).filter(
        ExecutionAuditLog.event_type.like("%executed%"),
        ExecutionAuditLog.details.like("%delete%"),
    )
    if go_live_at:
        deleted_q = deleted_q.filter(ExecutionAuditLog.created_at >= go_live_at)
    emails_deleted = deleted_q.scalar() or 0

    # -----------------------------------------------------------------------
    # 4. Senders Identified as Spam/Noise — contacts marked noise
    # -----------------------------------------------------------------------
    noise_q = db.query(func.count(Contact.id)).filter(Contact.is_noise.is_(True))
    if go_live_at:
        noise_q = noise_q.filter(Contact.updated_at >= go_live_at)
    senders_noise = noise_q.scalar() or 0

    # -----------------------------------------------------------------------
    # 5. VIP Contacts
    # -----------------------------------------------------------------------
    vip_q = db.query(func.count(Contact.id)).filter(Contact.is_vip.is_(True))
    vip_contacts = vip_q.scalar() or 0

    # -----------------------------------------------------------------------
    # 6. AI-Provided Content Items — conversation summaries + review packages
    #    generated by a non-mock provider, plus drafts with AI provider
    # -----------------------------------------------------------------------
    ai_summaries_q = db.query(func.count(ConversationSummary.id)).filter(
        ConversationSummary.provider_name != "mock"
    )
    if go_live_at:
        ai_summaries_q = ai_summaries_q.filter(ConversationSummary.created_at >= go_live_at)
    ai_summaries = ai_summaries_q.scalar() or 0

    ai_pkgs_q = db.query(func.count(ProposedActionReviewPackage.id)).filter(
        ProposedActionReviewPackage.provider_name != "mock"
    )
    if go_live_at:
        ai_pkgs_q = ai_pkgs_q.filter(ProposedActionReviewPackage.created_at >= go_live_at)
    ai_pkgs = ai_pkgs_q.scalar() or 0

    ai_drafts_q = db.query(func.count(DraftReply.id)).filter(DraftReply.provider_name != "mock")
    if go_live_at:
        ai_drafts_q = ai_drafts_q.filter(DraftReply.created_at >= go_live_at)
    ai_drafts_count = ai_drafts_q.scalar() or 0

    ai_content_items = ai_summaries + ai_pkgs + ai_drafts_count

    # -----------------------------------------------------------------------
    # 7. Hours Saved — transparent configurable estimate
    # -----------------------------------------------------------------------
    hours_saved, breakdown = _calculate_hours_saved(db, go_live_at)

    missing: list[str] = []
    if emails_processed == 0:
        missing.append(STAT_EMAILS_PROCESSED)
    if emails_drafted == 0:
        missing.append(STAT_EMAILS_DRAFTED)

    return LifetimeStats(
        emails_processed=emails_processed,
        emails_drafted=emails_drafted,
        emails_deleted=emails_deleted,
        senders_noise=senders_noise,
        vip_contacts=vip_contacts,
        ai_content_items=ai_content_items,
        hours_saved=hours_saved,
        go_live_at=go_live_at,
        last_recalculated_at=now,
        hours_saved_breakdown=breakdown,
        missing_data_keys=missing,
    )


def _calculate_hours_saved(
    db: Session, go_live_at: Optional[datetime]
) -> tuple[float, dict]:
    """Return (total_hours, breakdown_dict).

    All categories produce a seconds total, summed and converted to hours.
    """
    seconds = 0.0
    breakdown: dict[str, float] = {}

    # Category A: Mark reviewed / local process actions
    reviewed_q = db.query(func.count(AttentionItem.id)).filter(
        AttentionItem.status.in_([AttentionStatus.REVIEWED, AttentionStatus.DISMISSED])
    )
    if go_live_at:
        reviewed_q = reviewed_q.filter(AttentionItem.updated_at >= go_live_at)
    reviewed_count = reviewed_q.scalar() or 0
    cat_a = reviewed_count * (MANUAL_REVIEW_SECONDS_PER_EMAIL + MANUAL_BROWSER_OPEN_THREAD_SECONDS)
    seconds += cat_a
    breakdown["mark_reviewed"] = round(cat_a / 3600, 2)

    # Category B: Bulk triage / cleanup
    bulk_q = db.query(BulkTriageActionLog.item_count).filter(
        BulkTriageActionLog.is_undone.is_(False)
    )
    if go_live_at:
        bulk_q = bulk_q.filter(BulkTriageActionLog.created_at >= go_live_at)
    bulk_rows = bulk_q.all()
    bulk_message_count = sum(r[0] for r in bulk_rows)
    bulk_batch_count = len(bulk_rows)
    cat_b = (
        bulk_batch_count * MANUAL_BULK_CLEANUP_SETUP_SECONDS
        + bulk_message_count * MANUAL_BULK_CLEANUP_SECONDS_PER_EMAIL
    )
    seconds += cat_b
    breakdown["bulk_cleanup"] = round(cat_b / 3600, 2)

    # Category C: Draft generation / execution
    # Use word counts from drafts when available; fall back to email_drafted count
    draft_q = db.query(
        DraftReply.draft_text, DraftReply.send_ready_body
    ).filter(
        DraftReply.status.in_([DraftStatus.GENERATED, DraftStatus.EDITED, DraftStatus.APPROVED])
    )
    if go_live_at:
        draft_q = draft_q.filter(DraftReply.created_at >= go_live_at)
    draft_rows = draft_q.all()

    cat_c = 0.0
    for draft_text, send_ready_body in draft_rows:
        draft_words = _words(send_ready_body or draft_text)
        typing_seconds = (draft_words / TYPING_WORDS_PER_MINUTE) * 60
        cat_c += typing_seconds + MANUAL_SEND_OVERHEAD_SECONDS - AI_REVIEW_OVERHEAD_SECONDS
    cat_c = max(0.0, cat_c)
    seconds += cat_c
    breakdown["draft_generation"] = round(cat_c / 3600, 2)

    # Category D: AI-provided content (summaries, packages)
    ai_pkgs_q = db.query(func.count(ProposedActionReviewPackage.id)).filter(
        ProposedActionReviewPackage.provider_name != "mock"
    )
    if go_live_at:
        ai_pkgs_q = ai_pkgs_q.filter(ProposedActionReviewPackage.created_at >= go_live_at)
    ai_pkg_count = ai_pkgs_q.scalar() or 0
    # Estimate: each AI summary / recommendation saves ~(manual_review + browser_open) seconds
    cat_d = ai_pkg_count * (MANUAL_REVIEW_SECONDS_PER_EMAIL + MANUAL_BROWSER_OPEN_THREAD_SECONDS)
    seconds += cat_d
    breakdown["ai_content"] = round(cat_d / 3600, 2)

    total_hours = seconds / 3600.0
    return round(total_hours, 1), breakdown


def persist_lifetime_stats(db: Session, stats: LifetimeStats) -> None:
    """Upsert the calculated stats into app_stat_records.

    This is safe to call repeatedly; it never resets the go-live baseline.
    """
    now = utcnow()
    values = {
        STAT_EMAILS_PROCESSED: float(stats.emails_processed),
        STAT_EMAILS_DRAFTED: float(stats.emails_drafted),
        STAT_EMAILS_DELETED: float(stats.emails_deleted),
        STAT_SENDERS_NOISE: float(stats.senders_noise),
        STAT_VIP_CONTACTS: float(stats.vip_contacts),
        STAT_AI_CONTENT_ITEMS: float(stats.ai_content_items),
        STAT_HOURS_SAVED: stats.hours_saved,
    }
    for key, value in values.items():
        existing = db.query(AppStatRecord).filter_by(stat_key=key).one_or_none()
        if existing is None:
            record = AppStatRecord(
                stat_key=key,
                stat_value=value,
                first_tracked_at=stats.go_live_at or now,
                last_recalculated_at=now,
                notes="auto-calculated",
            )
            db.add(record)
        else:
            existing.stat_value = value
            existing.last_recalculated_at = now
    db.commit()


def initialize_go_live_baseline(db: Session, settings: Settings) -> datetime:
    """Set the go-live timestamp on all stat records to now if not already set.

    This action is idempotent — it will not overwrite an existing baseline.
    Returns the effective go-live datetime.
    """
    existing = db.query(AppStatRecord).filter_by(stat_key=STAT_EMAILS_PROCESSED).one_or_none()
    if existing and existing.first_tracked_at:
        return existing.first_tracked_at

    now = utcnow()
    for key in ALL_STAT_KEYS:
        record = db.query(AppStatRecord).filter_by(stat_key=key).one_or_none()
        if record is None:
            record = AppStatRecord(
                stat_key=key,
                stat_value=0,
                first_tracked_at=now,
                last_recalculated_at=now,
                notes="go-live baseline initialized",
            )
            db.add(record)
        elif record.first_tracked_at is None:
            record.first_tracked_at = now
    db.commit()
    return now


def load_persisted_stats(db: Session) -> dict[str, float]:
    """Return the last persisted stat values keyed by stat_key."""
    rows = db.query(AppStatRecord).all()
    return {r.stat_key: float(r.stat_value) for r in rows}
