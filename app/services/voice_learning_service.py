from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.connectors.gmail.client import GmailConnector
from app.models.entities import (
    Contact,
    InferenceStatus,
    Message,
    SentMailLearningRecord,
    UserFeedback,
    VipInferenceCandidate,
    VoiceGuidance,
    utcnow,
)
from app.services.contact_service import ensure_contact_for_sender, find_contact_by_sender_email

RELATIONSHIP_VIP_BONUS = {
    "partner": 18,
    "close_friend": 14,
    "family": 12,
    "client": 11,
    "friend": 7,
    "prospect": 4,
    "vendor": 3,
    "newsletter": -16,
    "system": -12,
    "unknown": 0,
}


@dataclass(frozen=True)
class SentLearningRunResult:
    fetched_count: int
    inserted_count: int
    updated_count: int
    vip_candidate_count: int
    guidance_count: int


@dataclass(frozen=True)
class VoiceGuidanceSelection:
    salutation_style: str | None
    preferred_name: str | None
    tone_notes: str | None
    source: str


def run_sent_mail_learning(
    db: Session,
    *,
    connector: GmailConnector | None = None,
    limit: int = 200,
) -> SentLearningRunResult:
    gmail = connector or GmailConnector()
    try:
        sent_messages = gmail.fetch_sent_messages(limit=limit, include_body=True)
    except TypeError:
        sent_messages = gmail.fetch_sent_messages(limit=limit)

    inserted = 0
    updated = 0
    for message in sent_messages:
        recipients = _normalized_unique_addresses(message.recipient_emails)
        if not recipients:
            continue
        for recipient in recipients:
            contact = ensure_contact_for_sender(db, recipient, None)
            existing = (
                db.query(SentMailLearningRecord)
                .filter_by(
                    source_type=message.source_type,
                    source_message_id=message.source_message_id,
                    recipient_email=recipient,
                )
                .first()
            )
            payload = {
                "source_type": message.source_type,
                "source_message_id": message.source_message_id,
                "source_thread_id": message.source_thread_id,
                "contact_id": contact.id if contact else None,
                "recipient_email": recipient,
                "sent_at": message.received_at or datetime.now(UTC),
                "subject": _truncate(message.subject, 500),
                "snippet_excerpt": _truncate(message.snippet, 500),
                "body_excerpt": _safe_excerpt(message.body_text or message.snippet),
                "is_reply": _looks_like_reply(message.subject, message.body_text),
            }
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(SentMailLearningRecord(**payload))
                inserted += 1

    db.flush()
    vip_candidates = infer_vip_candidates(db)
    voice_guidance = infer_voice_guidance(db)
    db.commit()
    return SentLearningRunResult(
        fetched_count=len(sent_messages),
        inserted_count=inserted,
        updated_count=updated,
        vip_candidate_count=vip_candidates,
        guidance_count=voice_guidance,
    )


def infer_vip_candidates(db: Session) -> int:
    grouped = _records_by_contact(db)
    updated = 0
    for contact_id, records in grouped.items():
        contact = db.get(Contact, contact_id)
        if not contact:
            continue
        sent_count = len(records)
        last_sent_at = max((record.sent_at for record in records), default=None)
        reply_count = sum(1 for record in records if record.is_reply)
        reply_ratio = Decimal(reply_count) / Decimal(sent_count) if sent_count else Decimal("0")
        recency_bonus = _recency_bonus(last_sent_at)
        feedback_bonus = _feedback_bonus(db, contact.id)
        relationship_bonus = RELATIONSHIP_VIP_BONUS.get(
            (contact.relationship_type or "unknown").strip().lower(),
            0,
        )
        manual_bonus = 14 if contact.is_vip else -35 if contact.is_noise else 0
        score = int(
            min(
                100,
                sent_count * 5 + recency_bonus + (float(reply_ratio) * 20) + feedback_bonus
                + relationship_bonus
                + manual_bonus,
            )
        )
        reasons = (
            f"sent_count={sent_count}; recency_bonus={recency_bonus}; "
            f"reply_ratio={reply_ratio:.2f}; feedback_bonus={feedback_bonus}; "
            f"relationship_bonus={relationship_bonus}; manual_bonus={manual_bonus}"
        )
        candidate = db.query(VipInferenceCandidate).filter_by(contact_id=contact.id).first()
        if not candidate:
            candidate = VipInferenceCandidate(contact_id=contact.id, reasons=reasons)
            db.add(candidate)
        candidate.score = score
        candidate.sent_count = sent_count
        candidate.reply_ratio = reply_ratio.quantize(Decimal("0.0001"))
        candidate.last_sent_at = last_sent_at
        candidate.reasons = reasons
        candidate.updated_at = utcnow()
        if candidate.status == InferenceStatus.APPROVED:
            contact.is_vip = True
            contact.is_noise = False
            contact.importance_tier = max(contact.importance_tier or 0, 4)
        elif candidate.status == InferenceStatus.REJECTED:
            contact.is_vip = False
        updated += 1
    return updated


