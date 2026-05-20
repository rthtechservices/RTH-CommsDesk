from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.live_ai_client import ai_provider_status

GMAIL_REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
)
GOOGLE_CALENDAR_REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.events",
)
MICROSOFT_GRAPH_REQUIRED_SCOPES = (
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
    "offline_access",
)


@dataclass(frozen=True)
class ProviderStatusRow:
    key: str
    label: str
    classification: str
    state: str
    mode: str
    detail: str
    next_action: str
    dry_run: bool = False


def provider_status_rows(settings: Settings | None = None) -> list[ProviderStatusRow]:
    active = settings or get_settings()
    ai_status = ai_provider_status(active)
    gmail_read_configured = _path_exists(active.gmail_client_secrets_file)
    gmail_token_exists = _path_exists(active.gmail_token_file)
    gmail_write_configured = gmail_read_configured
    graph_configured = _graph_configured(active)
    calendar_configured = _path_exists(active.gmail_client_secrets_file)
    calendar_token_exists = _path_exists(active.google_calendar_token_file)
    webhook_configured = bool(active.notification_webhook_secret)
    dry_run = active.external_write_dry_run
    graph_auth_mode = _graph_auth_mode(active)

    rows = [
        ProviderStatusRow(
            key="gmail_read",
            label="Gmail read",
            classification="live-ready",
            state="live" if gmail_read_configured else "missing_configuration",
            mode="read-only",
            detail=(
                "Gmail read and full-thread fetch use OAuth and the readonly scope."
                if gmail_read_configured
                else "Gmail OAuth client secrets are missing."
            ),
            next_action=(
                "Ready for read-only sync."
                if gmail_read_configured and gmail_token_exists
                else r"Run .\scripts\reauth-commsdesk.ps1 -Gmail, then POST /api/sync/gmail."
                if gmail_read_configured
                else "Set GMAIL_CLIENT_SECRETS_FILE to a local OAuth client JSON file."
            ),
        ),
        _gmail_write_status(
            active,
            key="gmail_draft_create",
            label="Gmail external draft creation",
            enabled=active.gmail_write_enabled and active.gmail_draft_create_enabled,
            configured=gmail_write_configured,
            dry_run=dry_run,
            feature_flag="GMAIL_WRITE_ENABLED and GMAIL_DRAFT_CREATE_ENABLED",
        ),
        _gmail_write_status(
            active,
            key="gmail_send_reply",
            label="Gmail send reply",
            enabled=active.gmail_write_enabled and active.gmail_send_enabled,
            configured=gmail_write_configured,
            dry_run=dry_run,
            feature_flag="GMAIL_WRITE_ENABLED and GMAIL_SEND_ENABLED",
        ),
        _gmail_write_status(
            active,
            key="gmail_label_archive",
            label="Gmail label/archive",
            enabled=active.gmail_write_enabled and active.gmail_label_archive_enabled,
            configured=gmail_write_configured,
            dry_run=dry_run,
            feature_flag="GMAIL_WRITE_ENABLED and GMAIL_LABEL_ARCHIVE_ENABLED",
        ),
        ProviderStatusRow(
            key="google_calendar_read",
            label="Google Calendar read",
            classification="partially wired",
            state=_enabled_state(active.google_calendar_read_enabled, calendar_configured, dry_run=False),
            mode="live read" if active.google_calendar_read_enabled else "disabled",
            detail="Google Calendar free/busy read is available when the read flag and OAuth config are present.",
            next_action=(
                "Set GOOGLE_CALENDAR_READ_ENABLED=true and authorize the calendar token."
                if not active.google_calendar_read_enabled
                else _calendar_action(calendar_configured, calendar_token_exists)
            ),
        ),
        ProviderStatusRow(
            key="google_calendar_write",
            label="Google Calendar write",
            classification="partially wired",
            state=_enabled_state(active.google_calendar_write_enabled, calendar_configured, dry_run=dry_run),
            mode="dry-run" if active.google_calendar_write_enabled and dry_run else "disabled",
            detail="Calendar create/reminder execution is guarded by feature flag, approval flow, and dry-run.",
            next_action=(
                "Set GOOGLE_CALENDAR_WRITE_ENABLED=true only after OAuth scopes are approved."
                if not active.google_calendar_write_enabled
                else _calendar_action(calendar_configured, calendar_token_exists)
            ),
            dry_run=active.google_calendar_write_enabled and dry_run,
        ),
        ProviderStatusRow(
            key="microsoft_graph_delegated_auth",
            label="Microsoft Graph delegated auth",
            classification="live-ready",
            state=_graph_delegated_auth_state(active),
            mode=graph_auth_mode,
            detail="Delegated OAuth stores a local token file and requests User.Read, Mail.Read, and offline_access by default.",
            next_action=_graph_delegated_next_action(active),
        ),
        ProviderStatusRow(
            key="operational_test_mode",
            label="Operational test mode",
            classification="test-safety-gate",
            state="live" if active.operational_test_mode else "disabled",
            mode="test mode" if active.operational_test_mode else "disabled",
            detail="Required before Phase 19 streamlined Gmail or Calendar test execution is available.",
            next_action=(
                "Ready; allowlist and per-action flags still apply."
                if active.operational_test_mode
                else "Set OPERATIONAL_TEST_MODE=true only for controlled local test execution."
            ),
        ),
        ProviderStatusRow(
            key="execution_test_email_allowlist",
            label="Execution test email allowlist",
            classification="test-safety-gate",
            state="live" if active.execution_test_email_allowlist.strip() else "missing_configuration",
            mode="exact-email/domain allowlist",
            detail=(
                "At least one test recipient/domain is configured."
                if active.execution_test_email_allowlist.strip()
                else "No streamlined test email execution recipients are configured."
            ),
            next_action=(
                "Ready; non-allowlisted recipients remain blocked."
                if active.execution_test_email_allowlist.strip()
                else "Set EXECUTION_TEST_EMAIL_ALLOWLIST to comma-separated test addresses."
            ),
        ),
        ProviderStatusRow(
            key="microsoft_graph_outlook_mail",
            label="Outlook mail read",
            classification="live-ready" if graph_configured else "adapter-shape-only",
            state=_enabled_state(
                active.microsoft_graph_enabled and active.microsoft_graph_outlook_mail_enabled,
                graph_configured,
                dry_run=False,
            ),
            mode=f"{graph_auth_mode} Graph" if active.microsoft_graph_outlook_mail_enabled else "disabled",
            detail="Outlook mail read can use Microsoft Graph delegated OAuth or the existing app-only client seam with Mail.Read.",
            next_action=_graph_next_action(active, "MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED"),
        ),
        _microsoft_write_status(
            active,
            key="outlook_draft_create",
            label="Outlook draft creation",
            enabled=active.outlook_draft_create_enabled,
            graph_configured=graph_configured,
            dry_run=dry_run,
            feature_flag="OUTLOOK_DRAFT_CREATE_ENABLED",
            required_scope="Mail.ReadWrite",
        ),
        _microsoft_write_status(
            active,
            key="outlook_send",
            label="Outlook send / reply",
            enabled=active.outlook_send_enabled,
            graph_configured=graph_configured,
            dry_run=dry_run,
            feature_flag="OUTLOOK_SEND_ENABLED",
            required_scope="Mail.Send",
        ),
        _microsoft_write_status(
            active,
            key="outlook_mail_modify",
            label="Outlook mail modify (category/archive)",
            enabled=active.outlook_mail_modify_enabled,
            graph_configured=graph_configured,
            dry_run=dry_run,
            feature_flag="OUTLOOK_MAIL_MODIFY_ENABLED",
            required_scope="Mail.ReadWrite",
        ),
        _microsoft_write_status(
            active,
            key="outlook_calendar_write",
            label="Outlook calendar event creation",
            enabled=active.outlook_calendar_write_enabled,
            graph_configured=graph_configured,
            dry_run=dry_run,
            feature_flag="OUTLOOK_CALENDAR_WRITE_ENABLED",
            required_scope="Calendars.ReadWrite",
        ),
        ProviderStatusRow(
            key="microsoft_graph_teams",
            label="Microsoft Graph Teams",
            classification="not implemented",
            state="disabled",
            mode="disabled",
            detail="Teams remains disabled and the adapter seam stays fail-closed.",
            next_action="Confirm tenant permissions and a future read scope before implementing Teams.",
        ),
        ProviderStatusRow(
            key="notification_webhook",
            label="Notification webhook",
            classification="live-ready",
            state="live" if webhook_configured else "disabled",
            mode="inbound webhook",
            detail="Webhook ingestion stores low-confidence summaries only.",
            next_action=(
                "Ready; webhook secret is configured."
                if webhook_configured
                else "Set NOTIFICATION_WEBHOOK_SECRET before exposing the webhook."
            ),
        ),
        ProviderStatusRow(
            key="ai_provider",
            label="Azure OpenAI / OpenAI-compatible AI provider",
            classification="live-ready" if ai_status.live_enabled else "mock-only",
            state="live" if ai_status.live_enabled else "mock",
            mode=ai_status.effective_provider,
            detail=ai_status.detail,
            next_action=(
                "Ready; use POST /api/ai/test for a sanitized live check."
                if ai_status.live_enabled
                else "Set AI_PROVIDER and required provider credentials to enable live AI."
            ),
        ),
    ]
    return rows


