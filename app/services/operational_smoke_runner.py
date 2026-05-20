from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import PROJECT_ROOT, engine
from app.models.entities import (
    ExecutionAuditLog,
    ExecutionRecord,
    ExecutionStatus,
    OperationalSmokeCheck,
    OperationalSmokeCheckStatus,
    OperationalSmokeMode,
    OperationalSmokeRun,
    OperationalSmokeStatus,
    SourceSyncState,
    VoiceGuidance,
    InferenceStatus,
    utcnow,
)
from app.services.backup_service import latest_backup_metadata, sqlite_database_path
from app.services.execution_test_policy import readiness_for_payload
from app.services.live_ai_client import ai_provider_status, test_live_ai_provider
from app.services.provider_status_service import provider_status_rows
from app.services.mailbox_cleanup_service import cleanup_candidate_summary
from app.services.operational_status_service import cleanup_execution_posture
from app.models.entities import ExecutionActionType

ROUTE_SMOKE_PATHS = (
    "/",
    "/assistant-profile",
    "/operational-smoke",
    "/providers",
    "/review-packages",
    "/executions",
    "/bulk-triage",
    "/bulk-triage/mailbox-cleanup",
    "/contacts",
    "/drafts",
    "/voice-calibration",
    "/admin",
    "/healthz",
)

SECRET_MARKERS = (
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "api_key",
    "password",
    "private_key",
    "body_text",
    "message_body",
)


@dataclass(frozen=True)
class SmokeCheckInput:
    check_key: str
    label: str
    category: str
    status: OperationalSmokeCheckStatus
    detail: str
    next_action: str
    sanitized_payload: dict[str, Any] | None = None


def run_operational_smoke(
    db: Session,
    *,
    mode: OperationalSmokeMode = OperationalSmokeMode.API,
    triggered_by: str = "local-user",
    settings: Settings | None = None,
) -> OperationalSmokeRun:
    active = settings or get_settings()
    started_at = utcnow()
    checks = _build_checks(db, active)
    overall_status = _overall_status(checks)
    summary = _summary(checks)
    detail = {
        "routes": list(ROUTE_SMOKE_PATHS),
        "generated_at": started_at.isoformat(),
        "safe_default": True,
        "external_write_performed": False,
    }
    run = OperationalSmokeRun(
        started_at=started_at,
        finished_at=utcnow(),
        triggered_by=_sanitize_text(triggered_by, 255),
        mode=mode,
        overall_status=overall_status,
        app_env=active.env,
        ai_provider=active.ai_provider,
        execution_provider=active.execution_provider,
        external_write_dry_run=active.external_write_dry_run,
        operational_test_mode=active.operational_test_mode,
        allowlist_configured=bool(active.execution_test_email_allowlist.strip()),
        summary_json=_json(summary),
        sanitized_detail_json=_json(detail),
    )
    db.add(run)
    db.flush()
    for item in checks:
        db.add(
            OperationalSmokeCheck(
                smoke_run_id=run.id,
                check_key=item.check_key,
                label=item.label,
                category=item.category,
                status=item.status,
                detail=_sanitize_text(item.detail, 1000),
                next_action=_sanitize_text(item.next_action, 1000),
                external_write_performed=False,
                sanitized_payload_json=_json(item.sanitized_payload or {}),
            )
        )
    db.commit()
    db.refresh(run)
    return run


def latest_smoke_run(db: Session) -> OperationalSmokeRun | None:
    return (
        db.query(OperationalSmokeRun)
        .order_by(OperationalSmokeRun.started_at.desc(), OperationalSmokeRun.id.desc())
        .first()
    )


def recent_smoke_runs(db: Session, limit: int = 10) -> list[OperationalSmokeRun]:
    return (
        db.query(OperationalSmokeRun)
        .order_by(OperationalSmokeRun.started_at.desc(), OperationalSmokeRun.id.desc())
        .limit(limit)
        .all()
    )


def smoke_run_detail(db: Session, run_id: int) -> OperationalSmokeRun | None:
    return db.get(OperationalSmokeRun, run_id)


