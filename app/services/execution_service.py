from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

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
    existing = (
        db.query(ExecutionRecord)
        .filter(ExecutionRecord.draft_id == draft.id, ExecutionRecord.action_type == action)
        .order_by(ExecutionRecord.id.desc())
        .first()
    )
    if existing:
        return PreparedExecution(record=existing, already_exists=True)
    payload = {
        "draft_id": draft.id,
        "thread_id": draft.thread_id,
        "message_id": draft.message_id,
        "subject": draft.message.subject if draft.message else None,
        "to": draft.message.sender_email if draft.message else None,
        "draft_text": draft.draft_text,
    }
    record = ExecutionRecord(
        draft_id=draft.id,
        action_type=action,
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
    existing = (
        db.query(ExecutionRecord)
        .filter(ExecutionRecord.review_package_id == package.id, ExecutionRecord.action_type == action)
        .order_by(ExecutionRecord.id.desc())
        .first()
    )
    if existing:
        return PreparedExecution(record=existing, already_exists=True)

    calendar_proposal = package.calendar_proposals[0] if package.calendar_proposals else None
    payload = _build_review_package_payload(package, action, calendar_proposal)
    record = ExecutionRecord(
        review_package_id=package.id,
        calendar_proposal_id=calendar_proposal.id if calendar_proposal else None,
        action_type=action,
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
    if record.status not in {ExecutionStatus.PENDING_REVIEW, ExecutionStatus.FAILED}:
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

    execution_provider = provider or MockExecutionProvider()
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
        record.error_text = str(exc)
        _append_audit(db, record, "failed", actor, {"error": str(exc)})
    db.commit()
    db.refresh(record)
    return record


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
    }
    if action == ExecutionActionType.SEND_GMAIL_REPLY:
        return {
            **base,
            "to": message.sender_email if message else None,
            "subject": f"Re: {message.subject}" if message and message.subject else "Re:",
            "body": package.draft_response
            or "Approved execution from review package with no draft_response text.",
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
