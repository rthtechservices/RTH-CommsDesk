from __future__ import annotations

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
    confirm_execution,
    prepare_execution_for_draft,
    prepare_execution_for_review_package,
)


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


def test_duplicate_prepare_returns_existing_execution_record(db_session):
    draft = _seed_draft(db_session)

    first = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    second = prepare_execution_for_draft(db_session, draft.id, actor="tester")

    assert second.already_exists is True
    assert first.record.id == second.record.id


def test_external_execution_provider_dry_run_requires_feature_flags(db_session):
    draft = _seed_draft(db_session)
    prepared = prepare_execution_for_draft(db_session, draft.id, actor="tester")
    approve_execution(db_session, prepared.record.id, actor="tester")
    provider = GuardedExternalExecutionProvider(
        Settings(
            _env_file=None,
            execution_provider="external",
            external_write_dry_run=True,
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
        Settings(_env_file=None, execution_provider="external", external_write_dry_run=True)
    )

    failed = confirm_execution(db_session, prepared.record.id, actor="tester", provider=provider)

    assert failed.status == ExecutionStatus.FAILED
    assert "disabled by provider feature flags" in (failed.error_text or "")


def _seed_draft(db_session) -> DraftReply:
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
        draft_text="Hi,\n\nHere is the update.\n\nBest",
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