def smoke_run_to_dict(run: OperationalSmokeRun, *, include_checks: bool = False) -> dict[str, Any]:
    data = {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "triggered_by": run.triggered_by,
        "mode": run.mode.value,
        "overall_status": run.overall_status.value,
        "app_env": run.app_env,
        "ai_provider": run.ai_provider,
        "execution_provider": run.execution_provider,
        "external_write_dry_run": run.external_write_dry_run,
        "operational_test_mode": run.operational_test_mode,
        "allowlist_configured": run.allowlist_configured,
        "summary": _parse_json(run.summary_json),
        "sanitized_detail": _parse_json(run.sanitized_detail_json),
    }
    if include_checks:
        data["checks"] = [smoke_check_to_dict(check) for check in run.checks]
    return data


def smoke_check_to_dict(check: OperationalSmokeCheck) -> dict[str, Any]:
    return {
        "id": check.id,
        "smoke_run_id": check.smoke_run_id,
        "check_key": check.check_key,
        "label": check.label,
        "category": check.category,
        "status": check.status.value,
        "detail": check.detail,
        "next_action": check.next_action,
        "external_write_performed": check.external_write_performed,
        "sanitized_payload": _parse_json(check.sanitized_payload_json),
        "created_at": check.created_at.isoformat() if check.created_at else None,
    }


def _build_checks(db: Session, settings: Settings) -> list[SmokeCheckInput]:
    provider_rows = provider_status_rows(settings)
    row_by_key = {row.key: row for row in provider_rows}
    checks: list[SmokeCheckInput] = []
    checks.extend(_route_checks())
    checks.extend(_provider_checks(provider_rows, settings))
    checks.extend(_execution_checks(db))
    checks.extend(_voice_checks(db))
    checks.extend(_database_checks(settings))
    checks.extend(_backup_checks())
    checks.extend(_sync_checks(db, settings, row_by_key))
    checks.extend(_readiness_checks(settings))
    checks.extend(_mailbox_cleanup_checks(db, settings, row_by_key))
    checks.extend(_microsoft_boundary_checks(row_by_key))
    return checks


def _mailbox_cleanup_checks(db: Session, settings: Settings, row_by_key: dict) -> list[SmokeCheckInput]:
    started = perf_counter()
    summary = cleanup_candidate_summary(db)
    query_elapsed_ms = round((perf_counter() - started) * 1000, 2)

    try:
        table_names = set(inspect(engine).get_table_names())
    except Exception:
        table_names = set()

    required_tables = {
        "mailbox_cleanup_candidates",
        "mailbox_cleanup_action_logs",
    }
    missing_tables = sorted(required_tables - table_names)
    tables_ok = not missing_tables

    posture = cleanup_execution_posture(settings)
    cleanup_provider_state = row_by_key["gmail_label_archive"].state
    posture_status = (
        OperationalSmokeCheckStatus.PASSED
        if posture["posture"] in {"dry_run", "live", "mock"}
        else OperationalSmokeCheckStatus.WARNING
    )

    return [
        SmokeCheckInput(
            check_key="mailbox_cleanup_tables",
            label="Mailbox cleanup table readiness",
            category="mailbox_cleanup",
            status=OperationalSmokeCheckStatus.PASSED if tables_ok else OperationalSmokeCheckStatus.FAILED,
            detail=(
                "Mailbox cleanup tables are present."
                if tables_ok
                else f"Missing mailbox cleanup tables: {', '.join(missing_tables)}"
            ),
            next_action=(
                "Ready."
                if tables_ok
                else "Run python -m alembic upgrade head to apply mailbox cleanup migrations."
            ),
            sanitized_payload={
                "required_tables": sorted(required_tables),
                "missing_tables": missing_tables,
            },
        ),
        SmokeCheckInput(
            check_key="mailbox_cleanup_counts",
            label="Mailbox cleanup candidate count readiness",
            category="mailbox_cleanup",
            status=(
                OperationalSmokeCheckStatus.PASSED
                if query_elapsed_ms <= 250
                else OperationalSmokeCheckStatus.WARNING
            ),
            detail="Mailbox cleanup sender-rollup counts are queryable without scanning messages.",
            next_action=(
                "Ready."
                if query_elapsed_ms <= 250
                else "Investigate mailbox cleanup indexes if count queries become slow."
            ),
            sanitized_payload={
                "query_elapsed_ms": query_elapsed_ms,
                "total_cleanup_candidates": summary.total_cleanup_candidates,
                "high_confidence_candidates": summary.high_confidence_candidates,
                "protected_candidates": summary.protected_candidates,
                "gmail_label_capable_candidates": summary.gmail_label_capable_candidates,
                "gmail_archive_capable_candidates": summary.gmail_archive_capable_candidates,
                "delete_candidates": summary.delete_candidates,
                "blocked_candidates": summary.blocked_candidates,
            },
        ),
        SmokeCheckInput(
            check_key="mailbox_cleanup_execution_posture",
            label="Mailbox cleanup execution posture",
            category="mailbox_cleanup",
            status=posture_status,
            detail=(
                f"Cleanup posture: {posture['label']}. Gmail label/archive provider state: {cleanup_provider_state}."
            ),
            next_action=str(posture["detail"]),
            sanitized_payload={
                "execution_posture": posture,
                "gmail_label_archive_provider_state": cleanup_provider_state,
            },
        ),
    ]


