from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.base import NormalizedMessage


def normalize_notification_payload(payload: dict) -> NormalizedMessage:
    notification_id = str(payload.get("notification_id") or payload.get("id") or "")
    channel = (payload.get("channel") or "notification").strip().lower()
    sender = (payload.get("sender") or payload.get("sender_id") or "").strip().lower() or None
    sender_name = payload.get("sender_name")
    created_at = _parse_timestamp(payload.get("created_at"))
    summary = (payload.get("summary") or payload.get("text") or "").strip()
    title = (payload.get("title") or f"{channel.title()} notification").strip()
    confidence = float(payload.get("source_confidence") or 0.45)
    confidence = max(0.05, min(confidence, 1.0))
    return NormalizedMessage(
        source_type=f"notification_{channel}",
        source_message_id=notification_id or f"{channel}-{int(created_at.timestamp())}",
        source_thread_id=str(payload.get("thread_id") or payload.get("conversation_id") or notification_id),
        sender_display_name=sender_name,
        sender_email=sender,
        recipient_emails=[],
        cc_emails=[],
        received_at=created_at,
        subject=title[:500],
        snippet=summary[:500] or None,
        body_text=None,
        has_attachments=False,
        is_unread=True,
        headers={"x-notification-channel": channel},
        source_channel=channel,
        source_confidence=confidence,
    )


def _parse_timestamp(value) -> datetime:
    if not value:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    text = str(value).strip()
    if not text:
        return datetime.now(UTC)
    text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
