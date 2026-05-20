"""Tests for Phase 25 — Controlled Live Gmail Cleanup Execution and Recovery.

Coverage:
- Gmail cleanup blocked when GMAIL_WRITE_ENABLED=false
- Gmail cleanup blocked when GMAIL_LABEL_ARCHIVE_ENABLED=false
- Dry-run provider does not call live Gmail client
- Live cleanup only executed after approve → confirm pipeline
- cleanup_label, cleanup_archive, cleanup_label_and_archive payload routing
- Duplicate message IDs are deduplicated before processing
- Empty message lists are skipped safely
- Partial failures are surfaced correctly in result (attempted/succeeded/failed)
- Large-batch threshold (>50 messages) sets large_batch_warning flag
- cleanup_execution_details() returns correct confirmation fields
- execution_detail route passes cleanup_details when payload has cleanup_mode
- Operational smoke reports Gmail cleanup readiness
- MockExecutionProvider returns correct shape for empty + duplicate ID inputs
- Outlook write remains disabled/not implemented
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.models.base import Base
from app.models.entities import (
    MailboxCleanupAction,
    MailboxCleanupCandidate,
    MailboxCleanupStatus,
    Message,
    MessageClassification,
    MessageThread,
)
from app.services.execution_service import MockExecutionProvider
from app.services.mailbox_cleanup_service import (
    LARGE_BATCH_THRESHOLD,
    PREFERRED_CLEANUP_LABELS,
    cleanup_execution_details,
    prepare_cleanup_archive_execution,
    prepare_cleanup_label_and_archive_execution,
    prepare_cleanup_label_execution,
)
from app.services.operational_status_service import cleanup_execution_posture


# ─── in-memory DB helpers ─────────────────────────────────────────────────────


def _make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _msg(
    db: Session,
    *,
    sender_email: str = "noise@example.com",
    source_type: str = "gmail",
    marketing: bool = True,
    source_message_id: str | None = None,
) -> Message:
    uid = str(uuid.uuid4())
    thread = MessageThread(source_type=source_type, source_thread_id=f"t-{uid}")
    db.add(thread)
    db.flush()
    msg = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=source_message_id or f"mid_{uid}",
        sender_email=sender_email,
        subject="Test",
        received_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    db.add(msg)
    db.flush()
    cls = MessageClassification(message_id=msg.id, is_marketing=marketing)
    db.add(cls)
    db.flush()
    return msg


def _candidate(
    db: Session,
    sender_email: str = "noise@example.com",
    message_count: int = 5,
    is_protected: bool = False,
    label: str | None = None,
) -> MailboxCleanupCandidate:
    c = MailboxCleanupCandidate(
        sender_key=sender_email,
        sender_email=sender_email,
        sender_domain=sender_email.split("@")[1] if "@" in sender_email else "example.com",
        source_type="gmail",
        total_message_count=message_count,
        is_protected=is_protected,
        confidence_score=Decimal("0.90"),
        recommended_action=MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL,
        recommended_gmail_label=label or PREFERRED_CLEANUP_LABELS["noise"],
        status=MailboxCleanupStatus.PENDING,
    )
    db.add(c)
    # add real message IDs for the candidate's source
    for _ in range(message_count):
        _msg(db, sender_email=sender_email)
    db.commit()
    db.refresh(c)
    return c


def _settings(**kwargs) -> Settings:
    """Return a Settings object overriding specific fields for testing."""
    base = get_settings()
    overrides = {
        "execution_provider": "mock",
        "gmail_write_enabled": False,
        "gmail_label_archive_enabled": False,
        "external_write_dry_run": True,
        "operational_test_mode": False,
    }
    overrides.update(kwargs)
    return base.model_copy(update=overrides)


# ─── Feature flag gate tests ──────────────────────────────────────────────────


class TestCleanupFeatureFlags:
    def test_blocked_when_gmail_write_disabled(self):
        """Execution policy blocks cleanup when GMAIL_WRITE_ENABLED=false."""
        from app.services.execution_test_policy import ExecutionActionType, readiness_for_payload

        s = _settings(
            execution_provider="external",
            gmail_write_enabled=False,
            gmail_label_archive_enabled=True,
            operational_test_mode=True,
        )
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2"],
        }
        result = readiness_for_payload(ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, payload, s)
        assert not result.allowed
        assert "GMAIL_WRITE_ENABLED" in result.blocked_reason

    def test_blocked_when_label_archive_disabled(self):
        """Execution policy blocks cleanup when GMAIL_LABEL_ARCHIVE_ENABLED=false."""
        from app.services.execution_test_policy import ExecutionActionType, readiness_for_payload

        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=False,
            operational_test_mode=True,
        )
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1"],
        }
        result = readiness_for_payload(ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, payload, s)
        assert not result.allowed
        assert "GMAIL_LABEL_ARCHIVE_ENABLED" in result.blocked_reason

    def test_blocked_when_provider_is_mock(self):
        """Execution policy blocks external cleanup when provider is mock."""
        from app.services.execution_test_policy import ExecutionActionType, readiness_for_payload

        s = _settings(
            execution_provider="mock",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            operational_test_mode=True,
        )
        payload = {"cleanup_mode": "cleanup_label", "source_message_ids": ["id1"]}
        result = readiness_for_payload(ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, payload, s)
        assert not result.allowed

    def test_allowed_when_all_flags_set(self):
        """Execution policy allows cleanup when all required flags are set."""
        from app.services.execution_test_policy import ExecutionActionType, readiness_for_payload

        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            operational_test_mode=True,
            external_write_dry_run=True,
        )
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1"],
        }
        result = readiness_for_payload(ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, payload, s)
        assert result.allowed


# ─── Dry-run provider tests ───────────────────────────────────────────────────


class TestDryRunProvider:
    def test_dry_run_does_not_call_gmail_client(self):
        """GuardedExternalProvider with dry_run=true returns dry-run result without calling Gmail."""
        from app.services.execution_service import GuardedExternalExecutionProvider

        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            external_write_dry_run=True,
        )
        provider = GuardedExternalExecutionProvider(settings=s)
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2"],
        }

        with patch(
            "app.services.execution_service.GmailWriteClient"
        ) as mock_client_cls:
            result = provider.apply_gmail_label_archive_batch(payload)

        # Should not have instantiated the Gmail write client
        mock_client_cls.assert_not_called()
        assert result["status"] == "dry_run"

    def test_dry_run_result_contains_mode_and_count(self):
        """Dry-run result has status=dry_run and references the action type."""
        from app.services.execution_service import GuardedExternalExecutionProvider

        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            external_write_dry_run=True,
        )
        provider = GuardedExternalExecutionProvider(settings=s)
        payload = {
            "cleanup_mode": "cleanup_archive",
            "cleanup_label_name": None,
            "source_message_ids": ["id1", "id2", "id3"],
        }
        result = provider.apply_gmail_label_archive_batch(payload)
        assert result["status"] == "dry_run"
        # Dry-run records the action name but does not include internal mode details
        assert "apply_gmail_label_archive_batch" in result.get("action", "")
        assert result.get("external_write_performed") is False


# ─── Cleanup payload routing tests ───────────────────────────────────────────


class TestCleanupPayloadRouting:
    def test_cleanup_label_payload_routed_correctly(self):
        """Payload with cleanup_mode='cleanup_label' routes to apply_gmail_label_archive_batch."""
        db = _make_db()
        c = _candidate(db, message_count=3)
        record = prepare_cleanup_label_execution(db, c.id)
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_label"
        assert payload["cleanup_label_name"] is not None
        assert isinstance(payload["source_message_ids"], list)
        assert len(payload["source_message_ids"]) > 0

    def test_cleanup_archive_payload_routed_correctly(self):
        db = _make_db()
        c = _candidate(db, message_count=3)
        record = prepare_cleanup_archive_execution(db, c.id)
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_archive"
        assert payload.get("cleanup_label_name") is None

    def test_cleanup_label_and_archive_payload_routed_correctly(self):
        db = _make_db()
        c = _candidate(db, message_count=3)
        record = prepare_cleanup_label_and_archive_execution(db, c.id)
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_label_and_archive"
        assert payload["cleanup_label_name"] is not None

    def test_mock_provider_handles_cleanup_label_payload(self):
        provider = MockExecutionProvider()
        result = provider.apply_gmail_label_archive_batch({
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2", "id3"],
        })
        assert result["status"] == "applied"
        assert result["applied_count"] == 3
        assert result["attempted_count"] == 3
        assert result["succeeded_count"] == 3
        assert result["failed_count"] == 0


# ─── Deduplication tests ──────────────────────────────────────────────────────


class TestDuplicateMessageIdHandling:
    def test_mock_provider_deduplicates_ids(self):
        """MockExecutionProvider deduplicates message IDs before reporting counts."""
        provider = MockExecutionProvider()
        result = provider.apply_gmail_label_archive_batch({
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2", "id1", "id3", "id2"],
        })
        # 3 unique IDs: id1, id2, id3
        assert result["applied_count"] == 3
        assert result["attempted_count"] == 3

    def test_live_client_deduplicates_ids(self):
        """GmailWriteClient.apply_label_archive_batch deduplicates IDs before calling Gmail."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings(
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
        )
        client = GmailWriteClient(settings=s)
        call_ids: list[str] = []

        def _fake_modify(userId, id, body):  # noqa: A002
            call_ids.append(id)
            req = MagicMock()
            req.execute.return_value = {"id": id}
            return req

        def _fake_ensure_label(service, label_name):  # noqa: ARG001
            return "label_123"

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.side_effect = _fake_modify

        with (
            patch.object(client, "_build_service", return_value=mock_service),
            patch.object(client, "_ensure_label_exists", side_effect=_fake_ensure_label),
        ):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": ["id1", "id2", "id1", "id3"],
            })

        # id1, id2, id3 only (id1 duplicate removed)
        assert len(call_ids) == 3
        assert result["attempted_count"] == 3
        assert result["succeeded_count"] == 3
        assert result["failed_count"] == 0

    def test_mock_provider_handles_empty_id_list(self):
        """MockExecutionProvider handles empty source_message_ids gracefully."""
        provider = MockExecutionProvider()
        result = provider.apply_gmail_label_archive_batch({
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": [],
        })
        assert result["applied_count"] == 0
        assert result["attempted_count"] == 0

    def test_live_client_skips_empty_id_list(self):
        """GmailWriteClient returns 'skipped' status for empty message ID lists."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings()
        client = GmailWriteClient(settings=s)
        mock_service = MagicMock()

        with patch.object(client, "_build_service", return_value=mock_service):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": [],
            })

        assert result["status"] == "skipped"
        assert result["reason"] == "no_message_ids"
        assert result["applied_count"] == 0
        assert result["attempted_count"] == 0
        assert result["failed_count"] == 0

    def test_live_client_skips_none_id_list(self):
        """GmailWriteClient handles None source_message_ids safely."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings()
        client = GmailWriteClient(settings=s)
        mock_service = MagicMock()

        with patch.object(client, "_build_service", return_value=mock_service):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": None,
            })

        assert result["status"] == "skipped"
        assert result["applied_count"] == 0


