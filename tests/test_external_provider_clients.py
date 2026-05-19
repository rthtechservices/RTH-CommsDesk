from __future__ import annotations

import base64
from email import message_from_bytes

from app.core.config import Settings
from app.services.external_provider_clients import (
    GMAIL_SCOPE_REAUTH_MESSAGE,
    ExternalProviderConfigurationError,
    GmailWriteClient,
    _calendar_event_body,
    _execute_google_request,
)


def test_calendar_reminder_payload_includes_configured_time_zone():
    body = _calendar_event_body(
        {
            "summary": "Registration renewal",
            "action_kind": "create_reminder",
            "reminder_at": "2026-05-13T09:00:00",
        },
        settings=Settings(_env_file=None, google_calendar_time_zone="America/Vancouver"),
    )

    assert body["start"] == {
        "dateTime": "2026-05-13T09:00:00",
        "timeZone": "America/Vancouver",
    }
    assert body["end"] == {
        "dateTime": "2026-05-13T09:00:00",
        "timeZone": "America/Vancouver",
    }


def test_calendar_scheduled_event_payload_includes_configured_time_zone():
    body = _calendar_event_body(
        {
            "summary": "Client meeting",
            "action_kind": "create_meeting",
            "proposed_start_at": "2026-05-20T14:00:00",
            "proposed_end_at": "2026-05-20T15:00:00",
        },
        settings=Settings(_env_file=None, google_calendar_time_zone="America/Vancouver"),
    )

    assert body["start"] == {
        "dateTime": "2026-05-20T14:00:00",
        "timeZone": "America/Vancouver",
    }
    assert body["end"] == {
        "dateTime": "2026-05-20T15:00:00",
        "timeZone": "America/Vancouver",
    }


def test_google_insufficient_scope_error_is_actionable():
    request = _FailingRequest(
        _FakeGoogleError(
            403,
            b'{"error": {"message": "Request had insufficient authentication scopes."}}',
        )
    )

    try:
        _execute_google_request(request, provider_label="Gmail draft creation")
    except ExternalProviderConfigurationError as exc:
        assert str(exc) == GMAIL_SCOPE_REAUTH_MESSAGE
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected insufficient-scope configuration error")


def test_gmail_create_draft_prefers_clean_send_ready_body() -> None:
    service = _CapturingGmailService()
    client = GmailWriteClient(Settings(_env_file=None), service=service)

    result = client.create_draft(
        {
            "to": "person@example.com",
            "send_ready_subject": "Re: Time to Meet",
            "send_ready_body": "Hi Pat,\n\nTuesday at 2 works for me.\n\nBest",
            "draft_text": (
                "Review-only draft suggestion. This has not been sent.\n\n"
                "Subject: Re: Time to Meet\n\n"
                "Hi Pat,\n\nTuesday at 2 works for me.\n\nBest"
            ),
        }
    )
    raw = service.created_body["message"]["raw"]
    message = message_from_bytes(base64.urlsafe_b64decode(raw.encode("ascii")))
    body = message.get_payload(decode=True).decode("utf-8")

    assert result == {"status": "created", "draft_id": "draft-1"}
    assert message["Subject"] == "Re: Time to Meet"
    assert "Hi Pat,\n\nTuesday at 2 works for me.\n\nBest" in body
    assert "Review-only draft suggestion" not in body
    assert "This has not been sent" not in body
    assert "Subject:" not in body


class _FailingRequest:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def execute(self) -> dict:
        raise self.exc


class _CapturingGmailService:
    def __init__(self) -> None:
        self.created_body: dict = {}

    def users(self) -> "_CapturingGmailService":
        return self

    def drafts(self) -> "_CapturingGmailService":
        return self

    def create(self, **kwargs) -> "_CapturingGmailService":
        self.created_body = kwargs["body"]
        return self

    def execute(self) -> dict:
        return {"id": "draft-1"}


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeGoogleError(Exception):
    def __init__(self, status: int, content: bytes) -> None:
        super().__init__(content.decode("utf-8", errors="replace"))
        self.resp = _FakeResponse(status)
        self.content = content