def provider_status_matrix(settings: Settings | None = None) -> dict[str, dict[str, str | bool]]:
    return {
        row.key: {
            "label": row.label,
            "classification": row.classification,
            "state": row.state,
            "mode": row.mode,
            "detail": row.detail,
            "next_action": row.next_action,
            "dry_run": row.dry_run,
        }
        for row in provider_status_rows(settings)
    }


def _microsoft_write_status(
    settings: Settings,
    *,
    key: str,
    label: str,
    enabled: bool,
    graph_configured: bool,
    dry_run: bool,
    feature_flag: str,
    required_scope: str,
) -> ProviderStatusRow:
    if not settings.microsoft_graph_enabled:
        state = "misconfigured"
        mode = "blocked"
        detail = f"{label} requires MICROSOFT_GRAPH_ENABLED=true."
        next_action = "Set MICROSOFT_GRAPH_ENABLED=true and configure tenant/client IDs."
    elif not graph_configured:
        state = "misconfigured"
        mode = "blocked"
        detail = f"{label} requires MICROSOFT_TENANT_ID and MICROSOFT_CLIENT_ID."
        next_action = "Configure Microsoft Graph credentials before enabling write surfaces."
    elif not enabled:
        state = "disabled"
        mode = "disabled"
        detail = (
            f"{label} is disabled by {feature_flag}=false. "
            f"Required Graph scope: {required_scope}."
        )
        next_action = (
            f"Set {feature_flag}=true after confirming Graph delegated auth has {required_scope}. "
            f"If scopes changed: Remove-Item '.\\microsoft_graph_token.json' -Force -ErrorAction SilentlyContinue, "
            f"then run POST /api/graph/test."
        )
    elif dry_run:
        state = "dry_run"
        mode = "dry-run write"
        detail = (
            f"{label} is enabled but EXTERNAL_WRITE_DRY_RUN=true so no live Graph write will occur. "
            f"Required scope: {required_scope}."
        )
        next_action = (
            "Set EXTERNAL_WRITE_DRY_RUN=false only after verifying dry-run results. "
            "All writes still require approval, confirmation, and audit."
        )
    else:
        state = "available"
        mode = "live Graph write"
        detail = (
            f"{label} is enabled. External writes require approval, confirmation, and audit. "
            f"Required scope: {required_scope}."
        )
        next_action = "Prepare an execution record, approve, confirm, and audit the result."
    return ProviderStatusRow(
        key=key,
        label=label,
        classification="partially wired" if graph_configured else "adapter-shape-only",
        state=state,
        mode=mode,
        detail=detail,
        next_action=next_action,
        dry_run=enabled and dry_run,
    )


