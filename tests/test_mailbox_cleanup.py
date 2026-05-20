"""Tests for Phase 23 — Mailbox Cleanup workflow.

Coverage:
- Sender/domain rollup scoring (noise, marketing, newsletter, etc.)
- Protected sender rules (VIP, client, partner, vendor, requires-reply, human-personal)
- Confidence thresholds and action recommendations
- Local actions (mark-noise, mark-protected, mark-delete-candidate)
- Execution record preparation (label, archive, label+archive)
- Feature flag gate — cleanup actions respect GMAIL_WRITE_ENABLED + GMAIL_LABEL_ARCHIVE_ENABLED
- Dry-run and mock provider behaviour
- Cleanup dashboard stats
- Mailbox cleanup routes render
- Dashboard cleanup counts appear
- Outlook write remains disabled
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.main import app
from app.models.base import Base
from app.models.entities import (
    Contact,
    MailboxCleanupAction,
    MailboxCleanupCandidate,
    MailboxCleanupStatus,
    Message,
    MessageClassification,
    MessageThread,
)
from app.services.mailbox_cleanup_service import (
    PREFERRED_CLEANUP_LABELS,
    CleanupDashboardStats,
    action_logs_for_candidate,
    build_cleanup_rollups,
    cleanup_dashboard_stats,
    get_cleanup_candidates,
    mark_delete_candidate_local,
    mark_sender_noise_local,
    mark_sender_not_noise,
    mark_sender_protected,
    prepare_cleanup_archive_execution,
    prepare_cleanup_label_and_archive_execution,
    prepare_cleanup_label_execution,
)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_db():
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
    sender_display_name: str | None = None,
    subject: str | None = "Test subject",
    snippet: str | None = None,
    body_text: str | None = None,
    source_message_id: str | None = None,
    source_type: str = "gmail",
    is_unread: bool = False,
    received_at: datetime | None = None,
    marketing: bool = False,
    newsletter: bool = False,
    group_noise: bool = False,
    system_notification: bool = False,
    requires_reply: bool = False,
    human_personal: bool = False,
) -> Message:
    uid = str(uuid.uuid4())
    thread = MessageThread(source_type=source_type, source_thread_id=f"thread-{uid}")
    db.add(thread)
    db.flush()
    msg = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=source_message_id or f"mid_{uid}",
        sender_email=sender_email,
        sender_display_name=sender_display_name,
        subject=subject,
        snippet=snippet,
        body_text=body_text,
        is_unread=is_unread,
        received_at=received_at or datetime(2025, 1, 1, tzinfo=UTC),
    )
    db.add(msg)
    db.flush()
    cls = MessageClassification(
        message_id=msg.id,
        is_marketing=marketing,
        is_newsletter=newsletter,
        is_group_noise=group_noise,
        is_system_notification=system_notification,
        requires_reply=requires_reply,
        is_human_personal=human_personal,
    )
    db.add(cls)
    db.flush()
    return msg


def _noise_batch(db: Session, sender: str = "noise@example.com", count: int = 5) -> list[Message]:
    msgs = []
    for i in range(count):
        msgs.append(
            _msg(
                db,
                sender_email=sender,
                subject=f"Marketing update #{i}",
                snippet="unsubscribe from our list",
                marketing=True,
            )
        )
    db.commit()
    return msgs


# ─── scoring / rollup tests ───────────────────────────────────────────────────


class TestBuildCleanupRollups:
    def test_creates_candidate_for_noise_sender(self, db_session):
        _noise_batch(db_session, "marketer@spam.com", count=5)
        count = build_cleanup_rollups(db_session)
        assert count >= 1
        candidates = get_cleanup_candidates(db_session, status_filter="all")
        senders = {c.sender_email for c in candidates}
        assert "marketer@spam.com" in senders

    def test_high_confidence_noise_recommends_label_and_archive(self, db_session):
        """Sender with ≥80% noise + unsubscribe language + ≥3 msgs → label_and_archive."""
        for i in range(6):
            _msg(
                db_session,
                sender_email="bulk@newsletter.com",
                subject=f"Newsletter #{i}",
                snippet="unsubscribe | manage preferences",
                newsletter=True,
            )
        db_session.commit()
        build_cleanup_rollups(db_session)
        candidates = get_cleanup_candidates(db_session, status_filter="pending")
        c = next((x for x in candidates if x.sender_email == "bulk@newsletter.com"), None)
        assert c is not None
        assert c.confidence_score >= Decimal("0.80")
        assert c.recommended_action == MailboxCleanupAction.LABEL_AND_ARCHIVE_GMAIL

    def test_low_noise_ratio_recommends_review_only(self, db_session):
        """Mostly normal messages → low confidence, review_only recommendation."""
        for i in range(5):
            _msg(db_session, sender_email="colleague@work.com", subject=f"Meeting note {i}")
        db_session.commit()
        build_cleanup_rollups(db_session)
        candidates = get_cleanup_candidates(db_session, status_filter="all")
        c = next((x for x in candidates if x.sender_email == "colleague@work.com"), None)
        assert c is not None
        assert c.confidence_score <= Decimal("0.20")
        assert c.recommended_action in {
            MailboxCleanupAction.REVIEW_ONLY,
            MailboxCleanupAction.SKIP_PROTECTED_SENDER,
        }

    def test_domain_extracted_correctly(self, db_session):
        _noise_batch(db_session, "user@bigspammer.io")
        build_cleanup_rollups(db_session)
        candidates = get_cleanup_candidates(db_session, status_filter="all")
        c = next((x for x in candidates if x.sender_email == "user@bigspammer.io"), None)
        assert c is not None
        assert c.sender_domain == "bigspammer.io"

    def test_upsert_does_not_duplicate(self, db_session):
        _noise_batch(db_session, "repeat@spam.com", count=3)
        build_cleanup_rollups(db_session)
        _noise_batch(db_session, "repeat@spam.com", count=2)
        build_cleanup_rollups(db_session)
        candidates = [c for c in get_cleanup_candidates(db_session, status_filter="all") if c.sender_email == "repeat@spam.com"]
        assert len(candidates) == 1
        assert candidates[0].total_message_count == 5


# ─── protection rule tests ────────────────────────────────────────────────────


class TestProtectionRules:
    def test_vip_contact_is_protected(self, db_session):
        """VIP contacts must always be protected regardless of noise signals."""
        contact = Contact(
            display_name="VIP Person",
            primary_email="boss@company.com",
            is_vip=True,
            relationship_type="client",
            importance_tier=5,
        )
        db_session.add(contact)
        db_session.commit()
        for i in range(5):
            _msg(
                db_session,
                sender_email="boss@company.com",
                marketing=True,
                snippet="unsubscribe",
            )
        db_session.commit()
        build_cleanup_rollups(db_session)
        c = next(
            (x for x in get_cleanup_candidates(db_session, status_filter="all") if x.sender_email == "boss@company.com"),
            None,
        )
        assert c is not None
        assert c.is_protected is True
        assert c.recommended_action == MailboxCleanupAction.SKIP_PROTECTED_SENDER
        assert c.confidence_score == Decimal("0.0")

    def test_requires_reply_blocks_cleanup(self, db_session):
        """Senders with any requires-reply messages must be protected."""
        for i in range(5):
            _msg(
                db_session,
                sender_email="person@example.com",
                marketing=True,
                requires_reply=(i == 0),  # one message needs reply
            )
        db_session.commit()
        build_cleanup_rollups(db_session)
        c = next(
            (x for x in get_cleanup_candidates(db_session, status_filter="all") if x.sender_email == "person@example.com"),
            None,
        )
        assert c is not None
        assert c.is_protected is True
        assert c.recommended_action == MailboxCleanupAction.SKIP_PROTECTED_SENDER

    def test_human_personal_blocks_cleanup(self, db_session):
        for i in range(5):
            _msg(
                db_session,
                sender_email="friend@personal.com",
                newsletter=(i > 0),
                human_personal=(i == 0),
            )
        db_session.commit()
        build_cleanup_rollups(db_session)
        c = next(
            (x for x in get_cleanup_candidates(db_session, status_filter="all") if x.sender_email == "friend@personal.com"),
            None,
        )
        assert c is not None
        assert c.is_protected is True

    @pytest.mark.parametrize("rel_type", ["client", "partner", "vendor", "employer", "colleague"])
    def test_protected_relationship_types_are_protected(self, db_session, rel_type):
        contact = Contact(
            display_name="Protected Contact",
            primary_email=f"{rel_type}@work.com",
            is_vip=False,
            relationship_type=rel_type,
            importance_tier=2,
        )
        db_session.add(contact)
        db_session.commit()
        for i in range(4):
            _msg(
                db_session,
                sender_email=f"{rel_type}@work.com",
                newsletter=True,
                snippet="unsubscribe",
            )
        db_session.commit()
        build_cleanup_rollups(db_session)
        c = next(
            (x for x in get_cleanup_candidates(db_session, status_filter="all") if x.sender_email == f"{rel_type}@work.com"),
            None,
        )
        assert c is not None
        assert c.is_protected is True, f"Relationship type {rel_type!r} must be protected"


# ─── mark-noise / mark-protected / reset tests ───────────────────────────────


class TestLocalActions:
    def _make_candidate(self, db: Session) -> MailboxCleanupCandidate:
        _noise_batch(db, "noise@example.com", count=4)
        build_cleanup_rollups(db)
        c = next(x for x in get_cleanup_candidates(db, status_filter="pending") if x.sender_email == "noise@example.com")
        return c

    def test_mark_sender_noise_local_sets_approved(self, db_session):
        c = self._make_candidate(db_session)
        updated = mark_sender_noise_local(db_session, c.id, actor="test-user")
        assert updated.status == MailboxCleanupStatus.APPROVED

    def test_mark_sender_protected_sets_protected(self, db_session):
        c = self._make_candidate(db_session)
        updated = mark_sender_protected(db_session, c.id, actor="test-user")
        assert updated.status == MailboxCleanupStatus.PROTECTED
        assert updated.is_protected is True
        assert updated.recommended_action == MailboxCleanupAction.SKIP_PROTECTED_SENDER

    def test_cannot_mark_protected_sender_as_noise(self, db_session):
        c = self._make_candidate(db_session)
        mark_sender_protected(db_session, c.id, actor="test-user")
        db_session.refresh(c)
        with pytest.raises(ValueError):
            mark_sender_noise_local(db_session, c.id, actor="test-user")

    def test_reset_to_pending_works(self, db_session):
        c = self._make_candidate(db_session)
        mark_sender_protected(db_session, c.id, actor="test-user")
        updated = mark_sender_not_noise(db_session, c.id, actor="test-user")
        assert updated.status == MailboxCleanupStatus.PENDING
        assert updated.is_protected is False

    def test_mark_delete_candidate_local_sets_label(self, db_session):
        c = self._make_candidate(db_session)
        updated = mark_delete_candidate_local(db_session, c.id, actor="test-user")
        assert updated.recommended_action == MailboxCleanupAction.PREPARE_DELETE_CANDIDATE
        assert updated.recommended_gmail_label == PREFERRED_CLEANUP_LABELS["delete_candidate"]

    def test_action_log_recorded(self, db_session):
        c = self._make_candidate(db_session)
        mark_sender_noise_local(db_session, c.id, actor="test-user")
        logs = action_logs_for_candidate(db_session, c.id)
        assert len(logs) >= 1
        assert any("mark_sender_noise_local" in log.action for log in logs)


# ─── execution record preparation ────────────────────────────────────────────


class TestExecutionPreparation:
    def _make_candidate_with_messages(self, db: Session) -> MailboxCleanupCandidate:
        for i in range(4):
            _msg(
                db,
                sender_email="bulk@newsletter.com",
                subject=f"Newsletter #{i}",
                snippet="unsubscribe",
                newsletter=True,
            )
        db.commit()
        build_cleanup_rollups(db)
        return next(
            x for x in get_cleanup_candidates(db, status_filter="pending")
            if x.sender_email == "bulk@newsletter.com"
        )

    def test_prepare_label_creates_execution_record(self, db_session):
        c = self._make_candidate_with_messages(db_session)
        record = prepare_cleanup_label_execution(db_session, c.id, actor="test-user")
        assert record is not None
        assert record.id is not None
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_label"
        assert payload["sender_email"] == "bulk@newsletter.com"

    def test_prepare_archive_creates_execution_record(self, db_session):
        c = self._make_candidate_with_messages(db_session)
        record = prepare_cleanup_archive_execution(db_session, c.id, actor="test-user")
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_archive"

    def test_prepare_label_and_archive_creates_execution_record(self, db_session):
        c = self._make_candidate_with_messages(db_session)
        record = prepare_cleanup_label_and_archive_execution(db_session, c.id, actor="test-user")
        payload = json.loads(record.payload_json)
        assert payload["cleanup_mode"] == "cleanup_label_and_archive"
        assert payload.get("cleanup_label_name") is not None

    def test_cannot_prepare_execution_for_protected_sender(self, db_session):
        c = self._make_candidate_with_messages(db_session)
        mark_sender_protected(db_session, c.id, actor="test-user")
        db_session.refresh(c)
        with pytest.raises(ValueError):
            prepare_cleanup_label_execution(db_session, c.id, actor="test-user")

    def test_execution_record_has_pending_review_status(self, db_session):
        from app.models.entities import ExecutionStatus

        c = self._make_candidate_with_messages(db_session)
        record = prepare_cleanup_label_execution(db_session, c.id, actor="test-user")
        assert record.status == ExecutionStatus.PENDING_REVIEW

    def test_prepare_label_sets_candidate_approved(self, db_session):
        c = self._make_candidate_with_messages(db_session)
        prepare_cleanup_label_execution(db_session, c.id, actor="test-user")
        db_session.refresh(c)
        assert c.status == MailboxCleanupStatus.APPROVED


# ─── feature flag gate tests ──────────────────────────────────────────────────


class TestFeatureFlagGates:
    def test_mock_provider_apply_cleanup_batch(self):
        """Mock provider returns dry-run-style result without touching Gmail."""
        from app.services.execution_service import MockExecutionProvider

        provider = MockExecutionProvider()
        result = provider.apply_gmail_label_archive_batch({
            "cleanup_mode": "cleanup_label",
            "sender_email": "noise@example.com",
            "source_message_ids": ["msg1", "msg2"],
            "message_count": 2,
        })
        assert result["status"] == "applied"
        assert result["applied_count"] == 2

    def test_guarded_provider_blocked_when_gmail_write_disabled(self, monkeypatch):
        """GuardedExternalExecutionProvider raises when GMAIL_WRITE_ENABLED=false."""
        from app.services.execution_service import GuardedExternalExecutionProvider

        monkeypatch.setenv("GMAIL_WRITE_ENABLED", "false")
        monkeypatch.setenv("GMAIL_LABEL_ARCHIVE_ENABLED", "true")
        get_settings.cache_clear()
        provider = GuardedExternalExecutionProvider(settings=get_settings())
        with pytest.raises((PermissionError, RuntimeError)):
            provider.apply_gmail_label_archive_batch({
                "cleanup_mode": "cleanup_label",
                "source_message_ids": [],
                "message_count": 0,
            })
        get_settings.cache_clear()

    def test_guarded_provider_blocked_when_label_archive_disabled(self, monkeypatch):
        from app.services.execution_service import GuardedExternalExecutionProvider

        monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
        monkeypatch.setenv("GMAIL_LABEL_ARCHIVE_ENABLED", "false")
        get_settings.cache_clear()
        provider = GuardedExternalExecutionProvider(settings=get_settings())
        with pytest.raises((PermissionError, RuntimeError)):
            provider.apply_gmail_label_archive_batch({
                "cleanup_mode": "cleanup_archive",
                "source_message_ids": [],
                "message_count": 0,
            })
        get_settings.cache_clear()

    def test_guarded_provider_dry_run_mode_does_not_call_gmail(self, monkeypatch):
        from app.services.execution_service import GuardedExternalExecutionProvider

        monkeypatch.setenv("GMAIL_WRITE_ENABLED", "true")
        monkeypatch.setenv("GMAIL_LABEL_ARCHIVE_ENABLED", "true")
        monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "true")
        get_settings.cache_clear()
        provider = GuardedExternalExecutionProvider(settings=get_settings())
        result = provider.apply_gmail_label_archive_batch({
            "cleanup_mode": "cleanup_label",
            "source_message_ids": ["id1"],
            "message_count": 1,
        })
        assert result.get("status") == "dry_run" or result.get("dry_run") is True
        get_settings.cache_clear()


# ─── execute_with_provider routing tests ─────────────────────────────────────


class TestExecuteWithProviderRouting:
    def test_cleanup_mode_routes_to_batch_method(self, monkeypatch):
        """_execute_with_provider must call apply_gmail_label_archive_batch for cleanup payloads."""
        from app.models.entities import ExecutionActionType
        from app.services.execution_service import MockExecutionProvider, _execute_with_provider

        provider = MockExecutionProvider()
        calls = []
        original = provider.apply_gmail_label_archive_batch

        def spy(payload):
            calls.append(payload)
            return original(payload)

        monkeypatch.setattr(provider, "apply_gmail_label_archive_batch", spy)
        _execute_with_provider(
            provider,
            ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE,
            {"cleanup_mode": "cleanup_label", "source_message_ids": [], "message_count": 0},
        )
        assert len(calls) == 1

    def test_non_cleanup_payload_routes_to_single_method(self, monkeypatch):
        from app.models.entities import ExecutionActionType
        from app.services.execution_service import MockExecutionProvider, _execute_with_provider

        provider = MockExecutionProvider()
        calls = []
        original = provider.apply_gmail_label_archive

        def spy(payload):
            calls.append(payload)
            return original(payload)

        monkeypatch.setattr(provider, "apply_gmail_label_archive", spy)
        _execute_with_provider(
            provider,
            ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE,
            {"message_id": "id1", "label": "SomeLabel"},
        )
        assert len(calls) == 1


# ─── dashboard stats ──────────────────────────────────────────────────────────


class TestCleanupDashboardStats:
    def test_empty_db_returns_zeros(self, db_session):
        stats = cleanup_dashboard_stats(db_session)
        assert isinstance(stats, CleanupDashboardStats)
        assert stats.total_candidates == 0
        assert stats.high_confidence_count == 0
        assert stats.protected_count == 0
        assert stats.pending_execution_count == 0

    def test_counts_after_rollup(self, db_session):
        _noise_batch(db_session, "spam@example.com", count=6)
        build_cleanup_rollups(db_session)
        stats = cleanup_dashboard_stats(db_session)
        assert stats.total_candidates >= 1

    def test_protected_count_increments(self, db_session):
        _noise_batch(db_session, "safe@example.com", count=4)
        build_cleanup_rollups(db_session)
        c = next(x for x in get_cleanup_candidates(db_session, status_filter="pending") if x.sender_email == "safe@example.com")
        mark_sender_protected(db_session, c.id, actor="test-user")
        stats = cleanup_dashboard_stats(db_session)
        assert stats.protected_count >= 1


# ─── web route smoke tests ────────────────────────────────────────────────────


def _test_client():
    get_settings.cache_clear()
    return TestClient(app, raise_server_exceptions=True)


class TestMailboxCleanupRoutes:
    def test_mailbox_cleanup_index_renders(self):
        client = _test_client()
        r = client.get("/bulk-triage/mailbox-cleanup")
        assert r.status_code == 200
        assert b"Mailbox Cleanup" in r.content

    def test_mailbox_cleanup_pending_filter(self):
        client = _test_client()
        r = client.get("/bulk-triage/mailbox-cleanup?status_filter=pending")
        assert r.status_code == 200

    def test_mailbox_cleanup_all_filter(self):
        client = _test_client()
        r = client.get("/bulk-triage/mailbox-cleanup?status_filter=all")
        assert r.status_code == 200

    def test_mailbox_cleanup_refresh_redirects(self):
        client = _test_client()
        r = client.post("/bulk-triage/mailbox-cleanup/refresh", follow_redirects=False)
        assert r.status_code == 303
        assert "/bulk-triage/mailbox-cleanup" in r.headers["location"]

    def test_mailbox_cleanup_detail_404_redirects(self):
        client = _test_client()
        r = client.get("/bulk-triage/mailbox-cleanup/99999", follow_redirects=False)
        assert r.status_code == 303

    def test_bulk_triage_page_has_cleanup_link(self):
        client = _test_client()
        r = client.get("/bulk-triage")
        assert r.status_code == 200
        assert b"mailbox-cleanup" in r.content.lower()

    def test_dashboard_renders_with_cleanup_stats(self):
        client = _test_client()
        r = client.get("/")
        assert r.status_code == 200
        assert b"Mailbox Cleanup" in r.content or b"mailbox-cleanup" in r.content.lower()


# ─── Outlook write remains disabled ──────────────────────────────────────────


class TestOutlookWriteDisabled:
    def test_microsoft_graph_token_not_used_for_write(self, monkeypatch):
        """Confirm no Outlook send/write endpoint exists."""
        from app.main import app as fastapi_app

        routes = [r.path for r in fastapi_app.routes]
        outlook_write_routes = [
            r for r in routes
            if "outlook" in r.lower() and any(w in r.lower() for w in ["send", "write", "archive", "label", "move"])
        ]
        assert len(outlook_write_routes) == 0, f"Unexpected Outlook write routes: {outlook_write_routes}"

    def test_cleanup_page_has_outlook_planning_note(self):
        client = _test_client()
        r = client.get("/bulk-triage/mailbox-cleanup")
        assert r.status_code == 200
        assert b"Outlook" in r.content
        # Must say planning only, not implemented
        assert b"Planning Only" in r.content or b"planning only" in r.content.lower()