def _route_checks() -> list[SmokeCheckInput]:
    return [
        SmokeCheckInput(
            check_key=f"route_{path.strip('/').replace('/', '_') or 'dashboard'}",
            label=f"Route {path}",
            category="routes",
            status=OperationalSmokeCheckStatus.PASSED,
            detail="Route is part of the daily local smoke set.",
            next_action=f"Open {path} if browser-level validation is needed.",
            sanitized_payload={"path": path, "method": "GET"},
        )
        for path in ROUTE_SMOKE_PATHS
    ]


def _provider_checks(provider_rows, settings: Settings) -> list[SmokeCheckInput]:
    checks: list[SmokeCheckInput] = []
    ai_status = ai_provider_status(settings)
    ai_payload: dict[str, Any] = {
        "provider": ai_status.requested_provider,
        "effective_provider": ai_status.effective_provider,
        "live_enabled": ai_status.live_enabled,
        "endpoint_host": ai_status.endpoint_host,
    }
    ai_check_status = OperationalSmokeCheckStatus.PASSED
    ai_detail = ai_status.detail
    ai_next = "Mock AI is acceptable for local development."
    if ai_status.live_enabled:
        diagnostic = test_live_ai_provider(settings)
        ai_payload.update(diagnostic)
        ai_check_status = (
            OperationalSmokeCheckStatus.PASSED
            if diagnostic.get("success")
            else OperationalSmokeCheckStatus.FAILED
        )
        ai_detail = "Live AI diagnostic executed with sanitized result."
        ai_next = "Fix provider configuration before relying on live analysis." if not diagnostic.get("success") else "Ready."
    checks.append(
        SmokeCheckInput(
            check_key="ai_provider",
            label="Azure/OpenAI readiness",
            category="providers",
            status=ai_check_status,
            detail=ai_detail,
            next_action=ai_next,
            sanitized_payload=ai_payload,
        )
    )
    for row in provider_rows:
        if row.key == "ai_provider":
            continue
        status = _status_from_provider_state(row.state)
        checks.append(
            SmokeCheckInput(
                check_key=f"provider_{row.key}",
                label=row.label,
                category="providers",
                status=status,
                detail=row.detail,
                next_action=row.next_action,
                sanitized_payload={
                    "key": row.key,
                    "state": row.state,
                    "mode": row.mode,
                    "classification": row.classification,
                    "dry_run": row.dry_run,
                },
            )
        )
    return checks


