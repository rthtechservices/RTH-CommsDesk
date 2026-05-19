from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from app.connectors.gmail.client import GmailConnector
from app.connectors.gmail.scopes import (
    GMAIL_COMBINED_SCOPES,
    GMAIL_DRAFT_SCOPE,
    GMAIL_MODIFY_SCOPE,
    GMAIL_READONLY_SCOPES,
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
    gmail_required_scopes,
    missing_gmail_scopes,
)
from app.core.config import Settings, get_settings
from app.services.external_provider_clients import GmailWriteClient


def test_read_only_mode_requests_only_gmail_readonly() -> None:
    settings = Settings(_env_file=None)

    assert gmail_required_scopes(settings) == GMAIL_READONLY_SCOPES


@pytest.mark.parametrize(
    "flag",
    [
        "gmail_write_enabled",
        "gmail_draft_create_enabled",
        "gmail_send_enabled",
        "gmail_label_archive_enabled",
    ],
)
def test_write_enabled_mode_requests_combined_gmail_scopes(flag: str) -> None:
    settings = Settings(_env_file=None, **{flag: True})

    assert gmail_required_scopes(settings) == GMAIL_COMBINED_SCOPES


def test_token_missing_required_scopes_forces_reauth(monkeypatch, tmp_path: Path) -> None:
    stubs = _install_google_oauth_stubs(monkeypatch)
    token_file = tmp_path / "gmail_token.json"
    secrets_file = tmp_path / "client_secret.json"
    token_file.write_text(json.dumps({"token": "read-token", "scopes": GMAIL_READONLY_SCOPES}))
    secrets_file.write_text("{}")
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("GMAIL_CLIENT_SECRETS_FILE", str(secrets_file))
    monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
    get_settings.cache_clear()

    GmailConnector()._build_service()

    assert stubs.flows == [GMAIL_COMBINED_SCOPES]
    assert stubs.built_credentials[-1].source == "flow"
    assert json.loads(token_file.read_text(encoding="utf-8"))["scopes"] == GMAIL_COMBINED_SCOPES


def test_missing_gmail_scopes_reports_exact_scopes(tmp_path: Path) -> None:
    token_file = tmp_path / "gmail_token.json"
    token_file.write_text(json.dumps({"scopes": [GMAIL_READONLY_SCOPE]}))

    assert missing_gmail_scopes(
        token_file=token_file,
        required_scopes=GMAIL_COMBINED_SCOPES,
    ) == [GMAIL_DRAFT_SCOPE, GMAIL_SEND_SCOPE, GMAIL_MODIFY_SCOPE]


@pytest.mark.parametrize(
    ("method_name", "payload"),
    [
        (
            "create_draft",
            {"to": "person@example.com", "subject": "Draft", "draft_text": "Hello"},
        ),
        ("send_reply", {"to": "person@example.com", "subject": "Re:", "body": "Hello"}),
    ],
)
def test_gmail_draft_send_does_not_reuse_read_only_token(
    monkeypatch,
    tmp_path: Path,
    method_name: str,
    payload: dict,
) -> None:
    stubs = _install_google_oauth_stubs(monkeypatch)
    token_file = tmp_path / "gmail_token.json"
    secrets_file = tmp_path / "client_secret.json"
    token_file.write_text(json.dumps({"token": "read-token", "scopes": GMAIL_READONLY_SCOPES}))
    secrets_file.write_text("{}")
    settings = Settings(
        _env_file=None,
        gmail_token_file=str(token_file),
        gmail_client_secrets_file=str(secrets_file),
        gmail_write_enabled=True,
        gmail_draft_create_enabled=True,
        gmail_send_enabled=True,
    )
    client = GmailWriteClient(settings)

    result = getattr(client, method_name)(payload)

    assert result["status"] in {"created", "sent"}
    assert stubs.flows == [GMAIL_COMBINED_SCOPES]
    assert stubs.built_credentials[-1].source == "flow"


class _GoogleOAuthStubs:
    def __init__(self) -> None:
        self.flows: list[list[str]] = []
        self.built_credentials: list[_FakeCredentials] = []


class _FakeCredentials:
    def __init__(self, scopes: list[str], *, source: str) -> None:
        self.scopes = scopes
        self.source = source
        self.valid = True
        self.expired = False
        self.refresh_token = "refresh-token"

    @classmethod
    def from_authorized_user_file(cls, filename: str, scopes: list[str]) -> "_FakeCredentials":
        return cls(scopes, source="token")

    def refresh(self, request) -> None:
        self.valid = True

    def to_json(self) -> str:
        return json.dumps({"token": f"{self.source}-token", "scopes": self.scopes})


class _FakeInstalledAppFlow:
    stubs: _GoogleOAuthStubs

    def __init__(self, scopes: list[str]) -> None:
        self.scopes = scopes

    @classmethod
    def from_client_secrets_file(cls, filename: str, scopes: list[str]) -> "_FakeInstalledAppFlow":
        cls.stubs.flows.append(list(scopes))
        return cls(scopes)

    def run_local_server(self, port: int) -> _FakeCredentials:
        return _FakeCredentials(self.scopes, source="flow")


class _FakeRequest:
    pass


class _FakeGoogleService:
    def users(self) -> "_FakeGoogleService":
        return self

    def drafts(self) -> "_FakeGoogleService":
        return self

    def messages(self) -> "_FakeGoogleService":
        return self

    def create(self, **kwargs) -> "_FakeGoogleService":
        self._result = {"id": "draft-1"}
        return self

    def send(self, **kwargs) -> "_FakeGoogleService":
        self._result = {"id": "message-1"}
        return self

    def execute(self) -> dict:
        return self._result


def _install_google_oauth_stubs(monkeypatch) -> _GoogleOAuthStubs:
    stubs = _GoogleOAuthStubs()
    _FakeInstalledAppFlow.stubs = stubs

    google_mod = types.ModuleType("google")
    auth_mod = types.ModuleType("google.auth")
    transport_mod = types.ModuleType("google.auth.transport")
    requests_mod = types.ModuleType("google.auth.transport.requests")
    oauth2_mod = types.ModuleType("google.oauth2")
    credentials_mod = types.ModuleType("google.oauth2.credentials")
    authlib_mod = types.ModuleType("google_auth_oauthlib")
    flow_mod = types.ModuleType("google_auth_oauthlib.flow")
    api_mod = types.ModuleType("googleapiclient")
    discovery_mod = types.ModuleType("googleapiclient.discovery")

    requests_mod.Request = _FakeRequest
    credentials_mod.Credentials = _FakeCredentials
    flow_mod.InstalledAppFlow = _FakeInstalledAppFlow

    def fake_build(service_name: str, version: str, credentials: _FakeCredentials):
        stubs.built_credentials.append(credentials)
        return _FakeGoogleService()

    discovery_mod.build = fake_build

    google_mod.auth = auth_mod
    google_mod.oauth2 = oauth2_mod
    auth_mod.transport = transport_mod
    transport_mod.requests = requests_mod
    oauth2_mod.credentials = credentials_mod
    authlib_mod.flow = flow_mod
    api_mod.discovery = discovery_mod

    for name, module in {
        "google": google_mod,
        "google.auth": auth_mod,
        "google.auth.transport": transport_mod,
        "google.auth.transport.requests": requests_mod,
        "google.oauth2": oauth2_mod,
        "google.oauth2.credentials": credentials_mod,
        "google_auth_oauthlib": authlib_mod,
        "google_auth_oauthlib.flow": flow_mod,
        "googleapiclient": api_mod,
        "googleapiclient.discovery": discovery_mod,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    return stubs
