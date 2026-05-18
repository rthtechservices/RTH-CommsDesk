from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.live_ai_client import ai_provider_status


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
    gmail_write_configured = gmail_read_configured
    graph_configured = _graph_configured(active)
    calendar_configured = _path_exists(active.gmail_client_secrets_file)
    webhook_configured = bool(active.notification_webhook_secret)
    dry_run = active.external_write_dry_run

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
                else _config_action(calendar_configured)
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
                else _config_action(calendar_configured)
            ),
            dry_run=active.google_calendar_write_enabled and dry_run,
        ),
        ProviderStatusRow(
            key="microsoft_graph_outlook_mail",
            label="Microsoft Graph Outlook mail",
            classification="partially wired" if graph_configured else "adapter-shape-only",
            state=_enabled_state(
                active.microsoft_graph_enabled and active.microsoft_graph_outlook_mail_enabled,
                graph_configured,
                dry_run=False,
            ),
            mode="app-only Graph" if active.microsoft_graph_outlook_mail_enabled else "disabled",
            detail="Outlook mail can use Microsoft Graph app credentials where tenant permissions allow Mail.Read.",
            next_action=_graph_next_action(active, "MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED"),
        ),
        ProviderStatusRow(
            key="microsoft_graph_teams",
            label="Microsoft Graph Teams",
            classification="adapter-shape-only",
            state="disabled" if not active.microsoft_graph_teams_enabled else "missing_configuration",
            mode="adapter",
            detail="Teams ingestion keeps the normalized adapter seam; live Graph setup is tenant-permission dependent.",
            next_action="Configure tenant app permissions for Teams export/chat reads before enabling.",
        ),
        ProviderStatusRow(
            key="outlook_calendar_read",
            label="Outlook Calendar read",
            classification="adapter-shape-only",
            state=_enabled_state(
                active.microsoft_graph_enabled
                and active.microsoft_graph_outlook_calendar_read_enabled
                and active.outlook_calendar_read_enabled,
                graph_configured,
                dry_run=False,
            ),
            mode="adapter",
            detail="Outlook calendar read remains fail-closed until tenant calendar permissions are confirmed.",
            next_action=_graph_next_action(active, "MICROSOFT_GRAPH_OUTLOOK_CALENDAR_READ_ENABLED"),
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
            else _config_action(configured)
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


def _graph_next_action(settings: Settings, flag_name: str) -> str:
    if not settings.microsoft_graph_enabled:
        return "Set MICROSOFT_GRAPH_ENABLED=true only after tenant app registration is complete."
    if not _graph_configured(settings):
        return "Set MICROSOFT_TENANT_ID, MICROSOFT_CLIENT_ID, and MICROSOFT_CLIENT_SECRET."
    return f"Set {flag_name}=true after confirming tenant permissions."


def _graph_configured(settings: Settings) -> bool:
    return bool(
        settings.microsoft_tenant_id
        and settings.microsoft_client_id
        and settings.microsoft_client_secret
    )


def _path_exists(value: str | None) -> bool:
    if not value:
        return False
    return Path(value).expanduser().exists()