def _execution_checks(db: Session) -> list[SmokeCheckInput]:
    counts = {
        "pending_review_count": _execution_count(db, ExecutionStatus.PENDING_REVIEW),
        "approved_count": _execution_count(db, ExecutionStatus.APPROVED),
        "executed_count": _execution_count(db, ExecutionStatus.EXECUTED),
        "failed_count": _execution_count(db, ExecutionStatus.FAILED),
        "audit_count": db.query(func.count(ExecutionAuditLog.id)).scalar() or 0,
    }
    status = (
        OperationalSmokeCheckStatus.WARNING
        if counts["failed_count"]
        else OperationalSmokeCheckStatus.PASSED
    )
    return [
        SmokeCheckInput(
            check_key="execution_audit_readiness",
            label="Execution audit readiness",
            category="workflow",
            status=status,
            detail="Execution lifecycle counts are available from the local database.",
            next_action="Open /executions and review failed records." if counts["failed_count"] else "Ready.",
            sanitized_payload=counts,
        )
    ]


def _voice_checks(db: Session) -> list[SmokeCheckInput]:
    approved_guidance = (
        db.query(func.count(VoiceGuidance.id))
        .filter(VoiceGuidance.status == InferenceStatus.APPROVED, VoiceGuidance.is_active.is_(True))
        .scalar()
        or 0
    )
    pending_guidance = (
        db.query(func.count(VoiceGuidance.id))
        .filter(VoiceGuidance.status == InferenceStatus.PENDING)
        .scalar()
        or 0
    )
    preferred = (
        db.query(VoiceGuidance)
        .filter(
            VoiceGuidance.status == InferenceStatus.APPROVED,
            VoiceGuidance.is_active.is_(True),
            VoiceGuidance.relationship_type == "global_operator",
            VoiceGuidance.tone_notes.ilike("%preferred sign-off:%"),
        )
        .order_by(VoiceGuidance.updated_at.desc())
        .first()
    )
    return [
        SmokeCheckInput(
            check_key="voice_memory_readiness",
            label="Voice memory readiness",
            category="workflow",
            status=OperationalSmokeCheckStatus.PASSED if approved_guidance else OperationalSmokeCheckStatus.WARNING,
            detail="Voice guidance counts are available without exposing private sent-mail text.",
            next_action=(
                "Open /assistant-profile and approve or edit guidance."
                if pending_guidance or not approved_guidance
                else "Ready."
            ),
            sanitized_payload={
                "preferred_signoff_approved": bool(preferred),
                "active_approved_guidance_count": approved_guidance,
                "pending_guidance_count": pending_guidance,
            },
        )
    ]


def _database_checks(settings: Settings) -> list[SmokeCheckInput]:
    db_path = sqlite_database_path(settings)
    migration = _migration_status()
    reachable = True
    try:
        inspect(engine).get_table_names()
    except Exception:
        reachable = False
    status = OperationalSmokeCheckStatus.PASSED if reachable and migration["current_is_head"] else OperationalSmokeCheckStatus.WARNING
    return [
        SmokeCheckInput(
            check_key="database_health",
            label="Database health",
            category="database",
            status=status,
            detail="Local database and Alembic status checked without shelling out.",
            next_action="Run python -m alembic upgrade head." if not migration["current_is_head"] else "Ready.",
            sanitized_payload={
                "database_kind": "sqlite" if db_path else "configured database",
                "sqlite_path": str(db_path) if db_path else None,
                "db_reachable": reachable,
                **migration,
            },
        )
    ]


def _backup_checks() -> list[SmokeCheckInput]:
    latest = latest_backup_metadata()
    status = OperationalSmokeCheckStatus.PASSED if latest else OperationalSmokeCheckStatus.WARNING
    return [
        SmokeCheckInput(
            check_key="backup_readiness",
            label="Backup readiness",
            category="backup",
            status=status,
            detail="Latest local sanitized backup metadata is available." if latest else "No local backup archive found.",
            next_action="Create a local backup from /admin or scripts/backup-commsdesk.ps1." if not latest else "Ready.",
            sanitized_payload=latest.as_dict() if latest else {"latest_backup": None},
        )
    ]


