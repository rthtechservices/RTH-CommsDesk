from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

GRAPH_TOKEN_SCOPE = "https://graph.microsoft.com/.default"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


class MicrosoftGraphConfigurationError(RuntimeError):
    """Raised when Microsoft Graph is not intentionally configured."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        category: str = "configuration_error",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.category = category


class MicrosoftGraphAuthorizationRequired(MicrosoftGraphConfigurationError):
    """Raised when delegated Graph auth needs local user action."""


@dataclass(frozen=True)
class GraphJsonResponse:
    data: dict[str, Any]
    status_code: int | None


UrlOpen = Callable[[urllib.request.Request, int], Any]


class MicrosoftGraphMailService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        urlopen: UrlOpen | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._urlopen = urlopen or urllib.request.urlopen
        self._access_token: str | None = None

    def fetch_messages(self, limit: int = 100, since: datetime | None = None) -> list[dict[str, Any]]:
        self._require_mail_read_enabled()
        params = self._message_query_params(page_size=min(max(limit, 1), 100), since=since)
        url = f"{self._messages_url()}?{urllib.parse.urlencode(params)}"
        messages: list[dict[str, Any]] = []
        pages_read = 0
        while url and len(messages) < limit and pages_read < 20:
            pages_read += 1
            response = self._get_json_response(url)
            rows = list(response.data.get("value") or [])
            remaining = limit - len(messages)
            messages.extend(rows[:remaining])
            next_link = response.data.get("@odata.nextLink")
            url = str(next_link) if next_link and len(messages) < limit else ""
        return messages

    def test_connection(self) -> GraphJsonResponse:
        self._require_graph_enabled()
        url = f"{self._account_url()}?{urllib.parse.urlencode({'$select': 'id,displayName,mail,userPrincipalName'})}"
        return self._get_json_response(url)

    def _message_query_params(self, *, page_size: int, since: datetime | None) -> dict[str, str]:
        params = {
            "$top": str(page_size),
            "$orderby": "receivedDateTime desc",
            "$select": (
                "id,conversationId,receivedDateTime,from,toRecipients,ccRecipients,"
                "subject,bodyPreview,hasAttachments,isRead"
            ),
        }
        if since:
            params["$filter"] = f"receivedDateTime ge {since.isoformat().replace('+00:00', 'Z')}"
        return params

    def _require_graph_enabled(self) -> None:
        if not self.settings.microsoft_graph_enabled:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph is disabled by MICROSOFT_GRAPH_ENABLED",
                category="disabled",
            )
        missing = [
            name
            for name, value in (
                ("MICROSOFT_TENANT_ID", self.settings.microsoft_tenant_id),
                ("MICROSOFT_CLIENT_ID", self.settings.microsoft_client_id),
            )
            if not value
        ]
        if self._auth_mode() == "app_only" and not self.settings.microsoft_client_secret:
            missing.append("MICROSOFT_CLIENT_SECRET")
        if missing:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph is missing required configuration: " + ", ".join(missing)
            )

    def _require_mail_read_enabled(self) -> None:
        self._require_graph_enabled()
        if not self.settings.microsoft_graph_outlook_mail_enabled:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph Outlook mail read is disabled by MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED",
                category="disabled",
            )

    def _auth_mode(self) -> str:
        raw = (self.settings.microsoft_graph_auth_mode or "app_only").strip().lower()
        if raw in {"delegated", "app_only"}:
            return raw
        raise MicrosoftGraphConfigurationError(
            "MICROSOFT_GRAPH_AUTH_MODE must be delegated or app_only"
        )

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        if self._auth_mode() == "delegated":
            self._access_token = self._delegated_token()
        else:
            self._access_token = self._app_only_token()
        return self._access_token

    def _app_only_token(self) -> str:
        tenant = urllib.parse.quote(self.settings.microsoft_tenant_id or "", safe="")
        response = self._post_form_json(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            {
                "client_id": self.settings.microsoft_client_id or "",
                "client_secret": self.settings.microsoft_client_secret or "",
                "grant_type": "client_credentials",
                "scope": GRAPH_TOKEN_SCOPE,
            },
        )
        token = response.data.get("access_token")
        if not token:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph token response was missing access_token",
                status_code=response.status_code,
                category="auth_error",
            )
        return str(token)

    def _delegated_token(self) -> str:
        token_data = self._load_token_file()
        access_token = token_data.get("access_token")
        expires_at = float(token_data.get("expires_at") or 0)
        if access_token and expires_at > time.time() + 60:
            return str(access_token)
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            return self._refresh_delegated_token(str(refresh_token))
        pending_device_code = token_data.get("device_code")
        if pending_device_code:
            return self._poll_delegated_device_code(token_data)
        return self._start_delegated_device_flow()

    def _refresh_delegated_token(self, refresh_token: str) -> str:
        response = self._post_form_json(
            self._token_url(),
            {
                "client_id": self.settings.microsoft_client_id or "",
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": self._delegated_scopes(),
            },
        )
        return self._store_delegated_token_response(response)

    def _start_delegated_device_flow(self) -> str:
        response = self._post_form_json(
            self._device_code_url(),
            {
                "client_id": self.settings.microsoft_client_id or "",
                "scope": self._delegated_scopes(),
            },
        )
        data = response.data
        device_code = data.get("device_code")
        if not device_code:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph device-code response was missing device_code",
                status_code=response.status_code,
                category="auth_error",
            )
        expires_at = time.time() + int(data.get("expires_in") or 900)
        pending = {
            "auth_mode": "delegated",
            "device_code": device_code,
            "user_code": data.get("user_code"),
            "verification_uri": data.get("verification_uri"),
            "message": data.get("message"),
            "expires_at": expires_at,
            "scope": self._delegated_scopes(),
        }
        self._save_token_file(pending)
        verification = data.get("verification_uri") or "https://microsoft.com/devicelogin"
        user_code = data.get("user_code") or "the device code in MICROSOFT_GRAPH_TOKEN_FILE"
        raise MicrosoftGraphAuthorizationRequired(
            (
                "Delegated Microsoft Graph authorization is required. Visit "
                f"{verification}, enter code {user_code}, then retry POST /api/graph/test."
            ),
            status_code=response.status_code,
            category="authorization_required",
        )

    def _poll_delegated_device_code(self, token_data: dict[str, Any]) -> str:
        if float(token_data.get("expires_at") or 0) <= time.time():
            self._save_token_file({})
            raise MicrosoftGraphAuthorizationRequired(
                "Delegated Microsoft Graph device-code authorization expired; retry to start a new flow.",
                category="authorization_expired",
            )
        try:
            response = self._post_form_json(
                self._token_url(),
                {
                    "client_id": self.settings.microsoft_client_id or "",
                    "grant_type": DEVICE_CODE_GRANT,
                    "device_code": str(token_data.get("device_code") or ""),
                },
            )
        except MicrosoftGraphConfigurationError as exc:
            if exc.category in {"authorization_pending", "slow_down"}:
                raise MicrosoftGraphAuthorizationRequired(
                    "Delegated Microsoft Graph authorization is pending; complete login and retry.",
                    status_code=exc.status_code,
                    category=exc.category,
                ) from exc
            raise
        return self._store_delegated_token_response(response)

    def _store_delegated_token_response(self, response: GraphJsonResponse) -> str:
        token = response.data.get("access_token")
        if not token:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph delegated token response was missing access_token",
                status_code=response.status_code,
                category="auth_error",
            )
        expires_in = int(response.data.get("expires_in") or 3600)
        token_data = {
            "auth_mode": "delegated",
            "token_type": response.data.get("token_type"),
            "access_token": token,
            "refresh_token": response.data.get("refresh_token"),
            "scope": response.data.get("scope") or self._delegated_scopes(),
            "expires_at": time.time() + expires_in,
        }
        self._save_token_file(token_data)
        return str(token)

    def _delegated_scopes(self) -> str:
        scopes = " ".join((self.settings.microsoft_graph_scopes or "").split())
        return scopes or "User.Read Mail.Read offline_access"

    def _token_url(self) -> str:
        tenant = urllib.parse.quote(self.settings.microsoft_tenant_id or "", safe="")
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    def _device_code_url(self) -> str:
        tenant = urllib.parse.quote(self.settings.microsoft_tenant_id or "", safe="")
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode"

    def _messages_url(self) -> str:
        return f"{self._account_url()}/messages"

    def _account_url(self) -> str:
        base = self.settings.microsoft_graph_base_url.rstrip("/")
        account = (self.settings.microsoft_account or "me").strip()
        if self._auth_mode() == "delegated" and account.lower() == "me":
            return f"{base}/me"
        user = urllib.parse.quote(account, safe="")
        return f"{base}/users/{user}"

    def _post_form_json(self, url: str, form: dict[str, str]) -> GraphJsonResponse:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(form).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        return self._request_json(request, timeout=20)

    def _get_json_response(self, url: str) -> GraphJsonResponse:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._token()}", "Accept": "application/json"},
            method="GET",
        )
        return self._request_json(request, timeout=30)

    def _request_json(self, request: urllib.request.Request, *, timeout: int) -> GraphJsonResponse:
        try:
            with self._urlopen(request, timeout=timeout) as response:
                status_code = _response_status(response)
                raw = response.read().decode("utf-8")
                return GraphJsonResponse(data=json.loads(raw or "{}"), status_code=status_code)
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            category, message = _graph_error(exc)
            raise MicrosoftGraphConfigurationError(
                message,
                status_code=status_code,
                category=category,
            ) from exc
        except TimeoutError as exc:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph request timed out",
                category="timeout",
            ) from exc
        except OSError as exc:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph request failed before a response was received",
                category="connection_error",
            ) from exc
        except json.JSONDecodeError as exc:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph returned invalid JSON",
                category="invalid_json",
            ) from exc

    def _load_token_file(self) -> dict[str, Any]:
        path = Path(self.settings.microsoft_graph_token_file).expanduser()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph token file is unreadable; delete it and reauthorize",
                category="token_file_error",
            ) from exc
        return data if isinstance(data, dict) else {}

    def _save_token_file(self, data: dict[str, Any]) -> None:
        path = Path(self.settings.microsoft_graph_token_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def test_microsoft_graph_connection(settings: Settings | None = None) -> dict[str, Any]:
    active = settings or get_settings()
    service = MicrosoftGraphMailService(active)
    result = {
        "auth_mode": _normalized_auth_mode(active),
        "account": active.microsoft_account,
        "tenant_configured": bool(active.microsoft_tenant_id),
        "client_configured": bool(active.microsoft_client_id),
        "client_secret_configured": bool(active.microsoft_client_secret),
        "success": False,
        "http_status": None,
        "error_category": None,
        "error_message": None,
    }
    try:
        response = service.test_connection()
        result["success"] = True
        result["http_status"] = response.status_code
    except MicrosoftGraphConfigurationError as exc:
        result["http_status"] = exc.status_code
        result["error_category"] = exc.category
        result["error_message"] = str(exc)
    return result


def _normalized_auth_mode(settings: Settings) -> str:
    raw = (settings.microsoft_graph_auth_mode or "app_only").strip().lower()
    return raw if raw in {"delegated", "app_only"} else "invalid"


def _response_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if status is not None:
        return int(status)
    getcode = getattr(response, "getcode", None)
    return int(getcode()) if callable(getcode) else None


def _graph_error(exc: urllib.error.HTTPError) -> tuple[str, str]:
    raw = exc.read().decode("utf-8", errors="replace")
    data: dict[str, Any] = {}
    if raw.strip():
        try:
            decoded = json.loads(raw)
            data = decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            pass
    graph_error = data.get("error")
    if isinstance(graph_error, dict):
        code = str(graph_error.get("code") or graph_error.get("error") or "").lower()
        message = str(graph_error.get("message") or "Microsoft Graph request failed")
    else:
        code = str(data.get("error") or "").lower()
        message = str(data.get("error_description") or raw or "Microsoft Graph request failed")
    return _error_category(exc.code, code, message), _sanitize_error_message(message)


def _error_category(status_code: int, code: str, message: str) -> str:
    text = f"{code} {message}".lower()
    if "authorization_pending" in text:
        return "authorization_pending"
    if "slow_down" in text:
        return "slow_down"
    if "invalid_grant" in text or status_code in {401, 403}:
        return "auth_error"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if 400 <= status_code < 500:
        return "bad_request"
    if status_code >= 500:
        return "provider_error"
    return "provider_error"


def _sanitize_error_message(message: str) -> str:
    text = " ".join((message or "Microsoft Graph request failed").split())
    blocked = ["access_token", "refresh_token", "client_secret", "authorization"]
    for marker in blocked:
        text = text.replace(marker, "[redacted]")
    return text[:400]