def infer_voice_guidance(db: Session) -> int:
    grouped = _records_by_contact(db)
    updated = 0
    relationship_records: dict[str, list[SentMailLearningRecord]] = defaultdict(list)
    for contact_id, records in grouped.items():
        contact = db.get(Contact, contact_id)
        if not contact:
            continue
        relationship = (contact.relationship_type or "unknown").strip().lower()
        relationship_records[relationship].extend(records)
        style, preferred_name, tone_notes, evidence = _infer_contact_voice(records, relationship)
        guidance = (
            db.query(VoiceGuidance)
            .filter(VoiceGuidance.contact_id == contact.id)
            .order_by(VoiceGuidance.id.desc())
            .first()
        )
        if not guidance:
            guidance = VoiceGuidance(contact_id=contact.id, relationship_type=relationship)
            db.add(guidance)
        if guidance.status != InferenceStatus.APPROVED:
            guidance.salutation_style = style
            guidance.preferred_name = preferred_name
            guidance.tone_notes = tone_notes
        guidance.relationship_type = relationship
        guidance.evidence_excerpt = evidence
        guidance.source = "contact_inference"
        guidance.updated_at = utcnow()
        updated += 1

    for relationship, records in relationship_records.items():
        if relationship in {"newsletter", "system", "unknown"}:
            continue
        _, _, tone_notes, evidence = _infer_contact_voice(records, relationship)
        guidance = (
            db.query(VoiceGuidance)
            .filter(VoiceGuidance.contact_id.is_(None), VoiceGuidance.relationship_type == relationship)
            .order_by(VoiceGuidance.id.desc())
            .first()
        )
        if not guidance:
            guidance = VoiceGuidance(contact_id=None, relationship_type=relationship)
            db.add(guidance)
        if guidance.status != InferenceStatus.APPROVED:
            guidance.tone_notes = tone_notes
        guidance.evidence_excerpt = evidence
        guidance.source = "relationship_inference"
        guidance.updated_at = utcnow()
        updated += 1
    return updated


def vip_candidates_for_review(db: Session) -> list[VipInferenceCandidate]:
    return (
        db.query(VipInferenceCandidate)
        .order_by(VipInferenceCandidate.score.desc(), VipInferenceCandidate.updated_at.desc())
        .limit(200)
        .all()
    )


def voice_guidance_for_review(db: Session) -> list[VoiceGuidance]:
    return (
        db.query(VoiceGuidance)
        .order_by(VoiceGuidance.status.asc(), VoiceGuidance.updated_at.desc(), VoiceGuidance.id.desc())
        .limit(300)
        .all()
    )


def update_vip_candidate_status(
    db: Session,
    candidate_id: int,
    *,
    status: InferenceStatus,
    review_note: str | None = None,
) -> VipInferenceCandidate:
    candidate = db.get(VipInferenceCandidate, candidate_id)
    if not candidate:
        raise ValueError("VIP inference candidate not found")
    candidate.status = status
    candidate.review_note = _truncate((review_note or "").strip() or None, 500)
    candidate.updated_at = utcnow()
    contact = db.get(Contact, candidate.contact_id)
    if contact:
        if status == InferenceStatus.APPROVED:
            contact.is_vip = True
            contact.is_noise = False
            contact.importance_tier = max(contact.importance_tier or 0, 4)
        elif status == InferenceStatus.REJECTED:
            contact.is_vip = False
    db.commit()
    db.refresh(candidate)
    return candidate