def _sync_checks(db: Session, settings: Settings, row_by_key: dict) -> list[SmokeCheckInput]:
    gmail = _sync_payload(db, "gmail", settings.gmail_account)
    outlook = _sync_payload(db, "outlook", "microsoft-graph")
    return [
        SmokeCheckInput(
            check_key="gmail_read_sync_readiness",
            label="Gmail read sync readiness",
            category="sync",
            status=OperationalSmokeCheckStatus.PASSED if row_by_key["gmail_read"].state == "live" else OperationalSmokeCheckStatus.FAILED,
            detail="Gmail read sync is checked from config and local sync state.",
            next_action=row_by_key["gmail_read"].next_action,
            sanitized_payload=gmail,
        ),
        SmokeCheckInput(
            check_key="outlook_mail_read_readiness",
            label="Outlook mail read readiness",
            category="sync",
            status=_status_from_provider_state(row_by_key["microsoft_graph_outlook_mail"].state),
            detail="Outlook mail read is checked from Graph provider state and local sync state.",
            next_action=row_by_key["microsoft_graph_outlook_mail"].next_action,
            sanitized_payload=outlook,
        ),
    ]


def _readiness_checks(settings: Settings) -> list[SmokeCheckInput]:
    draft = readiness_for_payload(
        ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
        {"to": _sample_allowlisted_target(settings.execution_test_email_allowlist)},
        settings,
    )
    gmail_send = readiness_for_payload(
        ExecutionActionType.SEND_GMAIL_REPLY,
        {"to": _sample_allowlisted_target(settings.execution_test_email_allowlist)},
        settings,
    )
    calendar = readiness_for_payload(ExecutionActionType.CREATE_CALENDAR_EVENT, {}, settings)
    token_checks = _token_readiness(settings)
    return [
        _readiness_check("gmail_draft_readiness", "Gmail write dry-run readiness", draft),
        _readiness_check("gmail_send_readiness", "Gmail write live readiness", gmail_send),
        _readiness_check("google_calendar_readiness", "Google Calendar write readiness", calendar),
        SmokeCheckInput(
            check_key="oauth_token_guidance",
            label="OAuth/token readiness guidance",
            category="providers",
            status=OperationalSmokeCheckStatus.PASSED if all(item["exists"] for item in token_checks if item["required_now"]) else OperationalSmokeCheckStatus.WARNING,
            detail="Token files are checked by existence only; token contents are not stored.",
            next_action="Run scripts/reauth-commsdesk.ps1 with the relevant switch when a token is missing or scopes changed.",
            sanitized_payload={"tokens": token_checks},
        ),
    ]


def _readiness_check(key: str, label: str, readiness) -> SmokeCheckInput:
    return SmokeCheckInput(
        check_key=key,
        label=label,
        category="execution",
        status=OperationalSmokeCheckStatus.PASSED if readiness.allowed else OperationalSmokeCheckStatus.WARNING,
        detail=readiness.next_action if readiness.allowed else readiness.blocked_reason or "Blocked.",
        next_action=readiness.next_action,
        sanitized_payload={
            "allowed": readiness.allowed,
            "dry_run": readiness.dry_run,
            "target_kind": readiness.target_kind,
            "required_flags": list(readiness.required_flags),
        },
    )


def _microsoft_boundary_checks(row_by_key: dict) -> list[SmokeCheckInput]:
    return [
        SmokeCheckInput(
            check_key=f"boundary_{key}",
            label=row_by_key[key].label,
            category="boundaries",
            status=OperationalSmokeCheckStatus.SKIPPED,
            detail=row_by_key[key].detail,
            next_action=row_by_key[key].next_action,
            sanitized_payload={"state": row_by_key[key].state, "implemented": False},
        )
        for key in (
            "outlook_draft_create",
            "outlook_send",
            "outlook_mail_modify",
            "outlook_calendar_write",
            "microsoft_graph_teams",
        )
        if key in row_by_key
    ]