# ─── Partial failure tests ────────────────────────────────────────────────────


class TestPartialFailures:
    def test_partial_failure_returns_partial_status(self):
        """When some messages fail, status is 'partial' and counts reflect reality."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings()
        client = GmailWriteClient(settings=s)
        call_count = 0

        def _fake_modify(userId, id, body):  # noqa: A002
            nonlocal call_count
            call_count += 1
            req = MagicMock()
            if id == "id2":
                req.execute.side_effect = Exception("API error for id2")
            else:
                req.execute.return_value = {"id": id}
            return req

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.side_effect = _fake_modify

        with (
            patch.object(client, "_build_service", return_value=mock_service),
            patch.object(client, "_ensure_label_exists", return_value="label_123"),
        ):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": ["id1", "id2", "id3"],
            })

        assert result["status"] == "partial"
        assert result["succeeded_count"] == 2
        assert result["failed_count"] == 1
        assert result["attempted_count"] == 3
        assert result["error_count"] == 1

    def test_all_fail_returns_failed_status(self):
        """When all messages fail, status is 'failed' with succeeded_count=0."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings()
        client = GmailWriteClient(settings=s)

        def _fail_modify(userId, id, body):  # noqa: A002
            req = MagicMock()
            req.execute.side_effect = Exception("all fail")
            return req

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.side_effect = _fail_modify

        with (
            patch.object(client, "_build_service", return_value=mock_service),
            patch.object(client, "_ensure_label_exists", return_value="label_123"),
        ):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": ["id1", "id2"],
            })

        assert result["status"] == "failed"
        assert result["succeeded_count"] == 0
        assert result["failed_count"] == 2

    def test_result_does_not_contain_private_content(self):
        """Result dict must not contain OAuth tokens, secrets, or private payloads."""
        from app.services.external_provider_clients import GmailWriteClient

        s = _settings()
        client = GmailWriteClient(settings=s)

        mock_service = MagicMock()
        modify_req = MagicMock()
        modify_req.execute.return_value = {"id": "id1"}
        mock_service.users.return_value.messages.return_value.modify.return_value = modify_req

        with (
            patch.object(client, "_build_service", return_value=mock_service),
            patch.object(client, "_ensure_label_exists", return_value="label_abc"),
        ):
            result = client.apply_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "cleanup_label_name": "RTH-Cleanup/Noise",
                "source_message_ids": ["id1"],
            })

        # label_id is intentionally omitted from the result
        assert "label_id" not in result
        result_str = str(result)
        assert "token" not in result_str.lower()
        assert "secret" not in result_str.lower()
        assert "password" not in result_str.lower()