def update_voice_guidance_status(
    db: Session,
    guidance_id: int,
    *,
    status: InferenceStatus,
    salutation_style: str | None = None,
    preferred_name: str | None = None,
    tone_notes: str | None = None,
) -> VoiceGuidance:
    guidance = db.get(VoiceGuidance, guidance_id)
    if not guidance:
        raise ValueError("Voice guidance not found")
    if salutation_style is not None:
        guidance.salutation_style = _validated_salutation_style(salutation_style)
    if preferred_name is not None:
        guidance.preferred_name = _truncate(preferred_name.strip() or None, 255)
    if tone_notes is not None:
        guidance.tone_notes = _truncate(tone_notes.strip() or None, 500)
    guidance.status = status
    guidance.is_active = status == InferenceStatus.APPROVED
    guidance.updated_at = utcnow()
    db.commit()
    db.refresh(guidance)
    return guidance


def resolve_guidance_for_message(
    db: Session,
    message: Message,
    contact: Contact | None = None,
) -> VoiceGuidanceSelection | None:
    contact = contact or _resolve_contact(db, message)
    if contact:
        contact_guidance = (
            db.query(VoiceGuidance)
            .filter(
                VoiceGuidance.contact_id == contact.id,
                VoiceGuidance.status == InferenceStatus.APPROVED,
                VoiceGuidance.is_active.is_(True),
            )
            .order_by(VoiceGuidance.updated_at.desc(), VoiceGuidance.id.desc())
            .first()
        )
        if contact_guidance:
            return VoiceGuidanceSelection(
                salutation_style=contact_guidance.salutation_style,
                preferred_name=contact_guidance.preferred_name,
                tone_notes=contact_guidance.tone_notes,
                source="contact",
            )

    relationship = (contact.relationship_type or "unknown").strip().lower() if contact else "unknown"
    relationship_guidance = (
        db.query(VoiceGuidance)
        .filter(
            VoiceGuidance.contact_id.is_(None),
            VoiceGuidance.relationship_type == relationship,
            VoiceGuidance.status == InferenceStatus.APPROVED,
            VoiceGuidance.is_active.is_(True),
        )
        .order_by(VoiceGuidance.updated_at.desc(), VoiceGuidance.id.desc())
        .first()
    )
    if not relationship_guidance:
        return None
    return VoiceGuidanceSelection(
        salutation_style=relationship_guidance.salutation_style,
        preferred_name=relationship_guidance.preferred_name,
        tone_notes=relationship_guidance.tone_notes,
        source="relationship",
    )


def _records_by_contact(db: Session) -> dict[int, list[SentMailLearningRecord]]:
    rows = (
        db.query(SentMailLearningRecord)
        .filter(SentMailLearningRecord.contact_id.is_not(None))
        .order_by(SentMailLearningRecord.sent_at.desc(), SentMailLearningRecord.id.desc())
        .all()
    )
    grouped: dict[int, list[SentMailLearningRecord]] = defaultdict(list)
    for row in rows:
        if row.contact_id is not None:
            grouped[row.contact_id].append(row)
    return grouped


def _recency_bonus(last_sent_at: datetime | None) -> int:
    if not last_sent_at:
        return 0
    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - last_sent_at).days
    if age_days <= 14:
        return 20
    if age_days <= 45:
        return 12
    if age_days <= 90:
        return 5
    return 0


def _feedback_bonus(db: Session, contact_id: int) -> int:
    rows = (
        db.query(UserFeedback.corrected_label)
        .filter(UserFeedback.contact_id == contact_id, UserFeedback.corrected_label.is_not(None))
        .all()
    )
    score = 0
    for (label,) in rows:
        if label in {"important", "needs_reply"}:
            score += 4
        if label in {"noise", "ignore", "newsletter"}:
            score -= 3
    return score


