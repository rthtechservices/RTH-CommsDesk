from __future__ import annotations

import urllib.error

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services import live_ai_client
from app.services.live_ai_client import (
    AzureOpenAIJsonClient,
    OpenAICompatibleJsonClient,
    ai_provider_status,
    build_openai_json_client,
)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body


def test_azure_openai_url_construction_and_api_key_header():
    captured = {}

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse(b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}')

    client = AzureOpenAIJsonClient(
        api_key="azure-secret",
        endpoint="https://rth-commsdesk-resource.cognitiveservices.azure.com/",
        deployment="gpt-5.4-mini",
        api_version="2025-04-01-preview",
        timeout_seconds=7,
        max_tokens=50,
        temperature=0.1,
        opener=fake_opener,
    )

    result = client.complete_json(system_prompt="Return JSON.", user_prompt="Return ok.")

    assert result == {"ok": True}
    assert captured["url"] == (
        "https://rth-commsdesk-resource.cognitiveservices.azure.com/openai/deployments/"
        "gpt-5.4-mini/chat/completions?api-version=2025-04-01-preview"
    )
    assert captured["headers"]["api-key"] == "azure-secret"
    assert "authorization" not in captured["headers"]


def test_azure_openai_ignores_legacy_ai_base_url_responses_endpoint():
    settings = Settings(
        _env_file=None,
        ai_provider="azure_openai",
        ai_base_url=(
            "https://rth-commsdesk-resource.cognitiveservices.azure.com/openai/responses"
            "?api-version=2025-04-01-preview"
        ),
        azure_openai_endpoint="https://rth-commsdesk-resource.cognitiveservices.azure.com",
        azure_openai_api_key="secret",
        azure_openai_deployment="gpt-5.4-mini",
        azure_openai_api_version="2025-04-01-preview",
    )

    client = build_openai_json_client(settings)

    assert isinstance(client, AzureOpenAIJsonClient)
    assert client.chat_completions_url == (
        "https://rth-commsdesk-resource.cognitiveservices.azure.com/openai/deployments/"
        "gpt-5.4-mini/chat/completions?api-version=2025-04-01-preview"
    )


def test_openai_compatible_url_and_bearer_header_still_work():
    captured = {}

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse(b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}')

    client = OpenAICompatibleJsonClient(
        api_key="openai-secret",
        model="gpt-test",
        base_url="https://api.example.test/v1/",
        timeout_seconds=7,
        max_tokens=50,
        temperature=0.1,
        opener=fake_opener,
    )

    result = client.complete_json(system_prompt="Return JSON.", user_prompt="Return ok.")

    assert result == {"ok": True}
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer openai-secret"
    assert "api-key" not in captured["headers"]


def test_ai_provider_status_reports_azure_openai_correctly():
    settings = Settings(
        _env_file=None,
        ai_provider="azure_openai",
        azure_openai_endpoint="https://rth-commsdesk-resource.cognitiveservices.azure.com",
        azure_openai_api_key="secret",
        azure_openai_deployment="gpt-5.4-mini",
        azure_openai_api_version="2025-04-01-preview",
    )

    status = ai_provider_status(settings)

    assert status.requested_provider == "azure_openai"
    assert status.effective_provider == "azure_openai"
    assert status.deployment == "gpt-5.4-mini"
    assert status.endpoint_host == "rth-commsdesk-resource.cognitiveservices.azure.com"
    assert status.live_enabled is True


def test_mock_provider_remains_default():
    status = ai_provider_status(Settings(_env_file=None))

    assert status.requested_provider == "mock"
    assert status.effective_provider == "mock"
    assert status.live_enabled is False


def test_api_ai_status_reports_azure_openai(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="azure_openai",
        azure_openai_endpoint="https://rth-commsdesk-resource.cognitiveservices.azure.com",
        azure_openai_api_key="secret",
        azure_openai_deployment="gpt-5.4-mini",
        azure_openai_api_version="2025-04-01-preview",
    )
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/api/ai/status")

    assert response.status_code == 200
    data = response.json()
    assert data["requested_provider"] == "azure_openai"
    assert data["effective_provider"] == "azure_openai"
    assert data["deployment"] == "gpt-5.4-mini"
    assert data["endpoint_host"] == "rth-commsdesk-resource.cognitiveservices.azure.com"


def test_api_ai_test_reports_sanitized_http_failures(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="azure_openai",
        azure_openai_endpoint="https://rth-commsdesk-resource.cognitiveservices.azure.com",
        azure_openai_api_key="super-secret-key",
        azure_openai_deployment="gpt-5.4-mini",
        azure_openai_api_version="2025-04-01-preview",
    )
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(live_ai_client.urllib.request, "urlopen", fake_urlopen)

    with TestClient(app) as client:
        response = client.post("/api/ai/test")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "provider": "azure_openai",
        "model": "",
        "deployment": "gpt-5.4-mini",
        "endpoint_host": "rth-commsdesk-resource.cognitiveservices.azure.com",
        "success": False,
        "http_status_code": 404,
        "error_category": "not_found",
    }
    assert "super-secret-key" not in response.text
    assert "openai/deployments" not in response.text


def test_api_ai_test_maps_common_http_failure_categories(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="openai-secret-key",
        ai_model="gpt-test",
        ai_base_url="https://api.example.test/v1",
    )
    monkeypatch.setattr("app.api.routes.get_settings", lambda: settings)

    def run_for_status(status_code: int) -> dict:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                status_code,
                "error",
                hdrs=None,
                fp=None,
            )

        monkeypatch.setattr(live_ai_client.urllib.request, "urlopen", fake_urlopen)
        with TestClient(app) as client:
            return client.post("/api/ai/test").json()

    assert run_for_status(401)["error_category"] == "auth_error"
    assert run_for_status(400)["error_category"] == "bad_request"
    assert run_for_status(404)["error_category"] == "not_found"