def _token_readiness(settings: Settings) -> list[dict[str, object]]:
    return [
        {
            "provider": "gmail",
            "file": Path(settings.gmail_token_file).name,
            "exists": Path(settings.gmail_token_file).expanduser().exists(),
            "required_now": True,
            "reauth_command": r".\scripts\reauth-commsdesk.ps1 -Gmail",
            "required_scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
        },
        {
            "provider": "google_calendar",
            "file": Path(settings.google_calendar_token_file).name,
            "exists": Path(settings.google_calendar_token_file).expanduser().exists(),
            "required_now": settings.google_calendar_read_enabled or settings.google_calendar_write_enabled,
            "reauth_command": r".\scripts\reauth-commsdesk.ps1 -GoogleCalendar",
            "required_scopes": [
                "https://www.googleapis.com/auth/calendar.freebusy",
                "https://www.googleapis.com/auth/calendar.events",
            ],
        },
        {
            "provider": "microsoft_graph",
            "file": Path(settings.microsoft_graph_token_file).name,
            "exists": Path(settings.microsoft_graph_token_file).expanduser().exists(),
            "required_now": settings.microsoft_graph_enabled and settings.microsoft_graph_auth_mode == "delegated",
            "reauth_command": r".\scripts\reauth-commsdesk.ps1 -MicrosoftGraph",
            "required_scopes": ["User.Read", "Mail.Read", "offline_access"],
        },
    ]


def _execution_count(db: Session, status: ExecutionStatus) -> int:
    return db.query(func.count(ExecutionRecord.id)).filter(ExecutionRecord.status == status).scalar() or 0


def _sync_payload(db: Session, source_type: str, account_identifier: str) -> dict[str, Any]:
    state = (
        db.query(SourceSyncState)
        .filter_by(source_type=source_type, account_identifier=account_identifier)
        .first()
    )
    if not state:
        return {"last_successful_sync_at": None, "last_error": None}
    return {
        "last_successful_sync_at": state.last_successful_sync_at.isoformat() if state.last_successful_sync_at else None,
        "last_started_at": state.last_started_at.isoformat() if state.last_started_at else None,
        "last_fetched_count": state.last_fetched_count,
        "last_inserted_count": state.last_inserted_count,
        "last_error": _sanitize_text(state.last_error, 300),
    }


def _migration_status() -> dict[str, Any]:
    try:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current = context.get_current_revision()
        return {"alembic_current": current, "alembic_head": head, "current_is_head": current == head}
    except Exception as exc:
        return {"alembic_current": None, "alembic_head": None, "current_is_head": False, "migration_error": _sanitize_text(str(exc), 300)}


def _status_from_provider_state(state: str) -> OperationalSmokeCheckStatus:
    if state in {"live", "mock"}:
        return OperationalSmokeCheckStatus.PASSED
    if state in {"disabled", "dry_run"}:
        return OperationalSmokeCheckStatus.WARNING
    if state in {"missing_configuration", "failed"}:
        return OperationalSmokeCheckStatus.FAILED
    return OperationalSmokeCheckStatus.WARNING


def _overall_status(checks: list[SmokeCheckInput]) -> OperationalSmokeStatus:
    if any(check.status == OperationalSmokeCheckStatus.FAILED for check in checks):
        return OperationalSmokeStatus.FAILED
    if any(check.status == OperationalSmokeCheckStatus.WARNING for check in checks):
        return OperationalSmokeStatus.WARNING
    return OperationalSmokeStatus.PASSED


def _summary(checks: list[SmokeCheckInput]) -> dict[str, Any]:
    return {
        "passed": sum(1 for check in checks if check.status == OperationalSmokeCheckStatus.PASSED),
        "warning": sum(1 for check in checks if check.status == OperationalSmokeCheckStatus.WARNING),
        "failed": sum(1 for check in checks if check.status == OperationalSmokeCheckStatus.FAILED),
        "skipped": sum(1 for check in checks if check.status == OperationalSmokeCheckStatus.SKIPPED),
        "external_write_performed": False,
    }


def _sample_allowlisted_target(raw_allowlist: str | None) -> str:
    first = next((item.strip() for item in (raw_allowlist or "").split(",") if item.strip()), "")
    if first.startswith("@"):
        return f"test{first}"
    return first


def _json(value: Any) -> str:
    return json.dumps(_sanitize_payload(value), sort_keys=True)


def _parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in SECRET_MARKERS):
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list | tuple):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _sanitize_text(value, 1000)
    return value


def _sanitize_text(value: str | None, max_length: int) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    for marker in SECRET_MARKERS:
        text = re.sub(marker, "[redacted]", text, flags=re.IGNORECASE)
    return text[:max_length]
