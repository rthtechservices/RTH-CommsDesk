from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.provider_status_service import provider_status_matrix, provider_status_rows


def test_provider_status_fails_closed_without_external_config():
    status = provider_status_matrix(
        Settings(_env_file=None, gmail_client_secrets_file="./does-not-exist-client-secret.json")
    )

    assert status["gmail_read"]["state"] == "missing_configuration"
    assert status["gmail_draft_create"]["state"] == "disabled"
    assert status["gmail_send_reply"]["state"] == "disabled"
    assert status["google_calendar_write"]["state"] == "disabled"
    assert status["microsoft_graph_outlook_mail"]["classification"] == "adapter-shape-only"
    assert status["ai_provider"]["state"] == "mock"


def test_provider_status_reports_dry_run_when_write_flags_are_enabled(tmp_path):
    secrets = tmp_path / "client_secret.json"
    secrets.write_text("{}", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        gmail_client_secrets_file=str(secrets),
        gmail_write_enabled=True,
        gmail_draft_create_enabled=True,
        gmail_send_enabled=True,
        google_calendar_write_enabled=True,
        external_write_dry_run=True,
    )

    status = provider_status_matrix(settings)

    assert status["gmail_read"]["state"] == "live"
    assert status["gmail_draft_create"]["state"] == "dry_run"
    assert status["gmail_send_reply"]["state"] == "dry_run"
    assert status["google_calendar_write"]["state"] == "dry_run"


def test_provider_status_rows_cover_required_phase15_actions():
    keys = {row.key for row in provider_status_rows(Settings(_env_file=None))}

    assert {
        "gmail_read",
        "gmail_draft_create",
        "gmail_send_reply",
        "gmail_label_archive",
        "google_calendar_read",
        "google_calendar_write",
        "microsoft_graph_delegated_auth",
        "microsoft_graph_outlook_mail",
        "microsoft_graph_outlook_mail_send",
        "microsoft_graph_teams",
        "outlook_calendar_read",
        "notification_webhook",
        "ai_provider",
    }.issubset(keys)


def test_provider_status_reports_delegated_graph_auth(tmp_path):
    token_file = tmp_path / "microsoft_graph_token.json"
    token_file.write_text("{}", encoding="utf-8")
    status = provider_status_matrix(
        Settings(
            _env_file=None,
            microsoft_graph_enabled=True,
            microsoft_graph_auth_mode="delegated",
            microsoft_tenant_id="tenant",
            microsoft_client_id="client",
            microsoft_graph_token_file=str(token_file),
            microsoft_graph_outlook_mail_enabled=True,
        )
    )

    assert status["microsoft_graph_delegated_auth"]["state"] == "live"
    assert status["microsoft_graph_outlook_mail"]["mode"] == "delegated Graph"
    assert status["microsoft_graph_outlook_mail_send"]["state"] == "disabled"
    assert status["outlook_calendar_read"]["state"] == "disabled"


def test_provider_status_route_loads():
    with TestClient(app) as client:
        response = client.get("/providers")
        api_response = client.get("/api/providers/status")

    assert response.status_code == 200
    assert "Provider Status" in response.text
    assert "Gmail external draft creation" in response.text
    assert api_response.status_code == 200
    assert "gmail_read" in api_response.json()


@pytest.mark.skipif(
    not Path("client_secret.json").exists(),
    reason="live Gmail/Calendar integration seam requires local OAuth credentials",
)
def test_live_provider_credentials_seam_is_available_when_local_oauth_file_exists():
    settings = Settings(_env_file=None, gmail_client_secrets_file="./client_secret.json")
    status = provider_status_matrix(settings)
    assert status["gmail_read"]["state"] == "live"
