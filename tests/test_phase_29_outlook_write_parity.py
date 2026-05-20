"""Phase 29 — Microsoft Write Cutover and Provider Parity

Focused tests for:
- Gmail source uses Gmail write path.
- Outlook source uses Microsoft Graph write path when enabled.
- Outlook source never attempts Gmail draft/send.
- Outlook draft blocks when disabled; executes with mocked Graph client when enabled.
- Outlook send blocks when disabled; executes with mocked Graph client when enabled.
- Outlook calendar write blocks when disabled; executes with mocked Graph client when enabled.
- Outlook mail modify blocks when disabled; seams correctly when enabled.
- Provider mismatch is blocked before mutation.
- Execution requires approval and final confirmation.
- Provider status reports Microsoft write readiness correctly.
- Route smoke.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import app
from app.models.entities import (
    DraftReply,
    DraftStatus,
    ExecutionActionType,
    ExecutionRecord,
    ExecutionStatus,
    Message,
    MessageThread,
    VoiceProfile,
)
from app.services.execution_service import (
    GuardedExternalExecutionProvider,
    MockExecutionProvider,
    approve_execution,
    confirm_execution,
    microsoft_write_readiness,
    prepare_execution_for_draft,
)
from app.services.provider_status_service import provider_status_rows


# ---------------------------------------------------------------------------
# Helper: seed a draft attached to a thread/message with a given source_type
# ---------------------------------------------------------------------------

def _seed_draft(
    db: Session,
    *,
    source_type: str = "gmail",
    suffix: str = "p29",
) -> DraftReply:
    thread = MessageThread(
        source_type=source_type,
        source_thread_id=f"p29-thread-{suffix}",
        normalized_subject=f"Phase 29 {suffix}",
    )
    db.add(thread)
    db.flush()
    message = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=f"p29-msg-{suffix}",
        sender_email=f"{suffix}@example.com",
        subject=f"Phase 29 {suffix}",
        snippet="Test snippet.",
    )
    db.add(message)
    db.flush()
    profile = VoiceProfile(
        name=f"P29 Voice {suffix}",
        audience_type="client",
        signoff_style="Best",
    )
    db.add(profile)
    db.flush()
    draft = DraftReply(
        thread_id=thread.id,
        message_id=message.id,
        voice_profile_id=profile.id,
        draft_text=f"Draft for {suffix}",
        send_ready_subject=f"Re: Phase 29 {suffix}",
        send_ready_body=f"Ready body {suffix}",
        status=DraftStatus.GENERATED,
        provider_name="mock",
    )
    db.add(draft)
    db.commit()
    return draft


# ---------------------------------------------------------------------------
# 1. Gmail source uses Gmail write path
# ---------------------------------------------------------------------------

def test_gmail_source_uses_gmail_write_path(db_session: Session, monkeypatch):
    monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
    monkeypatch.setenv("GMAIL_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="gmail", suffix="gmail-path")
    result = prepare_execution_for_draft(db_session, draft.id)

    assert result.record.action_type == ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT
    payload = json.loads(result.record.payload_json)
    assert payload.get("source_provider") == "gmail"
    assert payload.get("target_provider") == "gmail"


# ---------------------------------------------------------------------------
# 2. Outlook source uses Microsoft Graph write path when enabled
# ---------------------------------------------------------------------------

def test_outlook_source_uses_graph_write_path_when_enabled(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="graph-path")
    result = prepare_execution_for_draft(db_session, draft.id)

    assert result.record.action_type == ExecutionActionType.CREATE_OUTLOOK_DRAFT
    payload = json.loads(result.record.payload_json)
    assert payload.get("source_provider") == "outlook"
    assert payload.get("target_provider") == "microsoft_graph"


# ---------------------------------------------------------------------------
# 3. Outlook source never attempts Gmail draft/send
# ---------------------------------------------------------------------------

def test_outlook_source_never_uses_gmail_write_path(db_session: Session, monkeypatch):
    # Even with all Gmail flags on, Outlook source must not create a Gmail action
    monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
    monkeypatch.setenv("GMAIL_DRAFT_CREATE_ENABLED", "true")
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "false")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="no-gmail")

    with pytest.raises(ValueError, match="not implemented or not enabled"):
        prepare_execution_for_draft(db_session, draft.id)

    # Confirm no ExecutionRecord was created
    assert db_session.query(ExecutionRecord).count() == 0


def test_outlook_draft_never_creates_gmail_action_type(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="no-gmail-type")
    result = prepare_execution_for_draft(db_session, draft.id)

    assert result.record.action_type != ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT
    assert result.record.action_type != ExecutionActionType.SEND_GMAIL_REPLY


# ---------------------------------------------------------------------------
# 4. Outlook draft blocks when disabled
# ---------------------------------------------------------------------------

def test_outlook_draft_blocks_when_disabled(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "false")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="blocked")

    with pytest.raises(ValueError, match="not implemented or not enabled"):
        prepare_execution_for_draft(db_session, draft.id)


# ---------------------------------------------------------------------------
# 5. Outlook draft executes with mocked Graph client when enabled
# ---------------------------------------------------------------------------

def test_outlook_draft_executes_with_mock_graph_when_enabled(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    mock_graph.create_draft.return_value = {
        "status": "created",
        "draft_id": "GRAPH-DRAFT-001",
        "provider": "microsoft_graph",
    }

    provider = GuardedExternalExecutionProvider(
        settings, graph_client=mock_graph
    )

    payload = {
        "source_provider": "outlook",
        "target_provider": "microsoft_graph",
        "to": "test@example.com",
        "send_ready_subject": "Re: test",
        "send_ready_body": "Hello",
        "feature_flag": "OUTLOOK_DRAFT_CREATE_ENABLED",
    }
    result = provider.create_outlook_draft(payload)

    assert result["status"] == "created"
    assert result["draft_id"] == "GRAPH-DRAFT-001"
    mock_graph.create_draft.assert_called_once()


def test_outlook_draft_dry_run_does_not_call_graph(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "true")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    payload = {
        "source_provider": "outlook",
        "target_provider": "microsoft_graph",
        "to": "test@example.com",
        "send_ready_body": "Hello",
    }
    result = provider.create_outlook_draft(payload)

    assert result["status"] == "dry_run"
    assert result["external_write_performed"] is False
    mock_graph.create_draft.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Outlook send blocks when disabled
# ---------------------------------------------------------------------------

def test_outlook_send_blocks_when_disabled(monkeypatch):
    monkeypatch.setenv("OUTLOOK_SEND_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    with pytest.raises(RuntimeError, match="Outlook send is disabled by provider feature flags"):
        provider.send_outlook_reply({"source_provider": "outlook", "to": "test@example.com"})


# ---------------------------------------------------------------------------
# 7. Outlook send executes with mocked Graph client when enabled
# ---------------------------------------------------------------------------

def test_outlook_send_executes_with_mock_graph_when_enabled(monkeypatch):
    monkeypatch.setenv("OUTLOOK_SEND_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    mock_graph.create_and_send_reply.return_value = {
        "status": "sent",
        "message_id": "GRAPH-MSG-001",
        "provider": "microsoft_graph",
    }

    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    payload = {
        "source_provider": "outlook",
        "target_provider": "microsoft_graph",
        "source_message_id": "ORIG-MSG-001",
        "to": "test@example.com",
        "send_ready_body": "Reply text",
        "feature_flag": "OUTLOOK_SEND_ENABLED",
    }
    result = provider.send_outlook_reply(payload)

    assert result["status"] == "sent"
    mock_graph.create_and_send_reply.assert_called_once()


# ---------------------------------------------------------------------------
# 8. Outlook calendar write blocks when disabled
# ---------------------------------------------------------------------------

def test_outlook_calendar_write_blocks_when_disabled(monkeypatch):
    monkeypatch.setenv("OUTLOOK_CALENDAR_WRITE_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    with pytest.raises(
        RuntimeError,
        match="Outlook calendar write is disabled by provider feature flags",
    ):
        provider.create_outlook_calendar_event(
            {"source_provider": "outlook", "summary": "Test event"}
        )


# ---------------------------------------------------------------------------
# 9. Outlook calendar write executes with mocked Graph client when enabled
# ---------------------------------------------------------------------------

def test_outlook_calendar_write_executes_with_mock_graph(monkeypatch):
    monkeypatch.setenv("OUTLOOK_CALENDAR_WRITE_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    mock_graph.create_calendar_event.return_value = {
        "status": "created",
        "event_id": "GRAPH-EVT-001",
        "provider": "microsoft_graph",
    }

    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    payload = {
        "source_provider": "outlook",
        "target_provider": "microsoft_graph",
        "summary": "Review meeting",
        "start": "2030-06-01T10:00:00Z",
        "end": "2030-06-01T11:00:00Z",
        "feature_flag": "OUTLOOK_CALENDAR_WRITE_ENABLED",
    }
    result = provider.create_outlook_calendar_event(payload)

    assert result["status"] == "created"
    mock_graph.create_calendar_event.assert_called_once()


# ---------------------------------------------------------------------------
# 10. Outlook mail modify blocks when disabled; seams when enabled
# ---------------------------------------------------------------------------

def test_outlook_mail_modify_blocks_when_disabled(monkeypatch):
    monkeypatch.setenv("OUTLOOK_MAIL_MODIFY_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    with pytest.raises(
        RuntimeError,
        match="Outlook mail modify is disabled by provider feature flags",
    ):
        provider.apply_outlook_mail_modify(
            {"source_message_id": "MSG-001", "operation": "archive"}
        )


def test_outlook_mail_modify_dry_run_when_enabled(monkeypatch):
    monkeypatch.setenv("OUTLOOK_MAIL_MODIFY_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "true")
    get_settings.cache_clear()

    settings = get_settings()
    mock_graph = MagicMock()
    provider = GuardedExternalExecutionProvider(settings, graph_client=mock_graph)

    result = provider.apply_outlook_mail_modify(
        {"source_message_id": "MSG-001", "source_provider": "outlook", "operation": "archive"}
    )

    assert result["status"] == "dry_run"
    mock_graph.archive_message.assert_not_called()
    mock_graph.modify_message.assert_not_called()


# ---------------------------------------------------------------------------
# 11. Provider mismatch is blocked before mutation
# ---------------------------------------------------------------------------

def test_provider_mismatch_outlook_action_gmail_source_is_blocked(db_session: Session, monkeypatch):
    from app.services.execution_service import _execute_with_provider

    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    provider = MockExecutionProvider()
    payload = {
        "source_provider": "gmail",  # mismatch — gmail source with Outlook action
        "target_provider": "microsoft_graph",
        "to": "test@example.com",
    }

    with pytest.raises(ValueError, match="Provider mismatch"):
        _execute_with_provider(
            provider, ExecutionActionType.CREATE_OUTLOOK_DRAFT, payload
        )


def test_provider_mismatch_gmail_action_outlook_source_is_blocked(db_session: Session, monkeypatch):
    from app.services.execution_service import _execute_with_provider

    provider = MockExecutionProvider()
    payload = {
        "source_provider": "outlook",  # mismatch — outlook source with Gmail action
        "target_provider": "gmail",
        "to": "test@example.com",
    }

    with pytest.raises(ValueError, match="Provider mismatch"):
        _execute_with_provider(
            provider, ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT, payload
        )


# ---------------------------------------------------------------------------
# 12. Execution requires approval and final confirmation
# ---------------------------------------------------------------------------

def test_outlook_draft_execution_requires_approval(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="approval-required")
    result = prepare_execution_for_draft(db_session, draft.id)
    record = result.record

    assert record.status == ExecutionStatus.PENDING_REVIEW

    # Confirm must fail before approval
    with pytest.raises(ValueError, match="approved before confirmation"):
        confirm_execution(db_session, record.id)

    # After approval, confirm proceeds
    record = approve_execution(db_session, record.id)
    assert record.status == ExecutionStatus.APPROVED

    record = confirm_execution(db_session, record.id)
    assert record.status == ExecutionStatus.EXECUTED


def test_gmail_draft_execution_requires_approval(db_session: Session, monkeypatch):
    monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
    monkeypatch.setenv("GMAIL_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="gmail", suffix="gmail-approval")
    result = prepare_execution_for_draft(db_session, draft.id)
    record = result.record

    assert record.status == ExecutionStatus.PENDING_REVIEW

    with pytest.raises(ValueError, match="approved before confirmation"):
        confirm_execution(db_session, record.id)

    record = approve_execution(db_session, record.id)
    assert record.status == ExecutionStatus.APPROVED

    record = confirm_execution(db_session, record.id)
    assert record.status == ExecutionStatus.EXECUTED


# ---------------------------------------------------------------------------
# 13. Provider status reports Microsoft write readiness correctly
# ---------------------------------------------------------------------------

def test_provider_status_reports_ms_write_disabled_by_default():
    settings = Settings(
        microsoft_graph_enabled=True,
        microsoft_tenant_id="tenant-001",
        microsoft_client_id="client-001",
        microsoft_graph_auth_mode="delegated",
        outlook_draft_create_enabled=False,
        outlook_send_enabled=False,
        outlook_mail_modify_enabled=False,
        outlook_calendar_write_enabled=False,
    )
    rows = provider_status_rows(settings)
    row_map = {r.key: r for r in rows}

    assert row_map["outlook_draft_create"].state == "disabled"
    assert row_map["outlook_send"].state == "disabled"
    assert row_map["outlook_mail_modify"].state == "disabled"
    assert row_map["outlook_calendar_write"].state == "disabled"


def test_provider_status_reports_ms_write_dry_run_when_enabled():
    settings = Settings(
        microsoft_graph_enabled=True,
        microsoft_tenant_id="tenant-001",
        microsoft_client_id="client-001",
        microsoft_graph_auth_mode="delegated",
        external_write_dry_run=True,
        outlook_draft_create_enabled=True,
        outlook_send_enabled=True,
        outlook_mail_modify_enabled=True,
        outlook_calendar_write_enabled=True,
    )
    rows = provider_status_rows(settings)
    row_map = {r.key: r for r in rows}

    assert row_map["outlook_draft_create"].state == "dry_run"
    assert row_map["outlook_send"].state == "dry_run"
    assert row_map["outlook_mail_modify"].state == "dry_run"
    assert row_map["outlook_calendar_write"].state == "dry_run"


def test_provider_status_reports_ms_write_available_when_live():
    settings = Settings(
        microsoft_graph_enabled=True,
        microsoft_tenant_id="tenant-001",
        microsoft_client_id="client-001",
        microsoft_graph_auth_mode="delegated",
        external_write_dry_run=False,
        outlook_draft_create_enabled=True,
        outlook_send_enabled=True,
        outlook_mail_modify_enabled=True,
        outlook_calendar_write_enabled=True,
    )
    rows = provider_status_rows(settings)
    row_map = {r.key: r for r in rows}

    assert row_map["outlook_draft_create"].state == "available"
    assert row_map["outlook_send"].state == "available"
    assert row_map["outlook_mail_modify"].state == "available"
    assert row_map["outlook_calendar_write"].state == "available"


def test_provider_status_reports_ms_write_misconfigured_when_graph_disabled():
    settings = Settings(
        microsoft_graph_enabled=False,
        outlook_draft_create_enabled=True,
        outlook_send_enabled=True,
    )
    rows = provider_status_rows(settings)
    row_map = {r.key: r for r in rows}

    # Flags enabled but Graph not enabled → misconfigured
    assert row_map["outlook_draft_create"].state == "misconfigured"
    assert row_map["outlook_send"].state == "misconfigured"


def test_microsoft_write_readiness_helper_returns_correct_states(monkeypatch):
    monkeypatch.setenv("MICROSOFT_GRAPH_ENABLED", "true")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant-001")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-001")
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    monkeypatch.setenv("OUTLOOK_SEND_ENABLED", "false")
    monkeypatch.setenv("OUTLOOK_MAIL_MODIFY_ENABLED", "false")
    monkeypatch.setenv("OUTLOOK_CALENDAR_WRITE_ENABLED", "true")
    get_settings.cache_clear()

    readiness = microsoft_write_readiness()

    assert readiness["outlook_draft_create"]["state"] == "available"
    assert readiness["outlook_send"]["state"] == "disabled"
    assert readiness["outlook_mail_modify"]["state"] == "disabled"
    assert readiness["outlook_calendar_write"]["state"] == "available"


# ---------------------------------------------------------------------------
# 14. Route smoke — key routes return 200
# ---------------------------------------------------------------------------

def _client(db: Session):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        yield client
    finally:
        app.dependency_overrides.clear()


def _get(db: Session, path: str):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            return client.get(path)
    finally:
        app.dependency_overrides.clear()


def test_route_smoke_dashboard(db_session: Session):
    assert _get(db_session, "/").status_code == 200


def test_route_smoke_drafts(db_session: Session):
    assert _get(db_session, "/drafts").status_code == 200


def test_route_smoke_review_packages(db_session: Session):
    assert _get(db_session, "/review-packages").status_code == 200


def test_route_smoke_executions(db_session: Session):
    assert _get(db_session, "/executions").status_code == 200


def test_route_smoke_providers(db_session: Session):
    assert _get(db_session, "/providers").status_code == 200


def test_route_smoke_operational_smoke(db_session: Session):
    assert _get(db_session, "/operational-smoke").status_code == 200


def test_route_smoke_admin(db_session: Session):
    assert _get(db_session, "/admin").status_code == 200


def test_route_smoke_about(db_session: Session):
    assert _get(db_session, "/about").status_code == 200


def test_route_smoke_healthz(db_session: Session):
    assert _get(db_session, "/healthz").status_code == 200


# ---------------------------------------------------------------------------
# 15. Providers page contains Microsoft write readiness rows
# ---------------------------------------------------------------------------

def test_providers_page_shows_outlook_write_rows(db_session: Session):
    response = _get(db_session, "/providers")
    assert response.status_code == 200
    assert "outlook_draft_create" in response.text
    assert "outlook_send" in response.text
    assert "outlook_mail_modify" in response.text
    assert "outlook_calendar_write" in response.text


# ---------------------------------------------------------------------------
# 16. Mock provider includes all Outlook methods
# ---------------------------------------------------------------------------

def test_mock_provider_includes_outlook_methods():
    provider = MockExecutionProvider()
    payload = {"source_provider": "outlook", "to": "test@example.com"}

    draft = provider.create_outlook_draft(payload)
    assert draft["status"] == "created"
    assert draft["provider"] == "mock_outlook"

    reply = provider.send_outlook_reply(payload)
    assert reply["status"] == "sent"

    modify = provider.apply_outlook_mail_modify(payload)
    assert modify["status"] == "applied"

    event = provider.create_outlook_calendar_event(payload)
    assert event["status"] == "created"


# ---------------------------------------------------------------------------
# 17. Execution detail route shows provider detail for Outlook records
# ---------------------------------------------------------------------------

def test_execution_detail_shows_provider_detail_for_outlook(db_session: Session, monkeypatch):
    monkeypatch.setenv("OUTLOOK_DRAFT_CREATE_ENABLED", "true")
    get_settings.cache_clear()

    draft = _seed_draft(db_session, source_type="outlook", suffix="detail-test")
    result = prepare_execution_for_draft(db_session, draft.id)
    record = result.record

    response = _get(db_session, f"/executions/{record.id}")
    assert response.status_code == 200
    assert "microsoft_graph" in response.text
    assert "outlook" in response.text
    assert "OUTLOOK_DRAFT_CREATE_ENABLED" in response.text
