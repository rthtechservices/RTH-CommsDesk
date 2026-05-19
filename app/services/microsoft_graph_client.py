from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from app.core.config import Settings, get_settings


class MicrosoftGraphConfigurationError(RuntimeError):
    """Raised when Microsoft Graph is not intentionally configured."""


class MicrosoftGraphMailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._access_token: str | None = None

    def fetch_messages(self, limit: int = 100, since: datetime | None = None) -> list[dict[str, Any]]:
        self._require_enabled()
        params = {
            "$top": str(min(max(limit, 1), 100)),
            "$orderby": "receivedDateTime desc",
            "$select": (
                "id,conversationId,receivedDateTime,from,toRecipients,ccRecipients,"
                "subject,bodyPreview,hasAttachments,isRead"
            ),
        }
        if since:
            params["$filter"] = f"receivedDateTime ge {since.isoformat().replace('+00:00', 'Z')}"
        user = urllib.parse.quote(self.settings.microsoft_account or "me", safe="")
        url = f"{self.settings.microsoft_graph_base_url.rstrip('/')}/users/{user}/messages"
        data = self._get_json(f"{url}?{urllib.parse.urlencode(params)}")
        return list(data.get("value") or [])

    def _require_enabled(self) -> None:
        if not (self.settings.microsoft_graph_enabled and self.settings.microsoft_graph_outlook_mail_enabled):
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph Outlook mail is disabled by feature flags"
            )
        missing = [
            name
            for name, value in (
                ("MICROSOFT_TENANT_ID", self.settings.microsoft_tenant_id),
                ("MICROSOFT_CLIENT_ID", self.settings.microsoft_client_id),
                ("MICROSOFT_CLIENT_SECRET", self.settings.microsoft_client_secret),
            )
            if not value
        ]
        if missing:
            raise MicrosoftGraphConfigurationError(
                "Microsoft Graph is missing required configuration: " + ", ".join(missing)
            )

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        tenant = urllib.parse.quote(self.settings.microsoft_tenant_id or "", safe="")
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        payload = urllib.parse.urlencode(
            {
                "client_id": self.settings.microsoft_client_id or "",
                "client_secret": self.settings.microsoft_client_secret or "",
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        token = data.get("access_token")
        if not token:
            raise MicrosoftGraphConfigurationError("Microsoft Graph token response was missing access_token")
        self._access_token = token
        return token

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._token()}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise MicrosoftGraphConfigurationError(
                f"Microsoft Graph request failed with HTTP {exc.code}"
            ) from exc
