from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

MARKETING_KEYWORDS = {"sale", "discount", "deal", "limited time", "buy now", "promo", "offer"}
NEWSLETTER_KEYWORDS = {"newsletter", "digest", "weekly update", "unsubscribe"}
RECEIPT_KEYWORDS = {"receipt", "invoice", "payment", "order confirmation", "transaction"}
SYSTEM_KEYWORDS = {"noreply", "do-not-reply", "notification", "system", "alert"}
CLIENT_KEYWORDS = {"proposal", "contract", "client", "deliverable", "scope", "milestone"}
URGENCY_KEYWORDS = {"urgent", "asap", "today", "tomorrow", "deadline", "immediately"}
JOB_ALERT_KEYWORDS = {
    "job alert",
    "jobs alert",
    "recommended jobs",
    "new jobs",
    "jobs matching",
    "hiring",
    "linkedin job",
}
IMPORTANT_REMINDER_KEYWORDS = {
    "renewal",
    "renew",
    "insurance",
    "icbc",
    "invoice",
    "tax",
    "taxes",
    "bill",
    "due date",
    "payment deadline",
    "payment due",
    "expiry",
    "expires",
    "expiring",
}
QUESTION_PATTERNS = [
    r"\?",
    r"can you",
    r"could you",
    r"please",
    r"let me know",
    r"need your",
    r"reply",
]
HUMAN_FREEMAIL_DOMAINS = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com"}


@dataclass
class MessagePayload:
    sender_email: str | None
    subject: str | None
    snippet: str | None
    headers: dict[str, str] | None = None


@dataclass
class ClassificationResult:
    requires_reply: bool
    urgency_level: int
    is_human_personal: bool
    is_client_work: bool
    is_marketing: bool
    is_newsletter: bool
    is_receipt: bool
    is_group_noise: bool
    is_system_notification: bool
    confidence: Decimal
    classification_reason: str


def _contains_any(text: str, words: set[str]) -> bool:
    lower = text.lower()
    return any(word in lower for word in words)


def _domain(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].lower()


def classify_message(payload: MessagePayload) -> ClassificationResult:
    subject = payload.subject or ""
    snippet = payload.snippet or ""
    combined = f"{subject} {snippet}".lower()
    headers = {k.lower(): v for k, v in (payload.headers or {}).items()}

    list_unsubscribe_header = headers.get("list-unsubscribe", "").lower()
    precedence_header = headers.get("precedence", "").lower()
    auto_submitted_header = headers.get("auto-submitted", "").lower()
    reply_to_header = headers.get("reply-to", "").lower()

    list_unsub = "list-unsubscribe" in headers or "unsubscribe" in list_unsubscribe_header
    precedence_bulk = any(token in precedence_header for token in ("bulk", "list", "junk"))
    auto_generated = bool(auto_submitted_header and auto_submitted_header != "no")
    reply_to_suspicious = "noreply" in reply_to_header or "no-reply" in reply_to_header

    is_job_alert = _contains_any(combined, JOB_ALERT_KEYWORDS) or "linkedin" in _domain(
        payload.sender_email
    )
    has_important_reminder = _contains_any(combined, IMPORTANT_REMINDER_KEYWORDS)

    is_newsletter = (
        list_unsub
        or precedence_bulk
        or is_job_alert
        or _contains_any(combined, NEWSLETTER_KEYWORDS)
    )
    is_marketing = (
        _contains_any(combined, MARKETING_KEYWORDS)
        or is_newsletter
        or precedence_bulk
        or is_job_alert
    )
    is_receipt = _contains_any(combined, RECEIPT_KEYWORDS)
    is_system_notification = (
        _contains_any(combined, SYSTEM_KEYWORDS)
        or "noreply" in (payload.sender_email or "").lower()
        or auto_generated
        or reply_to_suspicious
        or is_job_alert
    )
    has_client_keywords = _contains_any(combined, CLIENT_KEYWORDS)
    business_domain = (
        bool(_domain(payload.sender_email))
        and _domain(payload.sender_email) not in HUMAN_FREEMAIL_DOMAINS
    )
    is_client_work = (
        has_client_keywords and not is_job_alert and not is_newsletter and not is_marketing
    ) or (
        business_domain
        and not is_job_alert
        and not is_newsletter
        and not is_marketing
        and not is_receipt
        and not is_system_notification
    )
    is_group_noise = is_marketing or is_newsletter or is_system_notification
    is_human_personal = not is_group_noise and not is_receipt and not is_client_work

    urgency_level = 0
    if _contains_any(combined, URGENCY_KEYWORDS):
        urgency_level = 2
    if "deadline" in combined or "urgent" in combined:
        urgency_level = 3
    if has_important_reminder:
        urgency_level = max(urgency_level, 2)
    if any(token in combined for token in ("payment deadline", "payment due", "due date")):
        urgency_level = max(urgency_level, 3)

    requires_reply = any(re.search(pattern, combined) for pattern in QUESTION_PATTERNS)
    if is_marketing or is_newsletter or is_job_alert:
        requires_reply = False

    reason_parts = []
    if is_job_alert:
        reason_parts.append("job alert signals")
    if has_important_reminder:
        reason_parts.append("important reminder keywords")
    if is_newsletter:
        reason_parts.append("newsletter-like signals")
    if list_unsub:
        reason_parts.append("list-unsubscribe header")
    if precedence_bulk:
        reason_parts.append("bulk/list precedence header")
    if is_marketing:
        reason_parts.append("marketing keywords")
    if auto_generated:
        reason_parts.append("auto-submitted header")
    if is_client_work:
        reason_parts.append("work/client-like context")
    if requires_reply:
        reason_parts.append("direct ask/question")
    if urgency_level > 0:
        reason_parts.append("urgency indicators")
    if not reason_parts:
        reason_parts.append("default deterministic classification")

    confidence = Decimal("0.65")
    if is_newsletter or is_marketing or is_receipt:
        confidence = Decimal("0.85")

    return ClassificationResult(
        requires_reply=requires_reply,
        urgency_level=urgency_level,
        is_human_personal=is_human_personal,
        is_client_work=is_client_work,
        is_marketing=is_marketing,
        is_newsletter=is_newsletter,
        is_receipt=is_receipt,
        is_group_noise=is_group_noise,
        is_system_notification=is_system_notification,
        confidence=confidence,
        classification_reason=", ".join(reason_parts),
    )
