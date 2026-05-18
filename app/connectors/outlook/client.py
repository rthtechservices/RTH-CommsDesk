from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.base import BaseConnector, NormalizedMessage
from app.core.config import get_settings
from app.services.microsoft_graph_client import MicrosoftGraphMailService


class OutlookConnector(BaseConnector):
    source_type = "outlook"

    def __init__(self, service=None) -> None:
        self._service = service

    def fetch_recent_messages(
        self, limit: int = 100, since: datetime | None = None
    ) -> list[NormalizedMessage]:
        if self._service is None and get_settings().microsoft_graph_outlook_mail_enabled:
            self._service = MicrosoftGraphMailService()
        if self._service is None:
            raise RuntimeError(
                "Outlook connector service is not configured. Provide a Graph service client."
            )
        rows = self._service.fetch_messages(limit=limit, since=since)
        return [self._normalize_graph_message(row) for row in rows]

    def _normalize_graph_message(self, row: dict) -> NormalizedMessage:
        sender = (((row.get("from") or {}).get("emailAddress")) or {}).get("address")
        sender_name = (((row.get("from") or {}).get("emailAddress")) or {}).get("name")
        received = _parse_graph_datetime(row.get("receivedDateTime"))
        to_recipients = _addresses_from_graph_recipients(row.get("toRecipients"))
        cc_recipients = _addresses_from_graph_recipients(row.get("ccRecipients"))
        return NormalizedMessage(
            source_type="outlook",
            source_message_id=str(row.get("id")),
            source_thread_id=str(row.get("conversationId") or row.get("id")),
            sender_display_name=sender_name,
            sender_email=sender,
            recipient_emails=to_recipients,
            cc_emails=cc_recipients,
            received_at=received,
            subject=row.get("subject"),
            snippet=row.get("bodyPreview"),
            body_text=row.get("bodyPreview"),
            has_attachments=bool(row.get("hasAttachments")),
            is_unread=not bool(row.get("isRead")),
            headers={"x-provider": "microsoft-graph"},
            source_channel="email",
            source_confidence=0.95,
        )


def _addresses_from_graph_recipients(recipients: list[dict] | None) -> list[str]:
    if not recipients:
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for recipient in recipients:
        address = (((recipient or {}).get("emailAddress")) or {}).get("address")
        normalized = (address or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
    return rows


def _parse_graph_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