def _infer_contact_voice(
    records: list[SentMailLearningRecord], relationship: str
) -> tuple[str | None, str | None, str | None, str | None]:
    style_counter: Counter[str] = Counter()
    preferred_counter: Counter[str] = Counter()
    casual_words = 0
    formal_words = 0
    evidence = None

    for record in records[:40]:
        text = (record.body_excerpt or record.snippet_excerpt or "").strip()
        if not text:
            continue
        if evidence is None:
            evidence = _safe_excerpt(text, max_length=220)
        first_line = text.splitlines()[0].strip()
        style, preferred = _infer_salutation(first_line)
        if style:
            style_counter[style] += 1
        if preferred:
            preferred_counter[preferred] += 1
        lower = text.lower()
        casual_words += sum(token in lower for token in ("hey", "thanks!", "lol", "haha", "great to"))
        formal_words += sum(
            token in lower for token in ("regards", "thank you", "please find", "sincerely")
        )

    salutation_style = style_counter.most_common(1)[0][0] if style_counter else "first_name"
    preferred_name = preferred_counter.most_common(1)[0][0] if preferred_counter else None

    if relationship in {"friend", "close_friend", "family", "partner"}:
        base_tone = "casual, warm, concise"
    elif relationship in {"client", "prospect", "vendor"}:
        base_tone = "concise, professional, clear next steps"
    else:
        base_tone = "clear and direct"

    if casual_words > formal_words + 1:
        tone_notes = f"{base_tone}; avoid corporate filler"
    elif formal_words > casual_words + 1:
        tone_notes = f"{base_tone}; keep professional greeting"
    else:
        tone_notes = base_tone

    return salutation_style, preferred_name, _truncate(tone_notes, 500), evidence


def _infer_salutation(first_line: str) -> tuple[str | None, str | None]:
    normalized = first_line.strip()
    if not normalized:
        return None, None

    formal_match = re.match(r"^(dear)\s+([^,:]+)", normalized, flags=re.IGNORECASE)
    if formal_match:
        return "formal", _truncate(formal_match.group(2).strip(), 255)

    casual_match = re.match(r"^(hi|hey|hello)\s+([^,:]+)", normalized, flags=re.IGNORECASE)
    if casual_match:
        raw_name = casual_match.group(2).strip()
        parts = raw_name.split()
        if len(parts) >= 2:
            return "full_name", _truncate(raw_name, 255)
        return "first_name", _truncate(raw_name, 255)

    if re.match(r"^[a-zA-Z][a-zA-Z .'-]{1,30},\s*$", normalized):
        bare_name = normalized.rstrip(",").strip()
        if len(bare_name.split()) >= 2:
            return "full_name", _truncate(bare_name, 255)
        return "first_name", _truncate(bare_name, 255)

    return "no_greeting", None


def _normalized_unique_addresses(addresses: list[str] | None) -> list[str]:
    if not addresses:
        return []
    seen: set[str] = set()
    values: list[str] = []
    for address in addresses:
        normalized = (address or "").strip().lower()
        if not normalized or "@" not in normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(normalized)
    return values


def _looks_like_reply(subject: str | None, body_text: str | None) -> bool:
    normalized_subject = (subject or "").strip().lower()
    if normalized_subject.startswith("re:"):
        return True
    normalized_body = (body_text or "").strip().lower()
    return normalized_body.startswith("hi ") or normalized_body.startswith("hey ")


def _safe_excerpt(value: str | None, *, max_length: int = 500) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", " ", value).strip()
    return _truncate(compact, max_length)


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value[:max_length]


def _validated_salutation_style(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    allowed = {"no_greeting", "first_name", "nickname", "full_name", "formal"}
    if normalized not in allowed:
        raise ValueError("Unsupported salutation style")
    return normalized


def _resolve_contact(db: Session, message: Message) -> Contact | None:
    if message.thread and message.thread.contact_id:
        return db.get(Contact, message.thread.contact_id)
    if message.sender_email:
        return find_contact_by_sender_email(db, message.sender_email)
    return None
