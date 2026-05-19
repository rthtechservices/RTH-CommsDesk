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
from app.services.draft_service import sanitize_send_ready_email_text, send_ready_email_for_draft


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

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        """Delete or unsubscribe operation with explicit confirmation."""


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

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        return {"operation_id": _mock_id("destructive", payload), "status": "executed"}


class GuardedExternalExecutionProvider:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        gmail_client: GmailWriteClient | None = None,
        calendar_client: GoogleCalendarClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.gmail_client = gmail_client or GmailWriteClient(self.settings)
        self.calendar_client = calendar_client or GoogleCalendarClient(self.settings)
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

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        raise RuntimeError("Delete/unsubscribe execution is not live-wired")

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
    action = ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT
    send_ready = send_ready_email_for_draft(draft)
    payload = {
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
    action = _map_package_to_execution_action(package.action_type)

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


def _map_package_to_execution_action(action_type: ProposedActionType) -> ExecutionActionType:
    if action_type in {ProposedActionType.REPLY, ProposedActionType.ASK_CLARIFYING_QUESTION}:
        return ExecutionActionType.SEND_GMAIL_REPLY
    if action_type in {ProposedActionType.CREATE_CALENDAR_REMINDER, ProposedActionType.SCHEDULE_MEETING}:
        return ExecutionActionType.CREATE_CALENDAR_EVENT
    if action_type in {ProposedActionType.MARK_NOISE, ProposedActionType.ARCHIVE_CANDIDATE}:
        return ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE
    if action_type in {ProposedActionType.DELETE_CANDIDATE, ProposedActionType.UNSUBSCRIBE_REVIEW}:
        return ExecutionActionType.DELETE_UNSUBSCRIBE
    raise ValueError("Review package action type is not executable in this phase")


def _build_review_package_payload(
    package: ProposedActionReviewPackage,
    action: ExecutionActionType,
    calendar_proposal: CalendarActionProposal | None,
) -> dict:
    message = package.message
    base = {
        "review_package_id": package.id,
        "thread_id": package.thread_id,
        "message_id": package.message_id,
        "source_message_id": message.source_message_id if message else None,
        "source_thread_id": message.thread.source_thread_id if message and message.thread else None,
    }
    if action == ExecutionActionType.SEND_GMAIL_REPLY:
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
    if action == ExecutionActionType.CREATE_CALENDAR_EVENT:
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
    if action == ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE:
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
    if action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT:
        return provider.create_external_gmail_draft(payload)
    if action_type == ExecutionActionType.SEND_GMAIL_REPLY:
        return provider.send_gmail_reply(payload)
    if action_type == ExecutionActionType.CREATE_CALENDAR_EVENT:
        return provider.create_calendar_event(payload)
    if action_type == ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE:
        return provider.apply_gmail_label_archive(payload)
    if action_type == ExecutionActionType.DELETE_UNSUBSCRIBE:
        return provider.delete_or_unsubscribe(payload)
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