def _gmail_write_status(
    settings: Settings,
    *,
    key: str,
    label: str,
    enabled: bool,
    configured: bool,
    dry_run: bool,
    feature_flag: str,
) -> ProviderStatusRow:
    state = _enabled_state(enabled, configured, dry_run=dry_run)
    missing_scopes = _missing_gmail_write_scopes(settings)
    if enabled and missing_scopes:
        state = "missing_configuration"
    return ProviderStatusRow(
        key=key,
        label=label,
        classification="partially wired",
        state=state,
        mode="dry-run" if enabled and dry_run else ("live write" if enabled else "disabled"),
        detail="Gmail write execution is guarded by prepare, approve, confirm, feature flags, and dry-run.",
        next_action=(
            f"Set {feature_flag}=true only after OAuth write scopes are intentionally authorized."
            if not enabled
            else (
                r"Run .\scripts\reauth-commsdesk.ps1 -Gmail after enabling Gmail write flags; missing scopes: "
                + ", ".join(missing_scopes)
                if missing_scopes
                else _config_action(configured)
            )
        ),
        dry_run=enabled and dry_run,
    )


def _enabled_state(enabled: bool, configured: bool, *, dry_run: bool) -> str:
    if not enabled:
        return "disabled"
    if not configured:
        return "missing_configuration"
    if dry_run:
        return "dry_run"
    return "live"


