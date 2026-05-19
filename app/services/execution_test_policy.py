from __future__ import annotations

import json
from dataclasses import dataclass
from email.utils import parseaddr

from app.core.config import Settings, get_settings
from app.models.entities import ExecutionActionType, ExecutionRecord


@dataclass(frozen=True)
class AllowlistEntry:
    value: str
    is_domain: bool


@dataclass(frozen=True)
class PolicyCheck:
    key: str
    label: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class TestExecutionReadiness:
    action_type: str
    provider: str
    dry_run: bool
    target: str
    target_kind: str
    allowlist_match: bool | None
    allowed: bool
    blocked_reason: str | None
    next_action: str
    checks: tuple[PolicyCheck, ...]
    required_flags: tuple[str, ...]


EMAIL_ACTIONS = {
    ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
    ExecutionActionType.SEND_GMAIL_REPLY,
}

CALENDAR_ACTIONS = {ExecutionActionType.CREATE_CALENDAR_EVENT}


def parse_execution_test_allowlist(raw: str | None) -> tuple[AllowlistEntry, ...]:
    entries: list[AllowlistEntry] = []
    for item in (raw or "").split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized.startswith("@") and "." in normalized:
            entries.append(AllowlistEntry(normalized, True))
            continue
        email = normalize_email_address(normalized)
        if email:
            entries.append(AllowlistEntry(email, False))
    return tuple(dict.fromkeys(entries))


def normalize_email_address(value: str | None) -> str:
    if not value:
        return ""
    _, parsed = parseaddr(value.strip())
    return parsed.strip().lower()


def recipient_is_allowlisted(
    recipient: str | None,
    entries: tuple[AllowlistEntry, ...],
) -> bool:
    email = normalize_email_address(recipient)
    if not email or "@" not in email:
        return False
    domain = "@" + email.rsplit("@", 1)[1]
    return any(
        email == entry.value if not entry.is_domain else domain == entry.value
        for entry in entries
    )


def readiness_for_execution(
    record: ExecutionRecord,
    settings: Settings | None = None,
) -> TestExecutionReadiness:
    active = settings or get_settings()
    return readiness_for_payload(
        record.action_type,
        _parse_payload(record.payload_json),
        active,
    )


def readiness_for_payload(
    action_type: ExecutionActionType,
    payload: dict | None = None,
    settings: Settings | None = None,
) -> TestExecutionReadiness:
    active = settings or get_settings()
    payload = payload or {}
    target = _target_for_action(action_type, payload, active)
    target_kind = "recipient" if action_type in EMAIL_ACTIONS else "calendar"
    entries = parse_execution_test_allowlist(active.execution_test_email_allowlist)
    allowlist_match = (
        recipient_is_allowlisted(target, entries) if action_type in EMAIL_ACTIONS else None
    )
    required_flags = _required_flags(action_type, active)
    checks = _checks_for_action(
        action_type,
        active,
        entries,
        allowlist_match,
    )
    blocker = next((check for check in checks if not check.passed), None)
    allowed = blocker is None
    return TestExecutionReadiness(
        action_type=action_type.value,
        provider=active.execution_provider,
        dry_run=active.external_write_dry_run,
        target=target or "-",
        target_kind=target_kind,
        allowlist_match=allowlist_match,
        allowed=allowed,
        blocked_reason=blocker.detail if blocker else None,
        next_action=_next_action(action_type, allowed, active),
        checks=tuple(checks),
        required_flags=required_flags,
    )


def ensure_test_execution_allowed(
    record: ExecutionRecord,
    settings: Settings | None = None,
) -> TestExecutionReadiness:
    readiness = readiness_for_execution(record, settings)
    if not readiness.allowed:
        raise RuntimeError(readiness.blocked_reason or "Test execution is blocked")
    return readiness


