from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path

from app.connectors.base import BaseConnector, NormalizedMessage
from app.core.config import get_settings

GMAIL_READONLY_SCOPE = ["https://www.googleapis.com/auth/gmail.readonly"]
PRESERVED_HEADERS = {
    "from",
    "subject",
    "list-unsubscribe",
    "precedence",
    "auto-submitted",
    "reply-to",
}


class GmailConnector(BaseConnector):
    source_type = "gmail"

    def __init__(self, service=None) -> None:
        self.settings = get_settings()
        self._service = service

    def _build_service(self):
        if self._service is not None:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Install optional gmail dependencies: pip install -e .[gmail]"
            ) from exc

        token_file = Path(self.settings.gmail_token_file)
        creds = None
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_READONLY_SCOPE)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secrets_file = Path(self.settings.gmail_client_secrets_file)
                if not secrets_file.exists():
                    raise FileNotFoundError(
                        f"Gmail OAuth client secrets file not found: {secrets_file}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(secrets_file),
                    GMAIL_READONLY_SCOPE,
                )
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_recent_messages(
        self, limit: int = 100, since: datetime | None = None
    ) -> list[NormalizedMessage]:
        service = self._build_service()
        query_parts = ["in:inbox"]
        if since:
            query_parts.append(f"after:{int(since.timestamp())}")

        response = (
            service.users()
            .messages()
            .list(userId=self.settings.gmail_account, q=" ".join(query_parts), maxResults=limit)
            .execute()
        )
        messages = response.get("messages", [])
        result: list[NormalizedMessage] = []

        for msg_ref in messages:
            data = (
                service.users()
                .messages()
                .get(userId=self.settings.gmail_account, id=msg_ref["id"], format="full")
                .execute()
            )
            payload = data.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            preserved_headers = {
                key: value for key, value in headers.items() if key in PRESERVED_HEADERS
            }
            sender_name, sender_email = parseaddr(headers.get("from", ""))
            subject = headers.get("subject")
            internal_date_ms = int(data.get("internalDate", "0"))
            received_at = (
                datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC)
                if internal_date_ms
                else datetime.now(UTC)
            )
            snippet = data.get("snippet")
            body_text = self._extract_body(payload) if self.settings.gmail_store_full_body else None
            body_mode = body_text if self.settings.gmail_store_full_body else None

            result.append(
                NormalizedMessage(
                    source_type="gmail",
                    source_message_id=data["id"],
                    source_thread_id=data["threadId"],
                    sender_display_name=sender_name or None,
                    sender_email=sender_email or None,
                    received_at=received_at,
                    subject=subject,
                    snippet=snippet,
                    body_text=body_mode,
                    has_attachments=self._has_attachments(payload),
                    is_unread="UNREAD" in data.get("labelIds", []),
                    headers=preserved_headers,
                )
            )

        return result

    @staticmethod
    def _has_attachments(payload: dict) -> bool:
        parts = payload.get("parts", [])
        return any(part.get("filename") for part in parts)

    def _extract_body(self, payload: dict) -> str | None:
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return self._decode_base64_url(body_data)
        for part in payload.get("parts", []):
            if part.get("mimeType", "").startswith("text/plain"):
                data = part.get("body", {}).get("data")
                if data:
                    return self._decode_base64_url(data)
        return None

    @staticmethod
    def _decode_base64_url(data: str) -> str:
        decoded = base64.urlsafe_b64decode(data + "===")
        return decoded.decode("utf-8", errors="replace")
