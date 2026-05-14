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
QUESTION_PATTERNS = [r"\?", r"can you", r"could you", r"please", r"let me know", r"need your", r"reply"]
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

    list_unsub = "list-unsubscribe" in headers or "unsubscribe" in headers.get("list-unsubscribe", "").lower()
    is_newsletter = list_unsub or _contains_any(combined, NEWSLETTER_KEYWORDS)
    is_marketing = _contains_any(combined, MARKETING_KEYWORDS) or is_newsletter
    is_receipt = _contains_any(combined, RECEIPT_KEYWORDS)
    is_system_notification = _contains_any(combined, SYSTEM_KEYWORDS) or "noreply" in (payload.sender_email or "").lower()
    is_client_work = _contains_any(combined, CLIENT_KEYWORDS) or _domain(payload.sender_email) not in HUMAN_FREEMAIL_DOMAINS
    is_group_noise = is_marketing or is_newsletter or is_system_notification
    is_human_personal = not is_group_noise and not is_receipt

    urgency_level = 0
    if _contains_any(combined, URGENCY_KEYWORDS):
        urgency_level = 2
    if "deadline" in combined or "urgent" in combined:
        urgency_level = 3

    requires_reply = any(re.search(pattern, combined) for pattern in QUESTION_PATTERNS)
    if is_marketing or is_newsletter:
        requires_reply = False

    reason_parts = []
    if is_newsletter:
        reason_parts.append("newsletter-like signals")
    if is_marketing:
        reason_parts.append("marketing keywords")
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
