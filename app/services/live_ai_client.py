from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings


class AIProviderError(RuntimeError):
    """Raised when a configured live AI provider cannot return usable output."""


@dataclass(frozen=True)
class AIProviderStatus:
    requested_provider: str
    effective_provider: str
    model: str
    live_enabled: bool
    fallback_provider: str
    detail: str


class OpenAICompatibleJsonClient:
    """Minimal OpenAI-compatible chat completions client for strict JSON outputs."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise AIProviderError(f"AI provider HTTP error: {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AIProviderError("AI provider request failed or timed out") from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError("AI provider returned an unexpected response shape") from exc

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI provider did not return valid JSON content") from exc
        if not isinstance(parsed, dict):
            raise AIProviderError("AI provider JSON content was not an object")
        return parsed


def build_openai_json_client(settings: Settings | None = None) -> OpenAICompatibleJsonClient:
    active_settings = settings or get_settings()
    api_key = (active_settings.openai_api_key or "").strip()
    model = (active_settings.ai_model or "").strip()
    if not api_key or not model:
        raise AIProviderError("Live AI provider is not fully configured")
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
    requested = (active_settings.ai_provider or "mock").strip().lower() or "mock"
    model = (active_settings.ai_model or "").strip()
    live_requested = requested not in {"mock", "local", "deterministic"}
    live_enabled = live_requested and bool((active_settings.openai_api_key or "").strip() and model)
    if not live_requested:
        return AIProviderStatus(
            requested_provider="mock",
            effective_provider="mock",
            model="",
            live_enabled=False,
            fallback_provider="mock",
            detail="Mock provider is the default local/test provider.",
        )
    if live_enabled:
        return AIProviderStatus(
            requested_provider=requested,
            effective_provider=requested,
            model=model,
            live_enabled=True,
            fallback_provider="mock",
            detail="Live AI is enabled with mock fallback on failure or invalid output.",
        )
    return AIProviderStatus(
        requested_provider=requested,
        effective_provider="mock",
        model=model,
        live_enabled=False,
        fallback_provider="mock",
        detail="Live AI was requested but required environment variables are missing.",
    )


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