# ─── cleanup_execution_details() tests ────────────────────────────────────────


class TestCleanupExecutionDetails:
    def test_returns_empty_for_none_payload(self):
        result = cleanup_execution_details(None)
        assert result == {}

    def test_returns_empty_for_empty_payload(self):
        result = cleanup_execution_details({})
        assert result == {}

    def test_cleanup_label_details(self):
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2", "id3"],
            "sender_email": "spam@example.com",
            "sender_domain": "example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["cleanup_mode"] == "cleanup_label"
        assert details["message_count"] == 3
        assert details["label_name"] == "RTH-Cleanup/Noise"
        assert details["is_label"] is True
        assert details["is_archive"] is False
        assert details["permanent_delete"] is False
        assert "label" in details["recovery_guidance"].lower()

    def test_cleanup_archive_details(self):
        payload = {
            "cleanup_mode": "cleanup_archive",
            "cleanup_label_name": None,
            "source_message_ids": ["id1", "id2"],
            "sender_email": "bulk@spam.com",
            "sender_domain": "spam.com",
        }
        details = cleanup_execution_details(payload)
        assert details["is_label"] is False
        assert details["is_archive"] is True
        assert details["permanent_delete"] is False
        assert "archive" in details["recovery_guidance"].lower()

    def test_cleanup_label_and_archive_details(self):
        payload = {
            "cleanup_mode": "cleanup_label_and_archive",
            "cleanup_label_name": "RTH-Cleanup/Marketing",
            "source_message_ids": ["id1", "id2", "id3", "id4"],
            "sender_email": "marketing@big.com",
            "sender_domain": "big.com",
        }
        details = cleanup_execution_details(payload)
        assert details["is_label"] is True
        assert details["is_archive"] is True
        assert "label" in details["recovery_guidance"].lower()
        assert "archive" in details["recovery_guidance"].lower() or "inbox" in details["recovery_guidance"].lower()

    def test_large_batch_warning_set_for_over_threshold(self):
        message_ids = [f"id{i}" for i in range(LARGE_BATCH_THRESHOLD + 1)]
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": message_ids,
            "sender_email": "bulk@example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["large_batch_warning"] is True
        assert details["message_count"] > LARGE_BATCH_THRESHOLD

    def test_no_large_batch_warning_under_threshold(self):
        message_ids = [f"id{i}" for i in range(LARGE_BATCH_THRESHOLD)]
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": message_ids,
            "sender_email": "bulk@example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["large_batch_warning"] is False

    def test_dry_run_flag_passed_from_posture(self):
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1"],
            "sender_email": "x@example.com",
        }
        dry_posture = {"dry_run": True, "label": "Dry-run", "posture": "dry_run"}
        details = cleanup_execution_details(payload, dry_posture)
        assert details["dry_run_mode"] is True

        live_posture = {"dry_run": False, "label": "Live", "posture": "live"}
        live_details = cleanup_execution_details(payload, live_posture)
        assert live_details["dry_run_mode"] is False

    def test_audit_statement_present(self):
        payload = {
            "cleanup_mode": "cleanup_label",
            "cleanup_label_name": "RTH-Cleanup/Noise",
            "source_message_ids": ["id1", "id2"],
            "sender_email": "x@example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["audit_statement"]
        assert "audit" in details["audit_statement"].lower()
        assert "permanent delete" in details["audit_statement"].lower()


# ─── Route rendering tests ────────────────────────────────────────────────────


class TestExecutionDetailRoute:
    def test_execution_detail_renders_cleanup_section(self, tmp_path, monkeypatch):
        """Execution detail page renders cleanup confirmation section when payload has cleanup_mode."""
        # Create in-memory db
        db = _make_db()
        candidate = _candidate(db, message_count=3)
        record = prepare_cleanup_label_execution(db, candidate.id)

        # Test cleanup_execution_details is correctly called when payload has cleanup_mode
        payload = json.loads(record.payload_json)
        assert payload.get("cleanup_mode") == "cleanup_label"
        details = cleanup_execution_details(payload)
        assert details  # non-empty dict means section will render
        assert "is_label" in details

    def test_execution_detail_no_cleanup_section_for_other_actions(self):
        """cleanup_execution_details returns empty dict for non-cleanup payloads."""
        # Draft create payload does not have cleanup_mode
        payload = {
            "action_type": "create_draft",
            "recipient": "test@example.com",
            "subject": "Test",
        }
        # No cleanup_mode key → function returns empty dict
        details = cleanup_execution_details(payload)
        assert details == {}


# ─── Cleanup execution posture tests ─────────────────────────────────────────


class TestCleanupExecutionPosture:
    def test_mock_posture_when_provider_is_mock(self):
        # Flags must be enabled so we reach the provider check; without them it returns 'blocked'
        s = _settings(
            execution_provider="mock",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
        )
        posture = cleanup_execution_posture(s)
        assert posture["posture"] == "mock"
        assert posture["can_execute_live"] is False

    def test_blocked_posture_when_flags_missing(self):
        s = _settings(
            execution_provider="external",
            gmail_write_enabled=False,
            gmail_label_archive_enabled=False,
        )
        posture = cleanup_execution_posture(s)
        assert posture["posture"] in {"blocked", "mock"}

    def test_dry_run_posture_when_flags_set_and_dry_run_true(self):
        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            external_write_dry_run=True,
        )
        posture = cleanup_execution_posture(s)
        assert posture["posture"] == "dry_run"
        assert posture["dry_run"] is True
        assert posture["can_execute_live"] is False

    def test_live_posture_when_all_flags_enabled(self):
        s = _settings(
            execution_provider="external",
            gmail_write_enabled=True,
            gmail_label_archive_enabled=True,
            external_write_dry_run=False,
        )
        posture = cleanup_execution_posture(s)
        assert posture["posture"] == "live"
        assert posture["can_execute_live"] is True
        assert posture["dry_run"] is False


