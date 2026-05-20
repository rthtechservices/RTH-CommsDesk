from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import (
    CalendarActionProposal,
    DraftReply,
    ExecutionActionType,
    ExecutionAuditLog,
    ExecutionRecord,
    ExecutionStatus,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
    utcnow,
)
from app.services.external_provider_clients import GmailWriteClient, GoogleCalendarClient
from app.services.microsoft_graph_client import MicrosoftGraphMailService
from app.services.draft_service import sanitize_send_ready_email_text, send_ready_email_for_draft
from app.services.execution_test_policy import ensure_test_execution_allowed


class ExecutionProvider(Protocol):
    name: str

    def create_external_gmail_draft(self, payload: dict) -> dict:
        """Create an external Gmail draft."""

    def send_gmail_reply(self, payload: dict) -> dict:
        """Send a Gmail reply."""

    def create_calendar_event(self, payload: dict) -> dict:
        """Create a calendar event or reminder."""

    def apply_gmail_label_archive(self, payload: dict) -> dict:
        """Apply label/archive operation."""

    def apply_gmail_label_archive_batch(self, payload: dict) -> dict:
        """Apply label/archive to a batch of sender messages (cleanup workflow)."""

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        """Delete or unsubscribe operation with explicit confirmation."""

    def create_outlook_draft(self, payload: dict) -> dict:
        """Create an Outlook draft via Microsoft Graph."""

    def send_outlook_reply(self, payload: dict) -> dict:
        """Send an Outlook reply/message via Microsoft Graph."""

    def apply_outlook_mail_modify(self, payload: dict) -> dict:
        """Apply category/read/archive modification to an Outlook message."""

    def create_outlook_calendar_event(self, payload: dict) -> dict:
        """Create an Outlook calendar event via Microsoft Graph."""


class MockExecutionProvider:
    name = "mock"

    def create_external_gmail_draft(self, payload: dict) -> dict:
        return {"draft_id": _mock_id("draft", payload), "status": "created"}

    def send_gmail_reply(self, payload: dict) -> dict:
        return {"message_id": _mock_id("reply", payload), "status": "sent"}

    def create_calendar_event(self, payload: dict) -> dict:
        return {"event_id": _mock_id("event", payload), "status": "created"}

    def apply_gmail_label_archive(self, payload: dict) -> dict:
        return {"operation_id": _mock_id("label", payload), "status": "applied"}

    def apply_gmail_label_archive_batch(self, payload: dict) -> dict:
        message_ids: list[str] = list(dict.fromkeys(
            mid for mid in (payload.get("source_message_ids") or []) if mid
        ))
        count = len(message_ids)
        return {
            "operation_id": _mock_id("cleanup_batch", payload),
            "status": "applied",
            "cleanup_mode": payload.get("cleanup_mode", "cleanup_label"),
            "attempted_count": count,
            "succeeded_count": count,
            "failed_count": 0,
            "applied_count": count,
        }

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        return {"operation_id": _mock_id("destructive", payload), "status": "executed"}

    def create_outlook_draft(self, payload: dict) -> dict:
        return {
            "draft_id": _mock_id("outlook_draft", payload),
            "status": "created",
            "provider": "mock_outlook",
        }

    def send_outlook_reply(self, payload: dict) -> dict:
        return {
            "message_id": _mock_id("outlook_reply", payload),
            "status": "sent",
            "provider": "mock_outlook",
        }

    def apply_outlook_mail_modify(self, payload: dict) -> dict:
        return {
            "operation_id": _mock_id("outlook_modify", payload),
            "status": "applied",
            "provider": "mock_outlook",
        }

    def create_outlook_calendar_event(self, payload: dict) -> dict:
        return {
            "event_id": _mock_id("outlook_event", payload),
            "status": "created",
            "provider": "mock_outlook",
        }


