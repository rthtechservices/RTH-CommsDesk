from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.core.config import Settings

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_DRAFT_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

GMAIL_READONLY_SCOPES = [GMAIL_READONLY_SCOPE]
GMAIL_WRITE_SCOPES = [GMAIL_DRAFT_SCOPE, GMAIL_SEND_SCOPE, GMAIL_MODIFY_SCOPE]
GMAIL_COMBINED_SCOPES = [GMAIL_READONLY_SCOPE, *GMAIL_WRITE_SCOPES]


def gmail_required_scopes(settings: Settings) -> list[str]:
    if gmail_write_scope_requested(settings):
        return list(GMAIL_COMBINED_SCOPES)
    return list(GMAIL_READONLY_SCOPES)


def gmail_write_scope_requested(settings: Settings) -> bool:
    return any(
        (
            settings.gmail_write_enabled,
            settings.gmail_draft_create_enabled,
            settings.gmail_send_enabled,
            settings.gmail_label_archive_enabled,
        )
    )


def missing_gmail_scopes(
    *,
    creds: Any | None = None,
    token_file: Path | None = None,
    required_scopes: Iterable[str],
) -> list[str]:
    granted_scopes = _extract_granted_scopes(creds=creds, token_file=token_file)
    if granted_scopes is None:
        return []
    return [scope for scope in required_scopes if scope not in granted_scopes]


def gmail_scope_reauth_message(missing_scopes: Iterable[str]) -> str:
    missing = ", ".join(missing_scopes) or "unknown required Gmail scope"
    return (
        "Gmail OAuth token is missing required scope(s): "
        f"{missing}. Delete gmail_token.json, then re-authorize after enabling the "
        "matching Gmail write feature flag(s)."
    )


def _extract_granted_scopes(*, creds: Any | None, token_file: Path | None) -> set[str] | None:
    token_scopes = _extract_token_file_scopes(token_file) if token_file else None
    if token_scopes is not None:
        return token_scopes

    for attr in ("granted_scopes", "scopes"):
        scopes = getattr(creds, attr, None) if creds is not None else None
        parsed = _normalize_scopes(scopes)
        if parsed is not None:
            return parsed
    return None


def _extract_token_file_scopes(token_file: Path) -> set[str] | None:
    if not token_file.exists():
        return None
    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    for key in ("scopes", "scope", "granted_scopes"):
        parsed = _normalize_scopes(data.get(key))
        if parsed is not None:
            return parsed
    return None


def _normalize_scopes(value: Any) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {scope for scope in value.split() if scope}
    try:
        return {str(scope) for scope in value if str(scope)}
    except TypeError:
        return None