def _checks_for_action(
    action_type: ExecutionActionType,
    settings: Settings,
    entries: tuple[AllowlistEntry, ...],
    allowlist_match: bool | None,
) -> list[PolicyCheck]:
    checks = [
        PolicyCheck(
            "operational_test_mode",
            "OPERATIONAL_TEST_MODE",
            settings.operational_test_mode,
            (
                "Operational test mode is enabled."
                if settings.operational_test_mode
                else "Blocked: operational test mode disabled. Set OPERATIONAL_TEST_MODE=true."
            ),
        ),
        PolicyCheck(
            "execution_provider",
            "EXECUTION_PROVIDER",
            (settings.execution_provider or "").strip().lower() == "external",
            (
                "Execution provider is external."
                if (settings.execution_provider or "").strip().lower() == "external"
                else "Blocked: execution provider not external. Set EXECUTION_PROVIDER=external."
            ),
        ),
    ]
    if action_type in EMAIL_ACTIONS:
        checks.append(
            PolicyCheck(
                "allowlist_present",
                "EXECUTION_TEST_EMAIL_ALLOWLIST",
                bool(entries),
                (
                    "Email allowlist is configured."
                    if entries
                    else "Blocked: allowlist empty. Set EXECUTION_TEST_EMAIL_ALLOWLIST to test recipients."
                ),
            )
        )
        checks.append(
            PolicyCheck(
                "recipient_allowlisted",
                "Recipient allowlist",
                bool(allowlist_match),
                (
                    "Eligible for test execution."
                    if allowlist_match
                    else "Blocked: recipient not allowlisted."
                ),
            )
        )
    if action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT:
        checks.extend(
            [
                _flag_check(settings.gmail_write_enabled, "GMAIL_WRITE_ENABLED"),
                _flag_check(settings.gmail_draft_create_enabled, "GMAIL_DRAFT_CREATE_ENABLED"),
            ]
        )
    elif action_type == ExecutionActionType.SEND_GMAIL_REPLY:
        checks.extend(
            [
                _flag_check(settings.gmail_write_enabled, "GMAIL_WRITE_ENABLED"),
                _flag_check(settings.gmail_send_enabled, "GMAIL_SEND_ENABLED"),
                PolicyCheck(
                    "dry_run_disabled",
                    "EXTERNAL_WRITE_DRY_RUN",
                    not settings.external_write_dry_run,
                    (
                        "Dry-run is disabled for explicit test send."
                        if not settings.external_write_dry_run
                        else "Blocked: dry-run still enabled. Gmail send cannot be live-sent until EXTERNAL_WRITE_DRY_RUN=false."
                    ),
                ),
            ]
        )
    elif action_type == ExecutionActionType.CREATE_CALENDAR_EVENT:
        checks.append(_flag_check(settings.google_calendar_write_enabled, "GOOGLE_CALENDAR_WRITE_ENABLED"))
    else:
        checks.append(
            PolicyCheck(
                "unsupported_action",
                "Supported test action",
                False,
                "Blocked: unsupported provider/action for Phase 19 streamlined test execution.",
            )
        )
    return checks


def _flag_check(enabled: bool, name: str) -> PolicyCheck:
    return PolicyCheck(
        name.lower(),
        name,
        enabled,
        f"{name}=true." if enabled else f"Blocked: feature flag disabled. Set {name}=true.",
    )


def _required_flags(action_type: ExecutionActionType, settings: Settings) -> tuple[str, ...]:
    base = ("OPERATIONAL_TEST_MODE", "EXECUTION_PROVIDER")
    if action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT:
        return (*base, "EXECUTION_TEST_EMAIL_ALLOWLIST", "GMAIL_WRITE_ENABLED", "GMAIL_DRAFT_CREATE_ENABLED")
    if action_type == ExecutionActionType.SEND_GMAIL_REPLY:
        return (
            *base,
            "EXECUTION_TEST_EMAIL_ALLOWLIST",
            "GMAIL_WRITE_ENABLED",
            "GMAIL_SEND_ENABLED",
            "EXTERNAL_WRITE_DRY_RUN=false",
        )
    if action_type == ExecutionActionType.CREATE_CALENDAR_EVENT:
        return (*base, "GOOGLE_CALENDAR_WRITE_ENABLED")
    return base


def _target_for_action(
    action_type: ExecutionActionType,
    payload: dict,
    settings: Settings,
) -> str:
    if action_type in EMAIL_ACTIONS:
        return normalize_email_address(payload.get("to")) or str(payload.get("to") or "")
    if action_type == ExecutionActionType.CREATE_CALENDAR_EVENT:
        return settings.google_calendar_id or "primary"
    return "-"


def _next_action(
    action_type: ExecutionActionType,
    allowed: bool,
    settings: Settings,
) -> str:
    if not allowed:
        return "Resolve the blocker before approving or confirming this test execution."
    if action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT and settings.external_write_dry_run:
        return "Approve and confirm to record a dry-run; no external Gmail draft will be created."
    if action_type == ExecutionActionType.CREATE_CALENDAR_EVENT and settings.external_write_dry_run:
        return "Approve and confirm to record a dry-run; no external calendar event will be created."
    return "Approve and confirm explicitly to execute this allowlisted test action."


def _parse_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
