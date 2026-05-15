from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture()
def auth_enabled_env(monkeypatch):
    monkeypatch.setenv("APP_AUTH_ENABLED", "true")
    monkeypatch.setenv("APP_AUTH_USERNAME", "admin")
    monkeypatch.setenv("APP_AUTH_PASSWORD", "pass123")
    monkeypatch.setenv("API_AUTH_TOKEN", "dev-api-token")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-secret-value")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def test_web_auth_redirects_then_allows_login(auth_enabled_env):
    with TestClient(app) as client:
        redirect = client.get("/", follow_redirects=False)
        assert redirect.status_code == 303
        assert redirect.headers["location"].startswith("/login")

        invalid = client.post(
            "/login",
            data={"username": "admin", "password": "wrong", "next_path": "/"},
            follow_redirects=False,
        )
        assert invalid.status_code == 303
        assert "/login?error=1" in invalid.headers["location"]

        login = client.post(
            "/login",
            data={"username": "admin", "password": "pass123", "next_path": "/"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/"

        dashboard = client.get("/", follow_redirects=False)
        assert dashboard.status_code == 200


def test_api_auth_requires_token_except_notification_webhook(auth_enabled_env):
    with TestClient(app) as client:
        unauthorized = client.post("/api/contacts/noise")
        assert unauthorized.status_code == 401

        authorized = client.post("/api/contacts/noise", headers={"x-api-key": "dev-api-token"})
        assert authorized.status_code == 422

        webhook = client.post(
            "/api/notifications/webhook",
            json={"notification_id": "auth-test", "channel": "sms", "summary": "hi"},
        )
        assert webhook.status_code == 200
