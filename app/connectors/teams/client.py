from __future__ import annotations

import re
from datetime import UTC, datetime

from app.connectors.base import BaseConnector, NormalizedMessage


class TeamsConnector(BaseConnector):
    source_type = "teams"

    def __init__(self, service=None) -> None:
        self._service = service

    def fetch_recent_messages(
        self, limit: int = 100, since: datetime | None = None
    ) -> list[NormalizedMessage]:
        if self._service is None:
            raise RuntimeError(
                "Teams connector service is not configured. Provide a Graph service client."
            )
        rows = self._service.fetch_messages(limit=limit, since=since)
        return [self._normalize_teams_message(row) for row in rows]

    def _normalize_teams_message(self, row: dict) -> NormalizedMessage:
        sender = ((((row.get("from") or {}).get("user")) or {}).get("userPrincipalName")) or (
            (((row.get("from") or {}).get("user")) or {}).get("id")
        )
        sender_name = (((row.get("from") or {}).get("user")) or {}).get("displayName")
        created = _parse_graph_datetime(row.get("createdDateTime"))
        body_html = (((row.get("body") or {}).get("content")) or "").strip()
        body_text = _strip_html(body_html)
        source_message_id = str(row.get("id"))
        source_thread_id = str(row.get("replyToId") or row.get("chatId") or source_message_id)
        return NormalizedMessage(
            source_type="teams",
            source_message_id=source_message_id,
            source_thread_id=source_thread_id,
            sender_display_name=sender_name,
            sender_email=sender,
            recipient_emails=[],
            cc_emails=[],
            received_at=created,
            subject=f"Teams message from {sender_name or sender or 'unknown'}",
            snippet=body_text[:300] if body_text else None,
            body_text=body_text or None,
            has_attachments=False,
            is_unread=False,
            headers={"x-provider": "microsoft-teams"},
            source_channel="teams",
            source_confidence=0.85,
        )


def _parse_graph_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _strip_html(value: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", value)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped
