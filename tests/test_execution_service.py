from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from app.models.entities import (
    CalendarActionProposal,
    DraftReply,
    ExecutionActionType,
    ExecutionAuditLog,
    ExecutionStatus,
    Message,
    MessageThread,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
    VoiceProfile,
)
from app.core.config import Settings
from app.services.execution_service import (
    GuardedExternalExecutionProvider,
    approve_execution,
    clone_execution,
    confirm_execution,
    prepare_new_execution_from_existing,
    prepare_execution_for_draft,
    prepare_execution_for_review_package,
    rerun_execution,
)
from app.services.external_provider_clients import GMAIL_SCOPE_REAUTH_MESSAGE


def test_prepare_and_execute_external_gmail_draft_once(db_session):
    draft = _seed_draft(db_session)

    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    assert prepared.record.status == ExecutionStatus.PENDING_REVIEW
    assert prepared.record.action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT

    approved = approve_execution(db_session, prepared.record.id, actor="tester")
    executed = confirm_execution(db_session, approved.id, actor="tester")
    second = confirm_execution(db_session, approved.id, actor="tester")

    assert executed.status == ExecutionStatus.EXECUTED
    assert second.id == executed.id
    assert executed.result_json is not None
    assert db_session.query(ExecutionAuditLog).filter_by(execution_record_id=executed.id).count() >= 3


def test_prepare_and_execute_send_reply_from_review_package(db_session):
    package = _seed_review_package(
        db_session,
        action_type=ProposedActionType.REPLY,
        draft_response="Hi there,\n\nI can help with this.\n\nBest",
    )

    prepared = prepare_execution_for_review_package(db_session, package.id, actor="tester")
    assert prepared.record.action_type == ExecutionActionType.SEND_GMAIL_REPLY

    approve_execution(db_session, prepared.record.id, actor="tester")
    executed = confirm_execution(db_session, prepared.record.id, actor="tester")

    assert executed.status == ExecutionStatus.EXECUTED
    db_session.refresh(package)
    assert package.status == ReviewPackageStatus.APPROVED


def test_prepare_and_execute_calendar_event_from_calendar_proposal(db_session):
    package = _seed_review_package(
        db_session,
        action_type=ProposedActionType.CREATE_CALENDAR_REMINDER,
        draft_response=None,
    )
    proposal = CalendarActionProposal(
        review_package_id=package.id,
        action_kind="create_reminder",
        reminder_at=datetime(2026, 6, 5, 9, 0, tzinfo=UTC),
        availability_reasoning="Detected due date, reminder scheduled one week earlier.",
        provider_name="mock",
    )
    db_session.add(proposal)
    db_session.commit()

    prepared = prepare_execution_for_review_package(db_session, package.id, actor="tester")
    assert prepared.record.action_type == ExecutionActionType.CREATE_CALENDAR_EVENT

    approve_execution(db_session, prepared.record.id, actor="tester")
    executed = confirm_execution(db_session, prepared.record.id, actor="tester")

    assert executed.status == ExecutionStatus.EXECUTED
    assert "event_id" in (executed.result_json or "")


def test_prepare_and_execute_label_archive_action(db_session):
    package = _seed_review_package(
        db_session,
        action_type=ProposedActionType.ARCHIVE_CANDIDATE,
        draft_response=None,
    )

    prepared = prepare_execution_for_review_package(db_session, package.id, actor="tester")
    assert prepared.record.action_type == ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE

    approve_execution(db_session, prepared.record.id, actor="tester")
    executed = confirm_execution(db_session, prepared.record.id, actor="tester")

    assert executed.status == ExecutionStatus.EXECUTED
    assert "operation_id" in (executed.result_json or "")


def test_prepare_creates_new_immutable_attempts(db_session):
    draft = _seed_draft(db_session)

    first = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    second = prepare_execution_for_draft(db_session, draft.id, actor="tester")

    assert second.already_exists is False
    assert first.record.id != second.record.id
    assert first.record.attempt_number == 1
    assert second.record.attempt_number == 2


def test_rerun_clone_and_prepare_new_create_pending_attempts(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")
    executed = confirm_execution(db_session, prepared.record.id, actor="tester")

    rerun = rerun_execution(db_session, executed.id, actor="tester")
    clone = clone_execution(db_session, executed.id, actor="tester")
    prepared_new = prepare_new_execution_from_existing(db_session, executed.id, actor="tester")

    assert [rerun.record.attempt_number, clone.record.attempt_number, prepared_new.record.attempt_number] == [
        2,
        3,
        4,
    ]
    for record in [rerun.record, clone.record, prepared_new.record]:
        assert record.status == ExecutionStatus.PENDING_REVIEW
        assert record.approved_at is None
        assert record.confirmed_at is None
        assert record.executed_at is None


def test_gmail_draft_execution_payload_uses_clean_send_ready_body(db_session):
    draft = _seed_draft(
        db_session,
        draft_text=(
            "Review-only draft suggestion. This has not been sent. Caveats: verify timing.\n\n"
            "Subject: Re: FW: Time to Meet\n\n"
            "Hi Pat,\n\nTuesday at 2 works for me.\n\nBest"
        ),
    )

    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    payload = json.loads(prepared.record.payload_json)

    assert payload["subject"] == "Re: FW: Time to Meet"
    assert payload["body"] == "Hi Pat,\n\nTuesday at 2 works for me.\n\nBest"
    assert "Review-only draft suggestion" not in payload["body"]
    assert "This has not been sent" not in payload["body"]
    assert "Caveats:" not in payload["body"]
    assert "Subject:" not in payload["body"]


def test_external_execution_provider_dry_run_requires_feature_flags(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")
    provider = GuardedExternalExecutionProvider(
        Settings(
            _env_file=None,
            execution_provider="external",
            external_write_dry_run=True,
            operational_test_mode=True,
            execution_test_email_allowlist="client@example.com",
            gmail_write_enabled=True,
            gmail_draft_create_enabled=True,
        )
    )

    executed = confirm_execution(db_session, prepared.record.id, actor="tester", provider=provider)

    assert executed.status == ExecutionStatus.EXECUTED
    assert executed.provider_name == "external-dry-run"
    assert '"external_write_performed": false' in (executed.result_json or "")


def test_external_execution_provider_fails_closed_when_flag_missing(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")
    provider = GuardedExternalExecutionProvider(
        Settings(
            _env_file=None,
            execution_provider="external",
            external_write_dry_run=True,
            operational_test_mode=True,
            execution_test_email_allowlist="client@example.com",
        )
    )

    failed = confirm_execution(db_session, prepared.record.id, actor="tester", provider=provider)

    assert failed.status == ExecutionStatus.FAILED
    assert failed.error_text == "Blocked: feature flag disabled. Set GMAIL_WRITE_ENABLED=true."


def test_external_execution_provider_blocks_non_allowlisted_recipient(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")
    provider = GuardedExternalExecutionProvider(
        Settings(
            _env_file=None,
            execution_provider="external",
            external_write_dry_run=True,
            operational_test_mode=True,
            execution_test_email_allowlist="allowed@example.com",
            gmail_write_enabled=True,
            gmail_draft_create_enabled=True,
        )
    )

    failed = confirm_execution(db_session, prepared.record.id, actor="tester", provider=provider)

    assert failed.status == ExecutionStatus.FAILED
    assert failed.error_text == "Blocked: recipient not allowlisted."


def test_execution_records_actionable_gmail_scope_error(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")

    failed = confirm_execution(
        db_session,
        prepared.record.id,
        actor="tester",
        provider=_ScopeFailingProvider(),
    )

    assert failed.status == ExecutionStatus.FAILED
    assert failed.error_text == GMAIL_SCOPE_REAUTH_MESSAGE
    audit = (
        db_session.query(ExecutionAuditLog)
        .filter_by(execution_record_id=failed.id, event_type="failed")
        .one()
    )
    assert GMAIL_SCOPE_REAUTH_MESSAGE in (audit.details or "")


def _seed_draft(
    db_session,
    *,
    draft_text: str = "Hi,\n\nHere is the update.\n\nBest",
) -> DraftReply:
    thread = MessageThread(source_type="gmail", source_thread_id="exec-draft-thread")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="exec-draft-message",
        sender_email="client@example.com",
        subject="Project update",
        snippet="Can you send the update?",
    )
    db_session.add(message)
    db_session.flush()
    profile = VoiceProfile(name="Execution Voice", audience_type="client")
    db_session.add(profile)
    db_session.flush()
    draft = DraftReply(
        thread_id=thread.id,
        message_id=message.id,
        voice_profile_id=profile.id,
        draft_text=draft_text,
    )
    db_session.add(draft)
    db_session.commit()
    return draft


def _seed_review_package(
    db_session,
    *,
    action_type: ProposedActionType,
    draft_response: str | None,
) -> ProposedActionReviewPackage:
    thread = MessageThread(source_type="gmail", source_thread_id=f"exec-package-thread-{action_type.value}")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id=f"exec-package-message-{action_type.value}",
        sender_email="person@example.com",
        subject="Execution package source",
        snippet="source",
    )
    db_session.add(message)
    db_session.flush()
    package = ProposedActionReviewPackage(
        thread_id=thread.id,
        message_id=message.id,
        action_type=action_type,
        explanation="Execution candidate",
        confidence=Decimal("0.8400"),
        draft_response=draft_response,
        status=ReviewPackageStatus.PENDING,
        provider_name="mock",
        is_external_action=False,
    )
    db_session.add(package)
    db_session.commit()
    return package


class _ScopeFailingProvider:
    name = "scope-failing-provider"

    def create_external_gmail_draft(self, payload: dict) -> dict:
        raise RuntimeError(GMAIL_SCOPE_REAUTH_MESSAGE)

    def send_gmail_reply(self, payload: dict) -> dict:
        raise RuntimeError(GMAIL_SCOPE_REAUTH_MESSAGE)

    def create_calendar_event(self, payload: dict) -> dict:
        return {"status": "not-used"}

    def apply_gmail_label_archive(self, payload: dict) -> dict:
        raise RuntimeError(GMAIL_SCOPE_REAUTH_MESSAGE)

    def delete_or_unsubscribe(self, payload: dict) -> dict:
        raise RuntimeError("not wired")