class GuardedExternalExecutionProvider:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        gmail_client: GmailWriteClient | None = None,
        calendar_client: GoogleCalendarClient | None = None,
        graph_client: MicrosoftGraphMailService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.gmail_client = gmail_client or GmailWriteClient(self.settings)
        self.calendar_client = calendar_client or GoogleCalendarClient(self.settings)
        self.graph_client = graph_client or MicrosoftGraphMailService(self.settings)
        self.name = "external-dry-run" if self.settings.external_write_dry_run else "external-live"

    def create_external_gmail_draft(self, payload: dict) -> dict:
        self._require(
            self.settings.gmail_write_enabled and self.settings.gmail_draft_create_enabled,
            "Gmail external draft creation",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("create_external_gmail_draft", payload)
        return self.gmail_client.create_draft(payload)

    def send_gmail_reply(self, payload: dict) -> dict:
        self._require(
            self.settings.gmail_write_enabled and self.settings.gmail_send_enabled,
            "Gmail send reply",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("send_gmail_reply", payload)
        return self.gmail_client.send_reply(payload)

    def create_calendar_event(self, payload: dict) -> dict:
        self._require(self.settings.google_calendar_write_enabled, "Google Calendar write")
        if self.settings.external_write_dry_run:
            return self._dry_run_result("create_calendar_event", payload)
        return self.calendar_client.create_event(payload)

    def apply_gmail_label_archive(self, payload: dict) -> dict:
        self._require(
            self.settings.gmail_write_enabled and self.settings.gmail_label_archive_enabled,
            "Gmail label/archive",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("apply_gmail_label_archive", payload)
        return self.gmail_client.apply_label_archive(payload)

    def apply_gmail_label_archive_batch(self, payload: dict) -> dict:
        self._require(
            self.settings.gmail_write_enabled and self.settings.gmail_label_archive_enabled,
            "Gmail label/archive batch (cleanup)",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("apply_gmail_label_archive_batch", payload)
        return self.gmail_client.apply_label_archive_batch(payload)

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        raise RuntimeError("Delete/unsubscribe execution is not live-wired")

    def create_outlook_draft(self, payload: dict) -> dict:
        self._require(
            self.settings.outlook_draft_create_enabled,
            "Outlook draft creation",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("create_outlook_draft", payload)
        return self.graph_client.create_draft(payload)

    def send_outlook_reply(self, payload: dict) -> dict:
        self._require(
            self.settings.outlook_send_enabled,
            "Outlook send",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("send_outlook_reply", payload)
        return self.graph_client.create_and_send_reply(payload)

    def apply_outlook_mail_modify(self, payload: dict) -> dict:
        self._require(
            self.settings.outlook_mail_modify_enabled,
            "Outlook mail modify",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("apply_outlook_mail_modify", payload)
        message_id = payload.get("source_message_id") or ""
        operation = payload.get("operation", "modify")
        if operation == "archive":
            return self.graph_client.archive_message(message_id)
        return self.graph_client.modify_message(message_id, payload)

    def create_outlook_calendar_event(self, payload: dict) -> dict:
        self._require(
            self.settings.outlook_calendar_write_enabled,
            "Outlook calendar write",
        )
        if self.settings.external_write_dry_run:
            return self._dry_run_result("create_outlook_calendar_event", payload)
        return self.graph_client.create_calendar_event(payload)

    @staticmethod
    def _dry_run_result(action: str, payload: dict) -> dict:
        return {
            "status": "dry_run",
            "action": action,
            "external_write_performed": False,
            "operation_id": _mock_id(f"dry_{action}", payload),
        }

    @staticmethod
    def _require(enabled: bool, label: str) -> None:
        if not enabled:
            raise RuntimeError(f"{label} is disabled by provider feature flags")


@dataclass(frozen=True)
class PreparedExecution:
    record: ExecutionRecord
    already_exists: bool


def prepare_execution_for_draft(
    db: Session, draft_id: int, *, actor: str = "local-user"
) -> PreparedExecution:
    draft = db.get(DraftReply, draft_id)
    if not draft:
        raise ValueError("Draft not found")
    source_type = (
        (draft.message.source_type if draft.message else None)
        or (draft.thread.source_type if draft.thread else None)
        or "gmail"
    ).strip().lower()

    settings = get_settings()

    if source_type == "outlook":
        # Route Outlook-originated drafts to Microsoft Graph — never Gmail
        if not settings.outlook_draft_create_enabled:
            raise ValueError(
                "Outlook draft creation is not implemented or not enabled."
            )
        action = ExecutionActionType.CREATE_OUTLOOK_DRAFT
        send_ready = send_ready_email_for_draft(draft)
        payload = {
            "source_provider": "outlook",
            "target_provider": "microsoft_graph",
            "draft_id": draft.id,
            "thread_id": draft.thread_id,
            "message_id": draft.message_id,
            "source_thread_id": draft.message.thread.source_thread_id if draft.message and draft.message.thread else None,
            "source_message_id": draft.message.source_message_id if draft.message else None,
            "conversation_id": draft.message.thread.source_thread_id if draft.message and draft.message.thread else None,
            "to": draft.message.sender_email if draft.message else None,
            "subject": send_ready.subject,
            "body": send_ready.body,
            "send_ready_subject": send_ready.subject,
            "send_ready_body": send_ready.body,
            "feature_flag": "OUTLOOK_DRAFT_CREATE_ENABLED",
        }
        record = ExecutionRecord(
            draft_id=draft.id,
            action_type=action,
            attempt_number=_next_attempt_number(db, draft_id=draft.id, action_type=action),
            status=ExecutionStatus.PENDING_REVIEW,
            created_by=actor,
            payload_json=_json(payload),
            provider_name="mock",
        )
        db.add(record)
        db.flush()
        _append_audit(db, record, "prepared", actor, payload)
        db.commit()
        db.refresh(record)
        return PreparedExecution(record=record, already_exists=False)

    if source_type != "gmail":
        raise ValueError(f"External draft creation is not implemented for source: {source_type}.")

    action = ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT
    send_ready = send_ready_email_for_draft(draft)
    payload = {
        "source_provider": "gmail",
        "target_provider": "gmail",
        "draft_id": draft.id,
        "thread_id": draft.thread_id,
        "message_id": draft.message_id,
        "source_thread_id": draft.message.thread.source_thread_id if draft.message and draft.message.thread else None,
        "source_message_id": draft.message.source_message_id if draft.message else None,
        "to": draft.message.sender_email if draft.message else None,
        "subject": send_ready.subject,
        "body": send_ready.body,
        "send_ready_subject": send_ready.subject,
        "send_ready_body": send_ready.body,
        "feature_flag": "GMAIL_WRITE_ENABLED and GMAIL_DRAFT_CREATE_ENABLED",
    }
    record = ExecutionRecord(
        draft_id=draft.id,
        action_type=action,
        attempt_number=_next_attempt_number(db, draft_id=draft.id, action_type=action),
        status=ExecutionStatus.PENDING_REVIEW,
        created_by=actor,
        payload_json=_json(payload),
        provider_name="mock",
    )
    db.add(record)
    db.flush()
    _append_audit(db, record, "prepared", actor, payload)
    db.commit()
    db.refresh(record)
    return PreparedExecution(record=record, already_exists=False)


def prepare_execution_for_review_package(
    db: Session, package_id: int, *, actor: str = "local-user"
) -> PreparedExecution:
    package = db.get(ProposedActionReviewPackage, package_id)
    if not package:
        raise ValueError("Review package not found")
    action = _map_package_to_execution_action(package)

    calendar_proposal = package.calendar_proposals[0] if package.calendar_proposals else None
    payload = _build_review_package_payload(package, action, calendar_proposal)
    record = ExecutionRecord(
        review_package_id=package.id,
        calendar_proposal_id=calendar_proposal.id if calendar_proposal else None,
        action_type=action,
        attempt_number=_next_attempt_number(
            db,
            review_package_id=package.id,
            calendar_proposal_id=calendar_proposal.id if calendar_proposal else None,
            action_type=action,
        ),
        status=ExecutionStatus.PENDING_REVIEW,
        created_by=actor,
        payload_json=_json(payload),
        provider_name="mock",
    )
    db.add(record)
    db.flush()
    _append_audit(db, record, "prepared", actor, payload)
    db.commit()
    db.refresh(record)
    return PreparedExecution(record=record, already_exists=False)


def approve_execution(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
) -> ExecutionRecord:
    record = db.get(ExecutionRecord, execution_id)
    if not record:
        raise ValueError("Execution record not found")
    if record.status == ExecutionStatus.EXECUTED:
        return record
    if record.status != ExecutionStatus.PENDING_REVIEW:
        raise ValueError("Execution record is not in an approvable state")
    record.status = ExecutionStatus.APPROVED
    record.approved_by = actor
    record.approved_at = utcnow()
    _append_audit(db, record, "approved", actor, {"status": record.status.value})
    db.commit()
    db.refresh(record)
    return record


def cancel_execution(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
) -> ExecutionRecord:
    record = db.get(ExecutionRecord, execution_id)
    if not record:
        raise ValueError("Execution record not found")
    if record.status == ExecutionStatus.EXECUTED:
        raise ValueError("Executed records cannot be cancelled")
    record.status = ExecutionStatus.CANCELLED
    _append_audit(db, record, "cancelled", actor, {"status": record.status.value})
    db.commit()
    db.refresh(record)
    return record


def rerun_execution(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
) -> PreparedExecution:
    source = _get_execution_record(db, execution_id)
    payload = _parse_json(source.payload_json)
    record = _copy_execution_attempt(
        db,
        source,
        payload=payload,
        actor=actor,
        event_type="rerun_prepared",
    )
    return PreparedExecution(record=record, already_exists=False)


def clone_execution(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
) -> PreparedExecution:
    source = _get_execution_record(db, execution_id)
    payload = _parse_json(source.payload_json)
    record = _copy_execution_attempt(
        db,
        source,
        payload=payload,
        actor=actor,
        event_type="cloned",
    )
    return PreparedExecution(record=record, already_exists=False)


def prepare_new_execution_from_existing(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
) -> PreparedExecution:
    source = _get_execution_record(db, execution_id)
    if source.draft_id:
        return prepare_execution_for_draft(db, source.draft_id, actor=actor)
    if source.review_package_id:
        return prepare_execution_for_review_package(db, source.review_package_id, actor=actor)
    raise ValueError("Execution record has no source artifact to prepare from")


def confirm_execution(
    db: Session,
    execution_id: int,
    *,
    actor: str = "local-user",
    provider: ExecutionProvider | None = None,
    destructive_confirm_token: str | None = None,
) -> ExecutionRecord:
    record = db.get(ExecutionRecord, execution_id)
    if not record:
        raise ValueError("Execution record not found")
    if record.status == ExecutionStatus.EXECUTED:
        return record
    if record.status != ExecutionStatus.APPROVED:
        raise ValueError("Execution must be approved before confirmation")
    if (
        record.action_type == ExecutionActionType.DELETE_UNSUBSCRIBE
        and destructive_confirm_token != "CONFIRM_DESTRUCTIVE"
    ):
        raise ValueError("Destructive execution requires CONFIRM_DESTRUCTIVE")

    execution_provider = provider or get_default_execution_provider()
    record.status = ExecutionStatus.EXECUTING
    record.confirmed_by = actor
    record.confirmed_at = utcnow()
    _append_audit(db, record, "confirm_started", actor, {"provider": execution_provider.name})
    db.flush()
    payload = _parse_json(record.payload_json)
    try:
        if isinstance(execution_provider, GuardedExternalExecutionProvider):
            ensure_test_execution_allowed(record, execution_provider.settings)
        result = _execute_with_provider(execution_provider, record.action_type, payload)
        record.status = ExecutionStatus.EXECUTED
        record.executed_at = utcnow()
        record.result_json = _json(result)
        record.error_text = None
        record.provider_name = execution_provider.name
        if record.review_package_id:
            package = db.get(ProposedActionReviewPackage, record.review_package_id)
            if package and package.status == ReviewPackageStatus.PENDING:
                package.status = ReviewPackageStatus.APPROVED
        _append_audit(db, record, "executed", actor, result)
    except Exception as exc:  # pragma: no cover - defensive path
        record.status = ExecutionStatus.FAILED
        record.error_text = _sanitize_execution_error(str(exc))
        _append_audit(db, record, "failed", actor, {"error": record.error_text})
    db.commit()
    db.refresh(record)
    return record


def execution_attempt_history(db: Session, record: ExecutionRecord) -> list[ExecutionRecord]:
    query = db.query(ExecutionRecord).filter(ExecutionRecord.action_type == record.action_type)
    if record.draft_id:
        query = query.filter(ExecutionRecord.draft_id == record.draft_id)
    elif record.review_package_id:
        query = query.filter(ExecutionRecord.review_package_id == record.review_package_id)
    elif record.calendar_proposal_id:
        query = query.filter(ExecutionRecord.calendar_proposal_id == record.calendar_proposal_id)
    else:
        query = query.filter(ExecutionRecord.id == record.id)
    return query.order_by(ExecutionRecord.attempt_number.asc(), ExecutionRecord.id.asc()).all()


def get_default_execution_provider(settings: Settings | None = None) -> ExecutionProvider:
    active = settings or get_settings()
    normalized = (active.execution_provider or "mock").strip().lower()
    if normalized in {"external", "live", "google"}:
        return GuardedExternalExecutionProvider(active)
    return MockExecutionProvider()


def microsoft_write_readiness(settings: Settings | None = None) -> dict:
    """Return a structured readiness summary for all Microsoft write surfaces.

    Each entry has: surface, feature_flag, state, reason, recovery.
    States: 'available', 'disabled', 'not_implemented', 'misconfigured'.
    """
    active = settings or get_settings()
    graph_enabled = bool(active.microsoft_graph_enabled)
    graph_configured = bool(active.microsoft_tenant_id and active.microsoft_client_id)

    def _surface_state(flag_enabled: bool) -> tuple[str, str, str]:
        if not graph_enabled:
            return (
                "misconfigured",
                "MICROSOFT_GRAPH_ENABLED is false",
                "Set MICROSOFT_GRAPH_ENABLED=true and configure tenant/client IDs.",
            )
        if not graph_configured:
            return (
                "misconfigured",
                "Microsoft Graph tenant/client IDs not configured",
                "Set MICROSOFT_TENANT_ID and MICROSOFT_CLIENT_ID.",
            )
        if not flag_enabled:
            return (
                "disabled",
                "Feature flag is false",
                "Enable the feature flag in .env when ready for live writes.",
            )
        return (
            "available",
            "Enabled and configured",
            "External write is guarded by approval, confirmation, and audit pipeline.",
        )

    draft_state, draft_reason, draft_recovery = _surface_state(active.outlook_draft_create_enabled)
    send_state, send_reason, send_recovery = _surface_state(active.outlook_send_enabled)
    modify_state, modify_reason, modify_recovery = _surface_state(active.outlook_mail_modify_enabled)
    cal_state, cal_reason, cal_recovery = _surface_state(active.outlook_calendar_write_enabled)

    return {
        "outlook_draft_create": {
            "surface": "Outlook draft creation",
            "feature_flag": "OUTLOOK_DRAFT_CREATE_ENABLED",
            "state": draft_state,
            "reason": draft_reason,
            "recovery": draft_recovery,
        },
        "outlook_send": {
            "surface": "Outlook send / reply",
            "feature_flag": "OUTLOOK_SEND_ENABLED",
            "state": send_state,
            "reason": send_reason,
            "recovery": send_recovery,
        },
        "outlook_mail_modify": {
            "surface": "Outlook mail modify (category/archive)",
            "feature_flag": "OUTLOOK_MAIL_MODIFY_ENABLED",
            "state": modify_state,
            "reason": modify_reason,
            "recovery": modify_recovery,
        },
        "outlook_calendar_write": {
            "surface": "Outlook calendar event creation",
            "feature_flag": "OUTLOOK_CALENDAR_WRITE_ENABLED",
            "state": cal_state,
            "reason": cal_reason,
            "recovery": cal_recovery,
        },
    }


def list_execution_records(db: Session, *, limit: int = 200) -> list[ExecutionRecord]:
    return (
        db.query(ExecutionRecord)
        .order_by(ExecutionRecord.created_at.desc(), ExecutionRecord.id.desc())
        .limit(limit)
        .all()
    )


def audit_entries_for_execution(db: Session, execution_id: int) -> list[ExecutionAuditLog]:
    return (
        db.query(ExecutionAuditLog)
        .filter(ExecutionAuditLog.execution_record_id == execution_id)
        .order_by(ExecutionAuditLog.created_at.asc(), ExecutionAuditLog.id.asc())
        .all()
    )


def _map_package_to_execution_action(
    package: "ProposedActionReviewPackage",
) -> ExecutionActionType:
    action_type = package.action_type
    # Detect source provider for routing
    source_provider = _source_provider_for_package(package)

    if action_type in {ProposedActionType.REPLY, ProposedActionType.ASK_CLARIFYING_QUESTION}:
        if source_provider == "outlook":
            return ExecutionActionType.SEND_OUTLOOK_REPLY
        return ExecutionActionType.SEND_GMAIL_REPLY
    if action_type in {ProposedActionType.CREATE_CALENDAR_REMINDER, ProposedActionType.SCHEDULE_MEETING}:
        if source_provider == "outlook":
            return ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT
        return ExecutionActionType.CREATE_CALENDAR_EVENT
    if action_type in {ProposedActionType.MARK_NOISE, ProposedActionType.ARCHIVE_CANDIDATE}:
        if source_provider == "outlook":
            return ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY
        return ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE
    if action_type in {ProposedActionType.DELETE_CANDIDATE, ProposedActionType.UNSUBSCRIBE_REVIEW}:
        return ExecutionActionType.DELETE_UNSUBSCRIBE
    raise ValueError("Review package action type is not executable in this phase")


def _source_provider_for_package(package: "ProposedActionReviewPackage") -> str:
    message = package.message
    if message:
        source_type = (message.source_type or "").strip().lower()
        if source_type:
            return source_type
        thread = getattr(message, "thread", None)
        if thread:
            return (thread.source_type or "gmail").strip().lower()
    return "gmail"


def _build_review_package_payload(
    package: ProposedActionReviewPackage,
    action: ExecutionActionType,
    calendar_proposal: CalendarActionProposal | None,
) -> dict:
    message = package.message
    source_provider = _source_provider_for_package(package)
    # Determine target provider based on action type
    _OUTLOOK_ACTIONS = {
        ExecutionActionType.CREATE_OUTLOOK_DRAFT,
        ExecutionActionType.SEND_OUTLOOK_REPLY,
        ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY,
        ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT,
    }
    target_provider = "microsoft_graph" if action in _OUTLOOK_ACTIONS else "gmail"
    feature_flag = _feature_flag_for_action(action)
    base = {
        "review_package_id": package.id,
        "thread_id": package.thread_id,
        "message_id": package.message_id,
        "source_message_id": message.source_message_id if message else None,
        "source_thread_id": message.thread.source_thread_id if message and message.thread else None,
        "source_provider": source_provider,
        "target_provider": target_provider,
        "feature_flag": feature_flag,
    }
    if action in {ExecutionActionType.SEND_GMAIL_REPLY, ExecutionActionType.SEND_OUTLOOK_REPLY}:
        fallback_subject = f"Re: {message.subject}" if message and message.subject else "Re:"
        send_ready = sanitize_send_ready_email_text(
            package.draft_response
            or "Approved execution from review package with no draft_response text.",
            fallback_subject=fallback_subject,
        )
        return {
            **base,
            "to": message.sender_email if message else None,
            "subject": send_ready.subject,
            "body": send_ready.body,
            "send_ready_subject": send_ready.subject,
            "send_ready_body": send_ready.body,
        }
    if action in {ExecutionActionType.CREATE_CALENDAR_EVENT, ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT}:
        return {
            **base,
            "summary": message.subject if message else "CommsDesk proposed calendar action",
            "action_kind": calendar_proposal.action_kind if calendar_proposal else "create_meeting",
            "proposed_start_at": (
                calendar_proposal.proposed_start_at.isoformat()
                if calendar_proposal and calendar_proposal.proposed_start_at
                else None
            ),
            "proposed_end_at": (
                calendar_proposal.proposed_end_at.isoformat()
                if calendar_proposal and calendar_proposal.proposed_end_at
                else None
            ),
            "reminder_at": (
                calendar_proposal.reminder_at.isoformat()
                if calendar_proposal and calendar_proposal.reminder_at
                else None
            ),
        }
    if action in {ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY}:
        return {
            **base,
            "operation": (
                "archive"
                if package.action_type == ProposedActionType.ARCHIVE_CANDIDATE
                else "mark_noise_label"
            ),
        }
    return {
        **base,
        "operation": (
            "unsubscribe" if package.action_type == ProposedActionType.UNSUBSCRIBE_REVIEW else "delete"
        ),
        "warning": "Destructive action requires CONFIRM_DESTRUCTIVE",
    }


def _feature_flag_for_action(action: ExecutionActionType) -> str:
    _flags = {
        ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT: "GMAIL_WRITE_ENABLED and GMAIL_DRAFT_CREATE_ENABLED",
        ExecutionActionType.SEND_GMAIL_REPLY: "GMAIL_WRITE_ENABLED and GMAIL_SEND_ENABLED",
        ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE: "GMAIL_WRITE_ENABLED and GMAIL_LABEL_ARCHIVE_ENABLED",
        ExecutionActionType.CREATE_CALENDAR_EVENT: "GOOGLE_CALENDAR_WRITE_ENABLED",
        ExecutionActionType.CREATE_OUTLOOK_DRAFT: "OUTLOOK_DRAFT_CREATE_ENABLED",
        ExecutionActionType.SEND_OUTLOOK_REPLY: "OUTLOOK_SEND_ENABLED",
        ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY: "OUTLOOK_MAIL_MODIFY_ENABLED",
        ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT: "OUTLOOK_CALENDAR_WRITE_ENABLED",
        ExecutionActionType.DELETE_UNSUBSCRIBE: "N/A — requires CONFIRM_DESTRUCTIVE",
    }
    return _flags.get(action, "unknown")


def _get_execution_record(db: Session, execution_id: int) -> ExecutionRecord:
    record = db.get(ExecutionRecord, execution_id)
    if not record:
        raise ValueError("Execution record not found")
    return record


def _copy_execution_attempt(
    db: Session,
    source: ExecutionRecord,
    *,
    payload: dict,
    actor: str,
    event_type: str,
) -> ExecutionRecord:
    record = ExecutionRecord(
        review_package_id=source.review_package_id,
        draft_id=source.draft_id,
        calendar_proposal_id=source.calendar_proposal_id,
        action_type=source.action_type,
        attempt_number=_next_attempt_number(
            db,
            draft_id=source.draft_id,
            review_package_id=source.review_package_id,
            calendar_proposal_id=source.calendar_proposal_id,
            action_type=source.action_type,
        ),
        status=ExecutionStatus.PENDING_REVIEW,
        created_by=actor,
        payload_json=_json(payload),
        provider_name="mock",
    )
    db.add(record)
    db.flush()
    _append_audit(
        db,
        record,
        event_type,
        actor,
        {"source_execution_id": source.id, "payload": payload},
    )
    db.commit()
    db.refresh(record)
    return record


def _next_attempt_number(
    db: Session,
    *,
    action_type: ExecutionActionType,
    draft_id: int | None = None,
    review_package_id: int | None = None,
    calendar_proposal_id: int | None = None,
) -> int:
    query = db.query(func.max(ExecutionRecord.attempt_number)).filter(
        ExecutionRecord.action_type == action_type
    )
    if draft_id is not None:
        query = query.filter(ExecutionRecord.draft_id == draft_id)
    elif review_package_id is not None:
        query = query.filter(ExecutionRecord.review_package_id == review_package_id)
    elif calendar_proposal_id is not None:
        query = query.filter(ExecutionRecord.calendar_proposal_id == calendar_proposal_id)
    else:
        return 1
    return int(query.scalar() or 0) + 1


def _execute_with_provider(
    provider: ExecutionProvider, action_type: ExecutionActionType, payload: dict
) -> dict:
    # Provider mismatch guard: Outlook actions must never fall back to Gmail
    source_provider = (payload.get("source_provider") or "").strip().lower()

    _OUTLOOK_ACTIONS = {
        ExecutionActionType.CREATE_OUTLOOK_DRAFT,
        ExecutionActionType.SEND_OUTLOOK_REPLY,
        ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY,
        ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT,
    }
    _GMAIL_ACTIONS = {
        ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
        ExecutionActionType.SEND_GMAIL_REPLY,
        ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE,
    }

    if action_type in _OUTLOOK_ACTIONS and source_provider == "gmail":
        raise ValueError(
            f"Provider mismatch: action {action_type} is an Outlook write but source_provider is gmail"
        )
    if action_type in _GMAIL_ACTIONS and source_provider == "outlook":
        raise ValueError(
            f"Provider mismatch: action {action_type} is a Gmail write but source_provider is outlook"
        )

    if action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT:
        return provider.create_external_gmail_draft(payload)
    if action_type == ExecutionActionType.SEND_GMAIL_REPLY:
        return provider.send_gmail_reply(payload)
    if action_type == ExecutionActionType.CREATE_CALENDAR_EVENT:
        return provider.create_calendar_event(payload)
    if action_type == ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE:
        # Cleanup batch operations use a richer payload with cleanup_mode field
        cleanup_mode = payload.get("cleanup_mode", "")
        if cleanup_mode:
            if not str(cleanup_mode).startswith("cleanup_"):
                raise ValueError(f"Unsupported cleanup mode in execution payload: {cleanup_mode!r}")
            return provider.apply_gmail_label_archive_batch(payload)
        return provider.apply_gmail_label_archive(payload)
    if action_type == ExecutionActionType.DELETE_UNSUBSCRIBE:
        return provider.delete_or_unsubscribe(payload)
    # Phase 29 — Microsoft Graph write actions
    if action_type == ExecutionActionType.CREATE_OUTLOOK_DRAFT:
        return provider.create_outlook_draft(payload)
    if action_type == ExecutionActionType.SEND_OUTLOOK_REPLY:
        return provider.send_outlook_reply(payload)
    if action_type == ExecutionActionType.APPLY_OUTLOOK_MAIL_MODIFY:
        return provider.apply_outlook_mail_modify(payload)
    if action_type == ExecutionActionType.CREATE_OUTLOOK_CALENDAR_EVENT:
        return provider.create_outlook_calendar_event(payload)
    raise ValueError("Unsupported execution action")


def _append_audit(
    db: Session,
    record: ExecutionRecord,
    event_type: str,
    actor: str | None,
    details: dict | None,
) -> None:
    db.add(
        ExecutionAuditLog(
            execution_record_id=record.id,
            event_type=event_type,
            actor=actor,
            details=_json(details) if details is not None else None,
        )
    )


def _json(value: dict | None) -> str:
    return json.dumps(value or {}, sort_keys=True)


def _parse_json(value: str | None) -> dict:
    if not value:
        return {}
    return json.loads(value)


def _mock_id(prefix: str, payload: dict) -> str:
    seed = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _sanitize_execution_error(value: str) -> str:
    text = " ".join((value or "Provider failure").split())
    for marker in ("access_token", "refresh_token", "client_secret", "authorization"):
        text = text.replace(marker, "[redacted]")
    return text[:500]