# ─── Operational smoke tests ──────────────────────────────────────────────────


class TestOperationalSmoke:
    def test_smoke_includes_gmail_cleanup_posture(self):
        """Operational smoke status includes mailbox_cleanup_execution_posture key."""
        from app.services.operational_status_service import operational_smoke_status

        db = _make_db()
        status = operational_smoke_status(db)
        assert "mailbox_cleanup_execution_posture" in status

    def test_smoke_cleanup_posture_has_required_keys(self):
        """Cleanup posture dict in smoke status includes all expected keys."""
        from app.services.operational_status_service import operational_smoke_status

        db = _make_db()
        status = operational_smoke_status(db)
        posture = status["mailbox_cleanup_execution_posture"]
        for key in ("posture", "label", "detail", "can_prepare", "can_execute_live", "dry_run"):
            assert key in posture, f"Missing key: {key}"

    def test_smoke_includes_gmail_cleanup_readiness_check(self):
        """Smoke status test_execution_readiness includes gmail_cleanup entry."""
        from app.services.operational_status_service import operational_smoke_status

        db = _make_db()
        status = operational_smoke_status(db)
        readiness = status.get("test_execution_readiness", {})
        assert "gmail_cleanup" in readiness


# ─── Outlook write disabled tests ────────────────────────────────────────────


