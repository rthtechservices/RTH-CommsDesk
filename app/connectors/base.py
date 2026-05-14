from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedMessage:
    source_type: str
    source_message_id: str
    source_thread_id: str
    sender_display_name: str | None
    sender_email: str | None
    received_at: datetime
    subject: str | None
    snippet: str | None
    body_text: str | None
    has_attachments: bool
    is_unread: bool


class BaseConnector:
    source_type: str

    def fetch_recent_messages(self, limit: int = 100, since: datetime | None = None) -> list[NormalizedMessage]:
        raise NotImplementedError
