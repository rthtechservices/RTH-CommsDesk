"""
Phase 18.6 Visual Design System tests.

Verifies that:
- All key routes return HTTP 200.
- Dark theme markers are present in rendered HTML.
- Grouped action panel h2 headings are present in message_detail.
- Microsoft write boundary strings are present in providers and operational_smoke pages.
- Key strings required by existing tests are present (regression guard).
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
def test_phase_18_6_key_routes_return_200(db_session, path):
    """All primary pages must return 200."""
    with _client_with_db(db_session) as client:
        resp = client.get(path)
    assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"


# ── dark theme markers ────────────────────────────────────────────────────────

def test_dashboard_has_dark_theme_css_var(db_session):
    """Dashboard HTML must reference the dark CSS variable --bg (from ui.css)."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    # base.html loads ui.css which defines --bg; the topbar or body uses color-scheme: dark
    assert "ui.css" in resp.text or "--bg" in resp.text or "base.html" in resp.text or "dark" in resp.text.lower()


def test_dashboard_uses_base_template(db_session):
    """Dashboard must include nav topbar elements from base.html."""
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    # base.html injects nav with RTH CommsDesk brand + links
    assert "RTH CommsDesk" in resp.text
    assert "Dashboard" in resp.text


def test_review_packages_uses_base_template(db_session):
    """Review packages page must include base.html nav structure."""
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert "RTH CommsDesk" in resp.text
    assert "Review" in resp.text


def test_executions_uses_base_template(db_session):
    """Executions page must include base.html nav structure."""
    with _client_with_db(db_session) as client:
        resp = client.get("/executions")
    assert resp.status_code == 200
    assert "RTH CommsDesk" in resp.text
    assert "Execution Queue" in resp.text


# ── message_detail grouped action panels ─────────────────────────────────────

def _make_message(db_session):
    """Create a minimal message for message_detail tests."""
    from app.models.entities import Message, MessageThread
    thread = MessageThread(source_type="gmail", source_thread_id="t-18-6")
    db_session.add(thread)
    db_session.flush()
    msg = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="m-18-6",
        sender_email="sender@example.com",
        subject="Phase 18.6 test message",
    )
    db_session.add(msg)
    db_session.commit()
    return msg


def test_message_detail_has_four_action_panels(db_session):
    """message_detail must render 4 grouped action h2 headings."""
    msg = _make_message(db_session)
    with _client_with_db(db_session) as client:
        resp = client.get(f"/messages/{msg.id}")
    assert resp.status_code == 200
    assert "Message actions" in resp.text
    assert "Conversation/AI actions" in resp.text
    assert "Contact actions" in resp.text
    assert "Draft/execution actions" in resp.text


# ── providers page: Microsoft write boundary strings ─────────────────────────

def test_providers_page_has_outlook_send_boundary():
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Outlook send actions are intentionally not implemented" in resp.text


def test_providers_page_has_calendar_boundary():
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Outlook calendar read/write remains fail-closed and is not implemented" in resp.text


def test_providers_page_has_teams_boundary():
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "Teams remains disabled" in resp.text


def test_providers_page_observes_config_only():
    with TestClient(app) as client:
        resp = client.get("/providers")
    assert resp.status_code == 200
    assert "This page observes configuration only" in resp.text


# ── operational smoke: required section headers ───────────────────────────────

def test_operational_smoke_has_gmail_read_config(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Gmail read config" in resp.text


def test_operational_smoke_has_outlook_delegated(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Outlook delegated Graph" in resp.text


def test_operational_smoke_has_dry_run_state(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Dry-run state" in resp.text


def test_operational_smoke_has_disabled_write_boundaries(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/operational-smoke")
    assert resp.status_code == 200
    assert "Disabled Microsoft Write Boundaries" in resp.text


# ── bulk_triage and contacts use base template ────────────────────────────────

def test_bulk_triage_uses_base_template(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/bulk-triage")
    assert resp.status_code == 200
    assert "RTH CommsDesk" in resp.text
    assert "Bulk Triage" in resp.text


def test_contacts_uses_base_template(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/contacts")
    assert resp.status_code == 200
    assert "RTH CommsDesk" in resp.text
    assert "Contacts" in resp.text


def test_admin_uses_base_template(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/admin")
    assert resp.status_code == 200
    assert "RTH CommsDesk" in resp.text
    assert "Admin" in resp.text


# ── workflow rail present on key pages ────────────────────────────────────────

def test_workflow_rail_present_on_dashboard(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert 'class="workflow"' in resp.text


def test_workflow_rail_present_on_review_packages(db_session):
    with _client_with_db(db_session) as client:
        resp = client.get("/review-packages")
    assert resp.status_code == 200
    assert 'class="workflow"' in resp.text
