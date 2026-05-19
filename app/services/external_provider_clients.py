from __future__ import annotations

import base64
import json
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


GMAIL_SCOPE_REAUTH_MESSAGE = (
    "Gmail OAuth token does not have the required write scope for this action. "
    "Delete gmail_token.json, then re-authorize after enabling the matching Gmail write "
    "feature flag and OAuth scope."
)


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
        result = _execute_google_request(
            service.users()
            .drafts()
            .create(userId=self.settings.gmail_account, body={"message": message_body}),
            provider_label="Gmail draft creation",
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
        result = _execute_google_request(
            service.users().messages().send(userId=self.settings.gmail_account, body=body),
            provider_label="Gmail send reply",
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
        result = _execute_google_request(
            service.users()
            .messages()
            .modify(userId=self.settings.gmail_account, id=source_message_id, body=body),
            provider_label="Gmail label/archive",
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
        event_body = _calendar_event_body(payload, settings=self.settings)
        result = _execute_google_request(
            service.events()
            .insert(calendarId=self.settings.google_calendar_id, body=event_body),
            provider_label="Google Calendar event creation",
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


def _calendar_event_body(payload: dict, *, settings: Settings | None = None) -> dict:
    active_settings = settings or get_settings()
    time_zone = active_settings.google_calendar_time_zone or "America/Vancouver"
    summary = payload.get("summary") or "CommsDesk reminder"
    action_kind = payload.get("action_kind")
    if action_kind == "create_reminder" or payload.get("reminder_at"):
        start = payload.get("reminder_at") or payload.get("proposed_start_at")
        return {
            "summary": summary,
            "description": "Created from an approved CommsDesk review package.",
            "start": {"dateTime": start, "timeZone": time_zone},
            "end": {"dateTime": start, "timeZone": time_zone},
            "reminders": {"useDefault": True},
        }
    start = payload.get("proposed_start_at")
    end = payload.get("proposed_end_at") or start
    if not start:
        raise ExternalProviderConfigurationError("Calendar event start time is required")
    return {
        "summary": summary,
        "description": "Created from an approved CommsDesk review package.",
        "start": {"dateTime": start, "timeZone": time_zone},
        "end": {"dateTime": end, "timeZone": time_zone},
    }


def _execute_google_request(request: Any, *, provider_label: str) -> dict:
    try:
        return request.execute()
    except Exception as exc:
        if _is_insufficient_scope_error(exc):
            raise ExternalProviderConfigurationError(GMAIL_SCOPE_REAUTH_MESSAGE) from exc
        raise ExternalProviderConfigurationError(f"{provider_label} failed: {_google_error_text(exc)}") from exc


def _is_insufficient_scope_error(exc: Exception) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    text = _google_error_text(exc).lower()
    return status == 403 and (
        "insufficient authentication scopes" in text
        or "insufficient_permission" in text
        or "insufficientpermissions" in text
    )


def _google_error_text(exc: Exception) -> str:
    content = getattr(exc, "content", None)
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    if isinstance(content, str) and content.strip():
        try:
            data = json.loads(content)
            message = ((data.get("error") or {}).get("message")) or data.get("error_description")
            if message:
                return str(message)
        except json.JSONDecodeError:
            return content
    return str(exc)
