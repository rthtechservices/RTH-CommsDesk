from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from app.core.config import Settings, get_settings


class AIProviderError(RuntimeError):
    """Raised when a configured live AI provider cannot return usable output."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "provider_error",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


@dataclass(frozen=True)
class AIProviderStatus:
    requested_provider: str
    effective_provider: str
    model: str
    deployment: str
    endpoint_host: str
    live_enabled: bool
    fallback_provider: str
    detail: str


class JsonAIClient(Protocol):
    provider: str
    model: str
    deployment: str
    endpoint_host: str

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Return parsed JSON from a provider chat-completions response."""


class OpenAICompatibleJsonClient:
    """Minimal OpenAI-compatible chat completions client for strict JSON outputs."""

    provider = "openai"
    deployment = ""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
        opener: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.opener = opener or urllib.request.urlopen
        self.endpoint_host = _host_from_url(self.base_url)

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    @property
    def provider_name(self) -> str:
        return f"openai:{self.model}"

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        request = self.build_request(system_prompt=system_prompt, user_prompt=user_prompt)
        raw = _read_response(request, timeout_seconds=self.timeout_seconds, opener=self.opener)
        return _parse_chat_json_content(raw)

    def build_request(self, *, system_prompt: str, user_prompt: str) -> urllib.request.Request:
        payload = _chat_payload(
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return urllib.request.Request(
            self.chat_completions_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )


class AzureOpenAIJsonClient:
    provider = "azure_openai"
    model = ""

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
        opener: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.deployment = deployment
        self.api_version = api_version
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.opener = opener or urllib.request.urlopen
        self.endpoint_host = _host_from_url(self.endpoint)

    @property
    def chat_completions_url(self) -> str:
        deployment = urllib.parse.quote(self.deployment, safe="")
        query = urllib.parse.urlencode({"api-version": self.api_version})
        return f"{self.endpoint}/openai/deployments/{deployment}/chat/completions?{query}"

    @property
    def provider_name(self) -> str:
        return f"azure_openai:{self.deployment}"

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        request = self.build_request(system_prompt=system_prompt, user_prompt=user_prompt)
        raw = _read_response(request, timeout_seconds=self.timeout_seconds, opener=self.opener)
        return _parse_chat_json_content(raw)

    def build_request(self, *, system_prompt: str, user_prompt: str) -> urllib.request.Request:
        payload = _chat_payload(
            model=None,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return urllib.request.Request(
            self.chat_completions_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )


def build_openai_json_client(settings: Settings | None = None) -> JsonAIClient:
    """Build the configured live JSON client.

    The function name is preserved for existing analysis/draft imports; it now dispatches to
    OpenAI-compatible or Azure OpenAI clients based on AI_PROVIDER.
    """

    active_settings = settings or get_settings()
    provider = normalize_ai_provider(active_settings.ai_provider)
    if provider == "azure_openai":
        api_key = (active_settings.azure_openai_api_key or "").strip()
        endpoint = (active_settings.azure_openai_endpoint or "").strip()
        deployment = (active_settings.azure_openai_deployment or "").strip()
        api_version = (active_settings.azure_openai_api_version or "").strip()
        if not api_key or not endpoint or not deployment or not api_version:
            raise AIProviderError("Azure OpenAI provider is not fully configured")
        return AzureOpenAIJsonClient(
            api_key=api_key,
            endpoint=endpoint,
            deployment=deployment,
            api_version=api_version,
            timeout_seconds=active_settings.ai_timeout_seconds,
            max_tokens=active_settings.ai_max_tokens,
            temperature=active_settings.ai_temperature,
        )

    api_key = (active_settings.openai_api_key or "").strip()
    model = (active_settings.ai_model or "").strip()
    if not api_key or not model:
        raise AIProviderError("OpenAI-compatible provider is not fully configured")
    return OpenAICompatibleJsonClient(
        api_key=api_key,
        model=model,
        base_url=active_settings.ai_base_url,
        timeout_seconds=active_settings.ai_timeout_seconds,
        max_tokens=active_settings.ai_max_tokens,
        temperature=active_settings.ai_temperature,
    )


def ai_provider_status(settings: Settings | None = None) -> AIProviderStatus:
    active_settings = settings or get_settings()
    requested = normalize_ai_provider(active_settings.ai_provider)
    if requested == "mock":
        return AIProviderStatus(
            requested_provider="mock",
            effective_provider="mock",
            model="",
            deployment="",
            endpoint_host="",
            live_enabled=False,
            fallback_provider="mock",
            detail="Mock provider is the default local/test provider.",
        )

    if requested == "azure_openai":
        endpoint = (active_settings.azure_openai_endpoint or "").strip()
        deployment = (active_settings.azure_openai_deployment or "").strip()
        api_key = (active_settings.azure_openai_api_key or "").strip()
        api_version = (active_settings.azure_openai_api_version or "").strip()
        live_enabled = bool(endpoint and deployment and api_key and api_version)
        return AIProviderStatus(
            requested_provider="azure_openai",
            effective_provider="azure_openai" if live_enabled else "mock",
            model="",
            deployment=deployment,
            endpoint_host=_host_from_url(endpoint),
            live_enabled=live_enabled,
            fallback_provider="mock",
            detail=(
                "Azure OpenAI is enabled with mock fallback on failure or invalid output."
                if live_enabled
                else "Azure OpenAI was requested but required environment variables are missing."
            ),
        )

    model = (active_settings.ai_model or "").strip()
    api_key = (active_settings.openai_api_key or "").strip()
    live_enabled = bool(api_key and model)
    return AIProviderStatus(
        requested_provider="openai",
        effective_provider="openai" if live_enabled else "mock",
        model=model,
        deployment="",
        endpoint_host=_host_from_url(active_settings.ai_base_url),
        live_enabled=live_enabled,
        fallback_provider="mock",
        detail=(
            "OpenAI-compatible AI is enabled with mock fallback on failure or invalid output."
            if live_enabled
            else "OpenAI-compatible AI was requested but required environment variables are missing."
        ),
    )


def test_live_ai_provider(settings: Settings | None = None) -> dict[str, Any]:
    active_settings = settings or get_settings()
    status = ai_provider_status(active_settings)
    diagnostic = _diagnostic_base(status)
    if not status.live_enabled:
        diagnostic.update(
            {
                "success": False,
                "http_status_code": None,
                "error_category": "missing_config",
            }
        )
        return diagnostic

    try:
        client = build_openai_json_client(active_settings)
        payload = client.complete_json(
            system_prompt="Return only JSON.",
            user_prompt='Return exactly this JSON object: {"ok": true}',
        )
    except AIProviderError as exc:
        diagnostic.update(
            {
                "success": False,
                "http_status_code": exc.status_code,
                "error_category": exc.category,
            }
        )
        return diagnostic
    if not isinstance(payload, dict):
        diagnostic.update(
            {
                "success": False,
                "http_status_code": None,
                "error_category": "invalid_json",
            }
        )
        return diagnostic
    diagnostic.update(
        {
            "success": True,
            "http_status_code": 200,
            "error_category": None,
        }
    )
    return diagnostic


def normalize_ai_provider(value: str | None) -> str:
    normalized = (value or "mock").strip().lower()
    if normalized in {"", "mock", "local", "deterministic"}:
        return "mock"
    if normalized in {"azure", "azure_openai", "azure-openai"}:
        return "azure_openai"
    return "openai"


def sanitize_ai_text(value: Any, *, max_length: int) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()[:max_length]


def decimal_confidence(value: Any) -> Decimal:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AIProviderError("AI output confidence was not numeric") from exc
    number = min(max(number, 0.0), 1.0)
    return Decimal(f"{number:.4f}")


def _chat_payload(
    *,
    model: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if model:
        payload["model"] = model
    return payload


def _read_response(
    request: urllib.request.Request,
    *,
    timeout_seconds: float,
    opener: Any,
) -> str:
    try:
        with opener(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise AIProviderError(
            f"AI provider HTTP error: {exc.code}",
            category=_category_for_http_status(exc.code),
            status_code=exc.code,
        ) from exc
    except TimeoutError as exc:
        raise AIProviderError("AI provider request timed out", category="timeout") from exc
    except socket.timeout as exc:
        raise AIProviderError("AI provider request timed out", category="timeout") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        category = "timeout" if isinstance(reason, TimeoutError | socket.timeout) else "provider_error"
        raise AIProviderError("AI provider request failed", category=category) from exc


def _parse_chat_json_content(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise AIProviderError(
            "AI provider returned an unexpected response shape",
            category="provider_error",
        ) from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIProviderError(
            "AI provider did not return valid JSON content",
            category="invalid_json",
        ) from exc
    if not isinstance(parsed, dict):
        raise AIProviderError("AI provider JSON content was not an object", category="invalid_json")
    return parsed


def _category_for_http_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth_error"
    if status_code == 404:
        return "not_found"
    if status_code == 400:
        return "bad_request"
    return "provider_error"


def _host_from_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.lower()


def _diagnostic_base(status: AIProviderStatus) -> dict[str, Any]:
    return {
        "provider": status.requested_provider,
        "model": status.model,
        "deployment": status.deployment,
        "endpoint_host": status.endpoint_host,
    }
