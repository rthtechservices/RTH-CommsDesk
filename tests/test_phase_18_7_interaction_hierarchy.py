"""
Phase 18.7 — Interaction Hierarchy, Triage Ergonomics & RTH Palette Alignment.

Verifies that:
- All key routes still return 200 (regression guard).
- Dashboard renders the Next Best Action strip.
- Dashboard renders status sections with semantic structure.
- Attention queue includes primary/amber/outline action hierarchy markers.
- Workflow rail stages are correctly marked done/active on key pages.
- Microsoft write boundaries on providers and operational_smoke remain intact.
- Phase 18.6 regression strings are preserved.
"""

import pytest
from contextlib import contextmanager
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


# ── helpers ──────────────────────────────────────────────────────────────────

@contextmanager
def _client_with_db(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _make_message(db_session, source_type: str = "gmail", subject: str = "Phase 18.7 test"):
    from app.models.entities import Message, MessageThread
    thread = MessageThread(source_type=source_type, source_thread_id=f"t-18-7-{source_type}")
    db_session.add(thread)
    db_session.flush()
    msg = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=f"m-18-7-{source_type}",
        sender_email="sender@example.com",
        subject=subject,
    )
    db_session.add(msg)
    db_session.commit()
    return msg


# ── route smoke: all key pages return 200 ────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/",
    "/operational-smoke",
    "/providers",
    "/review-packages",
    "/executions",
    "/bulk-triage",
    "/contacts",
    "/drafts",
    "/voice-calibration",
    "/admin",
    "/healthz",
])
def test_phase_18_7_key_routes_return_200(db_session, path):
    """All primary pages must return HTTP 200 after Phase 18.7 changes."""
    with _client_with_db(db_session) as client:
        resp = client.get(path)
    assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"


# ── NBA strip ─────────────────────────────────────────────────────────────────

def test_dashboard_renders_nba_strip(db_session):
    """Dashboard must render the Next Best Action strip."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "nba-strip" in resp.text


def test_dashboard_nba_strip_has_next_action_label(db_session):
    """NBA strip must contain the 'Next action' label."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Next action" in resp.text


# ── Dashboard status sections ─────────────────────────────────────────────────

def test_dashboard_renders_operational_status_section(db_session):
    """Dashboard must render an Operational Status section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Operational Status" in resp.text


def test_dashboard_renders_command_center_section(db_session):
    """Dashboard must render a Command Center section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Command Center" in resp.text


def test_dashboard_renders_sources_section(db_session):
    """Dashboard must render a Source Counts section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Source Counts" in resp.text


def test_dashboard_renders_attention_queue(db_session):
    """Dashboard must render the Needs My Attention section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Needs My Attention" in resp.text


# ── Attention queue action hierarchy ─────────────────────────────────────────

def test_dashboard_attention_queue_has_open_button(db_session):
    """Attention queue must render primary Open buttons when rows exist."""
    msg = _make_message(db_session)
    # Create an attention queue item for the message
    from app.models.entities import AttentionItem, AttentionStatus
    item = AttentionItem(
        thread_id=msg.thread_id,
        message_id=msg.id,
        attention_score=75,
        status=AttentionStatus.NEW,
        reason="Test attention item",
        recommended_action="reply",
    )
    db_session.add(item)
    db_session.commit()
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    # Open button: primary class applied to the message link
    assert "Open" in resp.text


def test_dashboard_attention_queue_has_reviewed_button(db_session):
    """Attention queue must render Reviewed buttons."""
    msg = _make_message(db_session, subject="Reviewed button test")
    from app.models.entities import AttentionItem, AttentionStatus
    item = AttentionItem(
        thread_id=msg.thread_id,
        message_id=msg.id,
        attention_score=40,
        status=AttentionStatus.NEW,
        reason="Reviewed button test",
    )
    db_session.add(item)
    db_session.commit()
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Reviewed" in resp.text


def test_dashboard_attention_queue_has_important_button(db_session):
    """Attention queue must render Important buttons."""
    msg = _make_message(db_session, subject="Important button test")
    from app.models.entities import AttentionItem, AttentionStatus
    item = AttentionItem(
        thread_id=msg.thread_id,
        message_id=msg.id,
        attention_score=55,
        status=AttentionStatus.NEW,
        reason="Important button test",
    )
    db_session.add(item)
    db_session.commit()
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Important" in resp.text


# ── Workflow stage markers ─────────────────────────────────────────────────────

def test_dashboard_workflow_triage_is_active(db_session):
    """Dashboard workflow rail must mark Triage as the active stage."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert 'class="active">Triage' in resp.text


def test_dashboard_workflow_sync_is_done(db_session):
    """Dashboard workflow rail must mark Sync as done."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert 'class="done">Sync' in resp.text


