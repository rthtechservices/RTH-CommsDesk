from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

GMAIL_DRAFT_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
CALENDAR_READ_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
CALENDAR_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"


class ExternalProviderConfigurationError(RuntimeError):
    """Raised when a live external provider is not intentionally configured."""


class GmailWriteClient:
    def __init__(self, settings: Settings | None = None, service: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._service = service

    def create_draft(self, payload: dict) -> dict:
        service = self._build_service([GMAIL_DRAFT_SCOPE])
        raw_message = _build_raw_email(
            to_address=payload.get("to"),
            subject=payload.get("subject") or "CommsDesk draft",
            body=payload.get("draft_text") or payload.get("body") or "",
            thread_id=payload.get("source_message_id") or payload.get("thread_id"),
        )
        message_body = {"raw": raw_message}
        if payload.get("source_thread_id"):
            message_body["threadId"] = payload.get("source_thread_id")
        result = (
            service.users()
            .drafts()
            .create(
                userId=self.settings.gmail_account,
                body={"message": message_body},
            )
            .execute()
        )
        return {"status": "created", "draft_id": result.get("id")}

    def send_reply(self, payload: dict) -> dict:
        service = self._build_service([GMAIL_SEND_SCOPE])
        raw_message = _build_raw_email(
            to_address=payload.get("to"),
            subject=payload.get("subject") or "Re:",
            body=payload.get("body") or "",
            thread_id=payload.get("source_message_id") or payload.get("thread_id"),
        )
        body = {"raw": raw_message}
        if payload.get("source_thread_id"):
            body["threadId"] = payload.get("source_thread_id")
        result = (
            service.users()
            .messages()
            .send(userId=self.settings.gmail_account, body=body)
            .execute()
        )
        return {"status": "sent", "message_id": result.get("id")}

    def apply_label_archive(self, payload: dict) -> dict:
        service = self._build_service([GMAIL_MODIFY_SCOPE])
        source_message_id = payload.get("source_message_id")
        if not source_message_id:
            raise ExternalProviderConfigurationError("Gmail source message id is required")
        operation = payload.get("operation")
        body: dict[str, list[str]] = {}
        if operation == "archive":
            body["removeLabelIds"] = ["INBOX"]
        elif operation == "mark_noise_label":
            if not self.settings.gmail_noise_label_id:
                raise ExternalProviderConfigurationError(
                    "GMAIL_NOISE_LABEL_ID is required for live Gmail noise labeling"
                )
            body["addLabelIds"] = [self.settings.gmail_noise_label_id]
        else:
            raise ExternalProviderConfigurationError(f"Unsupported Gmail label operation: {operation}")
        result = (
            service.users()
            .messages()
            .modify(userId=self.settings.gmail_account, id=source_message_id, body=body)
            .execute()
        )
        return {"status": "applied", "message_id": result.get("id"), "operation": operation}

    def _build_service(self, scopes: list[str]) -> Any:
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise ExternalProviderConfigurationError(
                "Install optional Gmail dependencies: pip install -e .[gmail]"
            ) from exc

        token_file = Path(self.settings.gmail_token_file)
        creds = Credentials.from_authorized_user_file(str(token_file), scopes) if token_file.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secrets_file = Path(self.settings.gmail_client_secrets_file)
                if not secrets_file.exists():
                    raise ExternalProviderConfigurationError(
                        "Gmail OAuth client secrets file is missing"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), scopes)
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds)
        return self._service


class GoogleCalendarClient:
    def __init__(self, settings: Settings | None = None, service: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._service = service

    def create_event(self, payload: dict) -> dict:
        service = self._build_service([CALENDAR_WRITE_SCOPE])
        event_body = _calendar_event_body(payload)
        result = (
            service.events()
            .insert(calendarId=self.settings.google_calendar_id, body=event_body)
            .execute()
        )
        return {"status": "created", "event_id": result.get("id"), "html_link": result.get("htmlLink")}

    def freebusy(self, start_at: str, end_at: str) -> dict:
        service = self._build_service([CALENDAR_READ_SCOPE])
        return (
            service.freebusy()
            .query(
                body={
                    "timeMin": start_at,
                    "timeMax": end_at,
                    "items": [{"id": self.settings.google_calendar_id}],
                }
            )
            .execute()
        )

    def _build_service(self, scopes: list[str]) -> Any:
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise ExternalProviderConfigurationError(
                "Install optional Gmail/Google dependencies: pip install -e .[gmail]"
            ) from exc

        token_file = Path(self.settings.google_calendar_token_file)
        creds = Credentials.from_authorized_user_file(str(token_file), scopes) if token_file.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secrets_file = Path(self.settings.gmail_client_secrets_file)
                if not secrets_file.exists():
                    raise ExternalProviderConfigurationError(
                        "Google OAuth client secrets file is missing"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), scopes)
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("calendar", "v3", credentials=creds)
        return self._service


def _build_raw_email(
    *,
    to_address: str | None,
    subject: str,
    body: str,
    thread_id: str | None = None,
) -> str:
    if not to_address:
        raise ExternalProviderConfigurationError("Recipient address is required")
    message = EmailMessage()
    message["To"] = to_address
    message["Subject"] = subject
    if thread_id:
        message["In-Reply-To"] = thread_id
        message["References"] = thread_id
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _calendar_event_body(payload: dict) -> dict:
    summary = payload.get("summary") or "CommsDesk reminder"
    action_kind = payload.get("action_kind")
    if action_kind == "create_reminder" or payload.get("reminder_at"):
        start = payload.get("reminder_at") or payload.get("proposed_start_at")
        return {
            "summary": summary,
            "description": "Created from an approved CommsDesk review package.",
            "start": {"dateTime": start},
            "end": {"dateTime": start},
            "reminders": {"useDefault": True},
        }
    start = payload.get("proposed_start_at")
    end = payload.get("proposed_end_at") or start
    if not start:
        raise ExternalProviderConfigurationError("Calendar event start time is required")
    return {
        "summary": summary,
        "description": "Created from an approved CommsDesk review package.",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