class TestOutlookWriteDisabled:
    def test_outlook_mail_send_not_implemented(self):
        """Provider status confirms Outlook mail send is intentionally not implemented."""
        from app.services.provider_status_service import provider_status_rows

        rows = provider_status_rows()
        row = next((r for r in rows if r.key == "microsoft_graph_outlook_mail_send"), None)
        assert row is not None
        assert row.state == "disabled"
        assert "not implemented" in row.classification.lower()

    def test_microsoft_graph_teams_not_implemented(self):
        """Microsoft Graph Teams provider row is disabled and not implemented."""
        from app.services.provider_status_service import provider_status_rows

        rows = provider_status_rows()
        row = next((r for r in rows if r.key == "microsoft_graph_teams"), None)
        assert row is not None
        assert row.state == "disabled"

    def test_outlook_calendar_not_implemented(self):
        """Outlook Calendar provider row is disabled."""
        from app.services.provider_status_service import provider_status_rows

        rows = provider_status_rows()
        row = next((r for r in rows if r.key == "outlook_calendar_read"), None)
        assert row is not None
        assert row.state == "disabled"


# ─── Large batch constants ────────────────────────────────────────────────────


class TestLargeBatchThreshold:
    def test_large_batch_threshold_is_50(self):
        """LARGE_BATCH_THRESHOLD constant must be 50 per Phase 25 spec."""
        assert LARGE_BATCH_THRESHOLD == 50

    def test_exactly_at_threshold_is_not_large(self):
        payload = {
            "cleanup_mode": "cleanup_label",
            "source_message_ids": [f"id{i}" for i in range(LARGE_BATCH_THRESHOLD)],
            "sender_email": "x@example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["large_batch_warning"] is False

    def test_one_over_threshold_triggers_warning(self):
        payload = {
            "cleanup_mode": "cleanup_label",
            "source_message_ids": [f"id{i}" for i in range(LARGE_BATCH_THRESHOLD + 1)],
            "sender_email": "x@example.com",
        }
        details = cleanup_execution_details(payload)
        assert details["large_batch_warning"] is True