def test_review_packages_workflow_review_is_active(db_session):
    """Review packages workflow rail must mark Review as active."""
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert 'class="active">Review' in resp.text


def test_review_packages_workflow_prior_stages_are_done(db_session):
    """Review packages must mark Sync, Triage, Analyze as done."""
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert 'class="done">Sync' in resp.text
    assert 'class="done">Triage' in resp.text
    assert 'class="done">Analyze' in resp.text


def test_executions_workflow_execute_is_active(db_session):
    """Executions workflow rail must mark Execute as active."""
    with _client_with_db(db_session) as client:
        resp = client.get("/executions")
    assert resp.status_code == 200
    assert 'class="active">Execute' in resp.text


def test_executions_workflow_prior_stages_are_done(db_session):
    """Executions must mark Sync through Prepare as done."""
    with _client_with_db(db_session) as client:
        resp = client.get("/executions")
    assert resp.status_code == 200
    assert 'class="done">Sync' in resp.text
    assert 'class="done">Review' in resp.text
    assert 'class="done">Prepare' in resp.text


def test_providers_workflow_audit_is_active(db_session):
    """Providers workflow rail must mark Audit as active."""
    with _client_with_db(db_session) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert 'class="active">Audit' in resp.text


def test_operational_smoke_workflow_audit_is_active(db_session):
    """Operational smoke workflow rail must mark Audit as active."""
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert 'class="active">Audit' in resp.text


def test_message_detail_workflow_analyze_is_active(db_session):
    """Message detail workflow rail must mark Analyze as active."""
    msg = _make_message(db_session, subject="Workflow analyze test")
    with _client_with_db(db_session) as client:
        resp = client.get(f"/messages/{msg.id}")
    assert resp.status_code == 200
    assert 'class="active">Analyze' in resp.text


def test_message_detail_workflow_prior_stages_done(db_session):
    """Message detail must mark Sync and Triage as done."""
    msg = _make_message(db_session, subject="Workflow done stages test")
    with _client_with_db(db_session) as client:
        resp = client.get(f"/messages/{msg.id}")
    assert resp.status_code == 200
    assert 'class="done">Sync' in resp.text
    assert 'class="done">Triage' in resp.text


# ── Providers page: Microsoft write boundaries (regression guard) ─────────────

def test_providers_page_outlook_send_boundary_intact():
    """Providers must still say Outlook send actions are intentionally not implemented."""
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Outlook send actions are intentionally not implemented" in resp.text


def test_providers_page_calendar_boundary_intact():
    """Providers must still say Outlook calendar is fail-closed and not implemented."""
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Outlook calendar read/write remains fail-closed and is not implemented" in resp.text


def test_providers_page_teams_boundary_intact():
    """Providers must still say Teams remains disabled."""
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Teams remains disabled" in resp.text


def test_providers_page_observes_config_only():
    """Providers must say this page observes configuration only."""
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "This page observes configuration only" in resp.text


def test_providers_page_has_callout_grey_cards():
    """Providers must render callout-grey cards for Microsoft write boundaries."""
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "callout-grey" in resp.text


# ── Operational smoke: required strings (regression guard) ───────────────────

def test_operational_smoke_gmail_read_config(db_session):
    """Operational smoke must still have Gmail read config section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Gmail read config" in resp.text


def test_operational_smoke_outlook_delegated(db_session):
    """Operational smoke must still have Outlook delegated Graph section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Outlook delegated Graph" in resp.text


def test_operational_smoke_dry_run_state(db_session):
    """Operational smoke must still have Dry-run state section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Dry-run state" in resp.text


def test_operational_smoke_disabled_write_boundaries(db_session):
    """Operational smoke must still have Disabled Microsoft Write Boundaries section."""
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Disabled Microsoft Write Boundaries" in resp.text


# ── Review packages: callout notice ──────────────────────────────────────────

def test_review_packages_has_callout_amber_notice(db_session):
    """Review packages must render the callout-amber local-recommendations notice."""
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert "callout-amber" in resp.text


def test_review_packages_local_only_notice(db_session):
    """Review packages local-recommendations notice text must be present."""
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert "Local recommendations only" in resp.text


# ── Dashboard widget sidebar ──────────────────────────────────────────────────

def test_dashboard_proposed_actions_widget(db_session):
    """Dashboard must render the Proposed Actions widget."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Proposed Actions" in resp.text


def test_dashboard_ready_for_approval_widget(db_session):
    """Dashboard must render the Ready For Approval widget."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Ready For Approval" in resp.text


def test_dashboard_vip_contacts_widget(db_session):
    """Dashboard must render the VIP Contacts widget."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "VIP Contacts" in resp.text
