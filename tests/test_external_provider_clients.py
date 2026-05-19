from __future__ import annotations

from app.core.config import Settings
from app.services.external_provider_clients import (
    GMAIL_SCOPE_REAUTH_MESSAGE,
    ExternalProviderConfigurationError,
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


class _FailingRequest:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def execute(self) -> dict:
        raise self.exc


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeGoogleError(Exception):
    def __init__(self, status: int, content: bytes) -> None:
        super().__init__(content.decode("utf-8", errors="replace"))
        self.resp = _FakeResponse(status)
        self.content = content
