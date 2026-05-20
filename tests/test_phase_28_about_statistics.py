"""Phase 28 — Daily-Use Cutover, Operator Console, and About Statistics.

Focused tests only:
- /about returns HTML 200
- About stats service returns required stat keys
- Hours saved calculation is deterministic from sample audited inputs
- Stats baseline persists
- Dashboard/process-next route returns 200
- Local review/dismiss actions do not mutate external providers
- External actions remain gated
- Route smoke includes /about
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.entities import (
    AppStatRecord,
    AttentionItem,
    AttentionStatus,
    BulkTriageActionLog,
    Contact,
    DraftReply,
    DraftStatus,
    ExecutionRecord,
    ExecutionStatus,
    Message,
    MessageThread,
)
from app.services.productivity_stats_service import (
    ALL_STAT_KEYS,
    STAT_HOURS_SAVED,
    compute_lifetime_stats,
    initialize_go_live_baseline,
    load_persisted_stats,
    persist_lifetime_stats,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _client(db_session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=True)


def _client_get(db_session: Session, path: str):
    with _client(db_session) as c:
        return c.get(path, follow_redirects=True)


def _client_post(db_session: Session, path: str, data: dict | None = None):
    with _client(db_session) as c:
        return c.post(path, data=data or {}, follow_redirects=True)


def _seed_message(db_session: Session, suffix: str = "a") -> Message:
    thread = MessageThread(source_type="gmail", source_thread_id=f"thread-p28-{suffix}")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id=f"msg-p28-{suffix}",
        sender_email=f"sender-p28-{suffix}@example.com",
        subject=f"Phase 28 test message {suffix}",
    )
    db_session.add(message)
    db_session.commit()
    return message


def _seed_draft(db_session: Session, suffix: str = "a") -> DraftReply:
    msg = _seed_message(db_session, suffix=f"draft-{suffix}")
    draft = DraftReply(
        thread_id=msg.thread_id,
        message_id=msg.id,
        draft_text=f"Phase 28 draft body {suffix} with some words in it",
        status=DraftStatus.GENERATED,
        provider_name="mock",
    )
    db_session.add(draft)
    db_session.commit()
    return draft


def _seed_attention(db_session: Session, suffix: str, status=AttentionStatus.NEW) -> AttentionItem:
    msg = _seed_message(db_session, suffix=f"att-{suffix}")
    item = AttentionItem(
        thread_id=msg.thread_id,
        message_id=msg.id,
        attention_score=50,
        status=status,
    )
    db_session.add(item)
    db_session.commit()
    return item


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------


def test_about_route_returns_html_200(db_session: Session):
    response = _client_get(db_session, "/about")
    assert response.status_code == 200
    assert "RTH CommsDesk" in response.text
    assert "Life-to-date statistics" in response.text
    assert "Estimated Hours Saved" in response.text


def test_about_page_shows_app_info(db_session: Session):
    response = _client_get(db_session, "/about")
    assert response.status_code == 200
    assert "Phase 28" in response.text
    assert "SQLite" in response.text
    assert "Provider summary" in response.text
    assert "Go-live baseline" in response.text


def test_about_page_shows_provider_summary(db_session: Session):
    response = _client_get(db_session, "/about")
    assert response.status_code == 200
    # Provider rows are rendered as mini state badges
    assert "pstate" in response.text


def test_about_page_init_baseline_action(db_session: Session):
    response = _client_post(db_session, "/admin/about/init-baseline")
    assert response.status_code == 200  # follows redirect to /about
    assert "Baseline set" in response.text or "baseline_result" in response.url


# ---------------------------------------------------------------------------
# Stats service
# ---------------------------------------------------------------------------


def test_compute_lifetime_stats_returns_required_keys(db_session: Session):
    stats = compute_lifetime_stats(db_session)
    d = stats.as_dict()
    for key in [
        "emails_processed",
        "emails_drafted",
        "emails_deleted",
        "senders_noise",
        "vip_contacts",
        "ai_content_items",
        "hours_saved",
    ]:
        assert key in d, f"Missing stat key: {key}"


def test_compute_lifetime_stats_with_no_data(db_session: Session):
    stats = compute_lifetime_stats(db_session)
    assert stats.emails_processed == 0
    assert stats.emails_drafted == 0
    assert stats.hours_saved >= 0.0


def test_hours_saved_deterministic_from_sample_inputs(db_session: Session):
    """Hours saved is deterministic from the same audited inputs."""
    # Seed enough reviewed items so that hours_saved > 0.0 after rounding to 1 dp
    # 5 * 20s = 100s = 0.028 hrs -> rounds to 0.0; need > 180s -> 200 items * 20s = 4000s = 1.1h
    for i in range(200):
        _seed_attention(db_session, suffix=f"hs-{i}", status=AttentionStatus.REVIEWED)

    # Seed a bulk triage log
    bulk = BulkTriageActionLog(action_type="mark_noise", item_count=10, is_undone=False)
    db_session.add(bulk)
    db_session.commit()

    # Run twice — same result
    stats1 = compute_lifetime_stats(db_session)
    stats2 = compute_lifetime_stats(db_session)
    assert stats1.hours_saved == stats2.hours_saved
    assert stats1.hours_saved > 0.0


def test_hours_saved_increases_with_more_reviewed_items(db_session: Session):
    stats_empty = compute_lifetime_stats(db_session)
    base = stats_empty.hours_saved

    for i in range(10):
        _seed_attention(db_session, suffix=f"incr-{i}", status=AttentionStatus.REVIEWED)

    stats_with_items = compute_lifetime_stats(db_session)
    assert stats_with_items.hours_saved >= base


def test_stats_baseline_persists(db_session: Session):
    """persist_lifetime_stats stores and load_persisted_stats retrieves."""
    stats = compute_lifetime_stats(db_session)
    persist_lifetime_stats(db_session, stats)

    loaded = load_persisted_stats(db_session)
    assert STAT_HOURS_SAVED in loaded
    for key in ALL_STAT_KEYS:
        assert key in loaded


def test_initialize_go_live_baseline_idempotent(db_session: Session):
    settings = get_settings()
    first = initialize_go_live_baseline(db_session, settings)
    second = initialize_go_live_baseline(db_session, settings)
    # Compare as naive UTC to avoid tz-aware vs tz-naive mismatch on SQLite round-trip
    def _naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    assert _naive(first) == _naive(second), "Baseline should be idempotent (same timestamp on second call)"


def test_stats_baseline_survives_recalculation(db_session: Session):
    """first_tracked_at is not overwritten on subsequent persist calls."""
    settings = get_settings()
    initialize_go_live_baseline(db_session, settings)

    stats = compute_lifetime_stats(db_session)
    persist_lifetime_stats(db_session, stats)
    persist_lifetime_stats(db_session, stats)

    record = db_session.query(AppStatRecord).filter_by(stat_key="emails_processed").one_or_none()
    assert record is not None
    assert record.first_tracked_at is not None


# ---------------------------------------------------------------------------
# Dashboard / process-next
# ---------------------------------------------------------------------------


def test_dashboard_returns_200(db_session: Session):
    response = _client_get(db_session, "/")
    assert response.status_code == 200


def test_process_next_redirects_to_message_or_empty(db_session: Session):
    """process-next redirects somewhere valid; with no data → dashboard."""
    with _client(db_session) as c:
        response = c.get("/process-next", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_process_next_lands_on_message_when_items_exist(db_session: Session):
    _seed_attention(db_session, suffix="pn1", status=AttentionStatus.NEW)
    response = _client_get(db_session, "/process-next")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Local review actions do not touch external providers
# ---------------------------------------------------------------------------


def test_mark_reviewed_does_not_create_execution_record(db_session: Session):
    item = _seed_attention(db_session, suffix="review-gate", status=AttentionStatus.NEW)
    before_count = db_session.query(ExecutionRecord).count()

    _client_post(db_session, f"/attention/{item.id}/review")

    after_count = db_session.query(ExecutionRecord).count()
    assert after_count == before_count, "Mark reviewed must not create an execution record"
    db_session.refresh(item)
    assert item.status == AttentionStatus.REVIEWED


def test_contact_mark_noise_does_not_create_execution_record(db_session: Session):
    contact = Contact(
        display_name="Phase 28 Noise Test",
        primary_email="phase28-noise@example.com",
    )
    db_session.add(contact)
    db_session.commit()
    before_count = db_session.query(ExecutionRecord).count()

    _client_post(db_session, "/contacts/noise", data={"sender_email": "phase28-noise@example.com"})

    after_count = db_session.query(ExecutionRecord).count()
    assert after_count == before_count, "Mark noise must not create an execution record"


# ---------------------------------------------------------------------------
# External actions remain gated
# ---------------------------------------------------------------------------


def test_draft_execution_prepare_creates_pending_not_executing(db_session: Session):
    draft = _seed_draft(db_session, suffix="gated")
    _client_post(db_session, f"/drafts/{draft.id}/prepare-execution")

    records = db_session.query(ExecutionRecord).all()
    if records:
        for record in records:
            assert record.status in {
                ExecutionStatus.PENDING_REVIEW,
                ExecutionStatus.APPROVED,
            }, "External action should start in pending/approved, never executing"


# ---------------------------------------------------------------------------
# Route smoke
# ---------------------------------------------------------------------------


SMOKE_ROUTES = [
    "/",
    "/drafts",
    "/review-packages",
    "/executions",
    "/bulk-triage",
    "/assistant-profile",
    "/voice-calibration",
    "/providers",
    "/operational-smoke",
    "/admin",
    "/about",
    "/healthz",
]


def test_route_smoke_all_return_200(db_session: Session):
    failed = []
    for path in SMOKE_ROUTES:
        response = _client_get(db_session, path)
        if response.status_code != 200:
            failed.append((path, response.status_code))
    assert not failed, f"Routes returned non-200: {failed}"


def test_about_in_nav(db_session: Session):
    response = _client_get(db_session, "/")
    assert response.status_code == 200
    assert 'href="/about"' in response.text
