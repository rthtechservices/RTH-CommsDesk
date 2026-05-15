from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from email.utils import getaddresses, parseaddr
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from app.connectors.base import BaseConnector, MessagePage, NormalizedMessage
from app.core.config import get_settings

GMAIL_READONLY_SCOPE = ["https://www.googleapis.com/auth/gmail.readonly"]
PRESERVED_HEADERS = {
    "from",
    "subject",
    "list-unsubscribe",
    "precedence",
    "auto-submitted",
    "reply-to",
    "to",
    "cc",
    "date",
    "message-id",
    "in-reply-to",
    "references",
}


class _PlainTextHTMLParser(HTMLParser):
    block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "table",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if tag in self.block_tags:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in self.block_tags:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        text = unescape("".join(self._chunks))
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return "\n".join(line.strip() for line in text.splitlines()).strip()


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
        return self.fetch_message_page(limit=limit, since=since).messages

    def fetch_sent_messages(
        self,
        limit: int = 100,
        since: datetime | None = None,
        *,
        include_body: bool = True,
    ) -> list[NormalizedMessage]:
        page = self.fetch_mailbox_page(
            mailbox_query="in:sent",
            limit=limit,
            since=since,
            include_body=include_body,
        )
        return page.messages

    def fetch_message_page(
        self,
        limit: int = 100,
        since: datetime | None = None,
        page_token: str | None = None,
    ) -> MessagePage:
        return self.fetch_mailbox_page(
            mailbox_query="in:inbox",
            limit=limit,
            since=since,
            page_token=page_token,
            include_body=None,
        )

    def fetch_mailbox_page(
        self,
        *,
        mailbox_query: str,
        limit: int = 100,
        since: datetime | None = None,
        page_token: str | None = None,
        include_body: bool | None = None,
    ) -> MessagePage:
        service = self._build_service()
        query_parts = [mailbox_query]
        if since:
            query_parts.append(f"after:{int(since.timestamp())}")

        list_kwargs = {
            "userId": self.settings.gmail_account,
            "q": " ".join(query_parts),
            "maxResults": limit,
        }
        if page_token:
            list_kwargs["pageToken"] = page_token

        response = service.users().messages().list(**list_kwargs).execute()
        messages = response.get("messages", [])
        result: list[NormalizedMessage] = []

        for msg_ref in messages:
            data = self._get_message(service, msg_ref["id"])
            result.append(self._normalize_message_data(data, include_body=include_body))

        return MessagePage(messages=result, next_page_token=response.get("nextPageToken"))

    def fetch_thread_messages(self, source_thread_id: str) -> list[NormalizedMessage]:
        service = self._build_service()
        data = (
            service.users()
            .threads()
            .get(userId=self.settings.gmail_account, id=source_thread_id, format="full")
            .execute()
        )
        messages = data.get("messages", [])
        return [
            self._normalize_message_data(message_data, include_body=True)
            for message_data in messages
        ]

    def _get_message(self, service, message_id: str) -> dict:
        return (
            service.users()
            .messages()
            .get(userId=self.settings.gmail_account, id=message_id, format="full")
            .execute()
        )

    def _normalize_message_data(
        self, data: dict, include_body: bool | None = None
    ) -> NormalizedMessage:
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
        store_body = self.settings.gmail_store_full_body if include_body is None else include_body
        body_text = self._extract_body(payload) if store_body else None

        return NormalizedMessage(
            source_type="gmail",
            source_message_id=data["id"],
            source_thread_id=data["threadId"],
            sender_display_name=sender_name or None,
            sender_email=sender_email or None,
            recipient_emails=self._parse_addresses(headers.get("to")),
            cc_emails=self._parse_addresses(headers.get("cc")),
            received_at=received_at,
            subject=subject,
            snippet=data.get("snippet"),
            body_text=body_text,
            has_attachments=self._has_attachments(payload),
            is_unread="UNREAD" in data.get("labelIds", []),
            headers=preserved_headers,
        )

    @staticmethod
    def _has_attachments(payload: dict) -> bool:
        parts = payload.get("parts", [])
        if payload.get("filename"):
            return True
        return any(GmailConnector._has_attachments(part) for part in parts)

    def _extract_body(self, payload: dict) -> str | None:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        self._collect_body_parts(payload, plain_parts, html_parts)
        if plain_parts:
            return self._collapse_text("\n\n".join(plain_parts))
        if html_parts:
            return self._html_to_text("\n\n".join(html_parts))
        return None

    def _collect_body_parts(
        self, payload: dict, plain_parts: list[str], html_parts: list[str]
    ) -> None:
        mime_type = payload.get("mimeType", "").lower()
        body_data = payload.get("body", {}).get("data")
        if body_data and mime_type.startswith("text/plain"):
            plain_parts.append(self._decode_base64_url(body_data))
        elif body_data and mime_type.startswith("text/html"):
            html_parts.append(self._decode_base64_url(body_data))
        elif body_data and not payload.get("parts"):
            plain_parts.append(self._decode_base64_url(body_data))

        for part in payload.get("parts", []):
            self._collect_body_parts(part, plain_parts, html_parts)

    @staticmethod
    def _decode_base64_url(data: str) -> str:
        decoded = base64.urlsafe_b64decode(data + ("=" * (-len(data) % 4)))
        return decoded.decode("utf-8", errors="replace")

    @staticmethod
    def _html_to_text(data: str) -> str:
        parser = _PlainTextHTMLParser()
        parser.feed(data)
        return parser.text()

    @staticmethod
    def _collapse_text(data: str) -> str:
        text = data.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()

    @staticmethod
    def _parse_addresses(value: str | None) -> list[str]:
        if not value:
            return []
        return [address.lower() for _, address in getaddresses([value]) if address]