def _config_action(configured: bool) -> str:
    if configured:
        return "Ready; external writes still require approval and final confirmation."
    return "Add the required OAuth client/token configuration before enabling live mode."


def _calendar_action(configured: bool, token_exists: bool) -> str:
    if not configured:
        return "Add the Google OAuth client JSON before enabling Calendar."
    if not token_exists:
        return r"Run .\scripts\reauth-commsdesk.ps1 -GoogleCalendar, then retry Calendar readiness."
    return "Ready; Calendar writes still require approval, final confirmation, and dry-run review."


def _graph_next_action(settings: Settings, flag_name: str) -> str:
    if not settings.microsoft_graph_enabled:
        return "Set MICROSOFT_GRAPH_ENABLED=true only after tenant app registration is complete."
    if not _graph_configured(settings):
        if _graph_auth_mode(settings) == "delegated":
            return "Set MICROSOFT_TENANT_ID and MICROSOFT_CLIENT_ID, then run POST /api/graph/test."
        return "Set MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, and MICROSOFT_CLIENT_SECRET."
    return f"Set {flag_name}=true after confirming tenant permissions."


def _graph_configured(settings: Settings) -> bool:
    if _graph_auth_mode(settings) == "delegated":
        return bool(settings.microsoft_tenant_id and settings.microsoft_client_id)
    return bool(
        settings.microsoft_tenant_id
        and settings.microsoft_client_id
        and settings.microsoft_client_secret
    )


def _graph_auth_mode(settings: Settings) -> str:
    raw = (settings.microsoft_graph_auth_mode or "app_only").strip().lower()
    return raw if raw in {"delegated", "app_only"} else "invalid"


def _graph_delegated_auth_state(settings: Settings) -> str:
    if _graph_auth_mode(settings) != "delegated":
        return "disabled"
    if not settings.microsoft_graph_enabled:
        return "disabled"
    if not settings.microsoft_tenant_id or not settings.microsoft_client_id:
        return "missing_configuration"
    return "live" if _path_exists(settings.microsoft_graph_token_file) else "missing_configuration"


def _graph_delegated_next_action(settings: Settings) -> str:
    if _graph_auth_mode(settings) != "delegated":
        return "Set MICROSOFT_GRAPH_AUTH_MODE=delegated to use local delegated OAuth."
    if not settings.microsoft_graph_enabled:
        return "Set MICROSOFT_GRAPH_ENABLED=true for local delegated Graph testing."
    if not settings.microsoft_tenant_id or not settings.microsoft_client_id:
        return "Set MICROSOFT_TENANT_ID and MICROSOFT_CLIENT_ID."
    if not _path_exists(settings.microsoft_graph_token_file):
        return r"Run .\scripts\reauth-commsdesk.ps1 -MicrosoftGraph, then POST /api/graph/test."
    return "Token file exists; run POST /api/graph/test to verify the delegated session."


def _path_exists(value: str | None) -> bool:
    if not value:
        return False
    return Path(value).expanduser().exists()


def _missing_gmail_write_scopes(settings: Settings) -> tuple[str, ...]:
    if not _path_exists(settings.gmail_token_file):
        return GMAIL_REQUIRED_SCOPES
    path = Path(settings.gmail_token_file).expanduser()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GMAIL_REQUIRED_SCOPES
    raw = data.get("scopes") or data.get("scope") or ""
    if isinstance(raw, str):
        scopes = set(raw.split())
    elif isinstance(raw, list):
        scopes = {str(item) for item in raw}
    else:
        scopes = set()
    if not scopes:
        return ()
    return tuple(scope for scope in GMAIL_REQUIRED_SCOPES if scope not in scopes)
