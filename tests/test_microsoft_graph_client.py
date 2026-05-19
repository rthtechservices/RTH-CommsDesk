from __future__ import annotations

import json
import time
import urllib.error
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.microsoft_graph_client import (
    MicrosoftGraphAuthorizationRequired,
    MicrosoftGraphMailService,
    test_microsoft_graph_connection as run_graph_connection_test,
)


def test_delegated_graph_mail_read_uses_me_messages_and_pages(tmp_path: Path) -> None:
    token_file = tmp_path / "microsoft_graph_token.json"
    token_file.write_text(
        json.dumps({"access_token": "delegated-token", "expires_at": time.time() + 3600}),
        encoding="utf-8",
    )
    fake = FakeGraphTransport(
        {
            "https://graph.microsoft.com/v1.0/me/messages": [
                {
                    "status": 200,
                    "json": {
                        "value": [{"id": "m1"}, {"id": "m2"}],
                        "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?page=2",
                    },
                },
                {"status": 200, "json": {"value": [{"id": "m3"}]}},
            ]
        }
    )
    service = MicrosoftGraphMailService(
        Settings(
            _env_file=None,
            microsoft_graph_enabled=True,
            microsoft_graph_auth_mode="delegated",
            microsoft_graph_outlook_mail_enabled=True,
            microsoft_tenant_id="tenant",
            microsoft_client_id="client",
            microsoft_account="me",
            microsoft_graph_token_file=str(token_file),
        ),
        urlopen=fake,
    )

    messages = service.fetch_messages(limit=3)

    assert [row["id"] for row in messages] == ["m1", "m2", "m3"]
    assert fake.requests[0].full_url.startswith("https://graph.microsoft.com/v1.0/me/messages")
    query = parse_qs(urlparse(fake.requests[0].full_url).query)
    assert "$select" in query
    assert "bodyPreview" in query["$select"][0]
    assert fake.requests[1].full_url == "https://graph.microsoft.com/v1.0/me/messages?page=2"


def test_app_only_graph_mail_read_preserves_users_client_credentials_seam() -> None:
    fake = FakeGraphTransport(
        {
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token": [
                {"status": 200, "json": {"access_token": "app-token"}}
            ],
            "https://graph.microsoft.com/v1.0/users/rohan%40example.com/messages": [
                {"status": 200, "json": {"value": [{"id": "app-message"}]}}
            ],
        }
    )
    service = MicrosoftGraphMailService(
        Settings(
            _env_file=None,
            microsoft_graph_enabled=True,
            microsoft_graph_auth_mode="app_only",
            microsoft_graph_outlook_mail_enabled=True,
            microsoft_tenant_id="tenant",
            microsoft_client_id="client",
            microsoft_client_secret="secret",
            microsoft_account="rohan@example.com",
        ),
        urlopen=fake,
    )

    messages = service.fetch_messages(limit=1)

    assert messages == [{"id": "app-message"}]
    token_request = fake.requests[0]
    assert token_request.full_url.endswith("/tenant/oauth2/v2.0/token")
    assert b"client_credentials" in (token_request.data or b"")
    assert fake.requests[1].full_url.startswith(
        "https://graph.microsoft.com/v1.0/users/rohan%40example.com/messages"
    )


def test_delegated_graph_test_starts_device_flow_without_returning_tokens(tmp_path: Path) -> None:
    token_file = tmp_path / "microsoft_graph_token.json"
    fake = FakeGraphTransport(
        {
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/devicecode": [
                {
                    "status": 200,
                    "json": {
                        "device_code": "secret-device-code",
                        "user_code": "ABCD-EFGH",
                        "verification_uri": "https://microsoft.com/devicelogin",
                        "expires_in": 900,
                    },
                }
            ]
        }
    )
    service = MicrosoftGraphMailService(
        Settings(
            _env_file=None,
            microsoft_graph_enabled=True,
            microsoft_graph_auth_mode="delegated",
            microsoft_tenant_id="tenant",
            microsoft_client_id="client",
            microsoft_graph_token_file=str(token_file),
        ),
        urlopen=fake,
    )

    try:
        service.test_connection()
    except MicrosoftGraphAuthorizationRequired as exc:
        assert exc.category == "authorization_required"
        assert exc.status_code == 200
        assert "secret-device-code" not in str(exc)
        assert "ABCD-EFGH" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected delegated authorization requirement")

    stored = json.loads(token_file.read_text(encoding="utf-8"))
    assert stored["device_code"] == "secret-device-code"


def test_graph_test_result_is_sanitized() -> None:
    result = run_graph_connection_test(
        Settings(
            _env_file=None,
            microsoft_graph_enabled=False,
            microsoft_graph_auth_mode="delegated",
            microsoft_tenant_id="tenant",
            microsoft_client_id="client",
            microsoft_client_secret="super-secret",
        )
    )

    assert result["auth_mode"] == "delegated"
    assert result["tenant_configured"] is True
    assert result["client_configured"] is True
    assert result["client_secret_configured"] is True
    assert result["success"] is False
    assert result["error_category"] == "disabled"
    assert "super-secret" not in json.dumps(result)


def test_graph_test_api_route_returns_sanitized_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.test_microsoft_graph_connection",
        lambda: {
            "auth_mode": "delegated",
            "account": "me",
            "tenant_configured": True,
            "client_configured": True,
            "client_secret_configured": False,
            "success": False,
            "http_status": 401,
            "error_category": "auth_error",
            "error_message": "Microsoft Graph authorization failed",
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/graph/test")

    assert response.status_code == 200
    data = response.json()
    assert data["auth_mode"] == "delegated"
    assert data["http_status"] == 401
    assert "token" not in json.dumps(data).lower()
    assert "super-secret" not in json.dumps(data)


class FakeGraphTransport:
    def __init__(self, routes: dict[str, list[dict]]) -> None:
        self.routes = routes
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: int) -> "FakeGraphResponse":
        self.requests.append(request)
        route_key = request.full_url.split("?", 1)[0]
        responses = self.routes.get(route_key)
        if not responses:
            raise AssertionError(f"Unexpected Graph request: {request.full_url}")
        response = responses.pop(0)
        status = int(response["status"])
        payload = json.dumps(response["json"]).encode("utf-8")
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "Graph error", {}, None)
        return FakeGraphResponse(status=status, payload=payload)


class FakeGraphResponse:
    def __init__(self, *, status: int, payload: bytes) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self) -> "FakeGraphResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.payload
