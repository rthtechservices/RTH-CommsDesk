from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime

from app.core.config import Settings


def validate_auth_configuration(settings: Settings) -> None:
    if not settings.auth_required:
        return
    missing: list[str] = []
    if not settings.app_auth_username:
        missing.append("APP_AUTH_USERNAME")
    if not settings.app_auth_password:
        missing.append("APP_AUTH_PASSWORD")
    if not settings.api_auth_token:
        missing.append("API_AUTH_TOKEN")
    if not settings.auth_session_secret:
        missing.append("AUTH_SESSION_SECRET")
    if missing:
        raise RuntimeError(
            "Authentication is enabled but required settings are missing: "
            + ", ".join(sorted(missing))
        )
    if settings.normalized_env in {"production", "prod", "staging"} and settings.auth_session_secret in {
        "local-dev-change-me",
        "change-me",
    }:
        raise RuntimeError(
            "AUTH_SESSION_SECRET must be replaced with a strong value for staging/production."
        )


def build_session_token(username: str, settings: Settings, now: datetime | None = None) -> str:
    issued = int((now or datetime.now(UTC)).timestamp())
    payload = f"{username}:{issued}"
    signature = _sign(payload, settings)
    raw = f"{payload}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def verify_session_token(token: str | None, settings: Settings, now: datetime | None = None) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, issued_at_text, signature = decoded.split(":", 2)
    except (ValueError, UnicodeDecodeError):
        return False
    payload = f"{username}:{issued_at_text}"
    expected_signature = _sign(payload, settings)
    if not hmac.compare_digest(signature, expected_signature):
        return False
    try:
        issued_at = int(issued_at_text)
    except ValueError:
        return False
    max_age_seconds = max(1, settings.auth_session_ttl_hours) * 3600
    now_ts = int((now or datetime.now(UTC)).timestamp())
    return 0 <= now_ts - issued_at <= max_age_seconds


def verify_login_credentials(username: str, password: str, settings: Settings) -> bool:
    expected_username = settings.app_auth_username or ""
    expected_password = settings.app_auth_password or ""
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
        password, expected_password
    )


def verify_api_token(
    settings: Settings,
    *,
    x_api_key: str | None = None,
    authorization: str | None = None,
) -> bool:
    expected = settings.api_auth_token or ""
    if not expected:
        return False
    token = (x_api_key or "").strip()
    if not token and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    if not token:
        return False
    return hmac.compare_digest(token, expected)


def _sign(payload: str, settings: Settings) -> str:
    secret = settings.auth_session_secret.encode("utf-8")
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest
