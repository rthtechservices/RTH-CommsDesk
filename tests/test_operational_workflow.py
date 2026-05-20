from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.entities import (
    AttentionItem,
    Contact,
    ConversationSummary,
    ExecutionActionType,
    ExecutionRecord,
    ExecutionStatus,
    Message,
    MessageClassification,
    MessageThread,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
)
from app.services.attention_service import build_attention_queue
from app.services.operational_status_service import operational_smoke_status


def test_dashboard_renders_operational_smoke_statuses(db_session):
    _message_with_attention(db_session, source_type="gmail", source_id="dash-gmail", score=66)
    _message_with_attention(db_session, source_type="outlook", source_id="dash-outlook", score=55)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Operational Status" in response.text
    assert "Command Center State" in response.text
    assert "status-dot" in response.text
    assert "Operational Smoke" in response.text
    assert "Gmail read config" in response.text
    assert "Outlook delegated Graph" in response.text
    assert "Outlook sync" in response.text
    assert "Azure/OpenAI analysis" in response.text
    assert "External dry-run" in response.text
    assert "Source Counts" in response.text
    assert "Process next" in response.text
    assert "Sync Teams" not in response.text


def test_operational_smoke_reports_disabled_microsoft_write_boundaries(db_session):
    status = operational_smoke_status(db_session)
    disabled = {row.key: row.state for row in status["disabled_boundaries"]}

    assert disabled["microsoft_graph_outlook_mail_send"] == "disabled"
    assert disabled["outlook_calendar_read"] == "disabled"
    assert disabled["microsoft_graph_teams"] == "disabled"
    assert status["external_write_dry_run"] is True
    assert status["google_calendar_write_enabled"] is False
    assert status["gmail_write_flags"]["GMAIL_SEND_ENABLED"] is False


def test_notification_source_filter_groups_notification_derived_items(db_session):
    _, gmail_item = _message_with_attention(
        db_session, source_type="gmail", source_id="filter-gmail", score=80
    )
    _, notification_item = _message_with_attention(
        db_session,
        source_type="notification_whatsapp",
        source_id="filter-notification",
        score=70,
    )
    db_session.commit()

    notification_queue = build_attention_queue(db_session, source="notification")
    gmail_queue = build_attention_queue(db_session, source="gmail")

    assert [item.id for item in notification_queue] == [notification_item.id]
    assert [item.id for item in gmail_queue] == [gmail_item.id]


def test_process_next_routes_redirect_to_next_pending_work(db_session):
    message, _ = _message_with_attention(
        db_session, source_type="outlook", source_id="next-outlook", score=88
    )
    package = _review_package(db_session, message)
    execution = ExecutionRecord(
        review_package_id=package.id,
        action_type=ExecutionActionType.SEND_GMAIL_REPLY,
        attempt_number=1,
        status=ExecutionStatus.PENDING_REVIEW,
        payload_json="{}",
        provider_name="mock",
    )
    db_session.add(execution)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            attention_response = client.get(
                "/process-next?source=outlook", follow_redirects=False
            )
            package_response = client.get("/review-packages/next", follow_redirects=False)
            execution_response = client.get("/executions/next", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert attention_response.status_code == 303
    assert attention_response.headers["location"].endswith(f"/messages/{message.id}")
    assert package_response.status_code == 303
    assert package_response.headers["location"].endswith(f"/review-packages/{package.id}")
    assert execution_response.status_code == 303
    assert execution_response.headers["location"].endswith(f"/executions/{execution.id}")


def test_operational_smoke_route_exposes_key_status_without_microsoft_writes(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/operational-smoke")
            provider_response = client.get("/api/providers/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Gmail read config" in response.text
    assert "Outlook delegated Graph" in response.text
    assert "Dry-run state" in response.text
    assert "Disabled Microsoft Write Boundaries" in response.text
    assert "Phase 19 Test Execution Readiness" in response.text
    assert "Operational test mode" in response.text
    assert "Test email allowlist" in response.text
    assert "Gmail draft test execution" in response.text
    assert "Gmail send test execution" in response.text
    assert "Google Calendar test execution" in response.text
    assert "Gmail cleanup test execution" in response.text
    assert "Mailbox cleanup readiness" in response.text
    provider_status = provider_response.json()
    assert provider_status["microsoft_graph_outlook_mail_send"]["state"] == "disabled"
    assert provider_status["outlook_calendar_read"]["state"] == "disabled"
    assert provider_status["microsoft_graph_teams"]["state"] == "disabled"


def test_provider_status_page_keeps_microsoft_write_boundaries_not_implemented():
    with TestClient(app) as client:
        response = client.get("/providers")

    assert response.status_code == 200
    assert "Outlook send actions are intentionally not implemented" in response.text
    assert "Outlook calendar read/write remains fail-closed and is not implemented" in response.text
    assert "Teams remains disabled" in response.text
    assert "This page observes configuration only" in response.text


def test_message_detail_groups_actions_and_contains_timeline_inside_main_column(db_session):
    message, _ = _message_with_attention(
        db_session, source_type="gmail", source_id="detail-layout", score=77
    )
    message.body_text = "Long local body " * 80
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/messages/{message.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Conversation Timeline" in response.text
    assert "timeline-body" in response.text
    assert "main-column" in response.text
    assert "Message actions" in response.text
    assert "Conversation/AI actions" in response.text
    assert "Contact actions" in response.text
    assert "Draft/execution actions" in response.text
    assert "What this page is for" in response.text


def test_message_detail_hides_redundant_contact_actions_for_vip_contact(db_session):
    contact = Contact(
        display_name="VIP Sender",
        primary_email="vip-sender@example.com",
        relationship_type="client",
        importance_tier=4,
        is_vip=True,
        is_noise=False,
    )
    db_session.add(contact)
    db_session.flush()
    message, _ = _message_with_attention(
        db_session,
        source_type="gmail",
        source_id="vip-sender",
        score=84,
        contact_id=contact.id,
    )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/messages/{message.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Mark Contact VIP" not in response.text
    assert "Reset contact normal" in response.text
    assert "Mark Sender as Noise" in response.text
    assert "VIP" in response.text


def test_message_detail_hides_noise_action_for_noise_contact(db_session):
    contact = Contact(
        display_name="Noise Sender",
        primary_email="noise-sender@example.com",
        relationship_type="newsletter",
        importance_tier=0,
        is_vip=False,
        is_noise=True,
    )
    db_session.add(contact)
    db_session.flush()
    message, _ = _message_with_attention(
        db_session,
        source_type="gmail",
        source_id="noise-sender",
        score=20,
        contact_id=contact.id,
    )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/messages/{message.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Mark Sender as Noise" not in response.text
    assert "Reset contact normal" in response.text
    assert "Noise" in response.text


def test_review_and_execution_pages_render_workflow_help():
    with TestClient(app) as client:
        review_response = client.get("/review-packages")
        execution_response = client.get("/executions")

    assert review_response.status_code == 200
    assert 'class="done">Sync</span><span class="done">Triage</span><span class="done">Analyze</span><span class="active">Review' in review_response.text
    assert "What this page is for" in review_response.text
    assert execution_response.status_code == 200
    assert '<span class="active">Execute</span><span>Audit</span>' in execution_response.text
    assert "What this page is for" in execution_response.text


def test_execution_detail_renders_test_execution_readiness_panel(db_session):
    message, _ = _message_with_attention(
        db_session, source_type="gmail", source_id="exec-readiness", score=77
    )
    execution = ExecutionRecord(
        action_type=ExecutionActionType.SEND_GMAIL_REPLY,
        attempt_number=1,
        status=ExecutionStatus.PENDING_REVIEW,
        payload_json=f'{{"to":"{message.sender_email}"}}',
        provider_name="mock",
    )
    db_session.add(execution)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/executions/{execution.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Test Execution Readiness" in response.text
    assert "Blocked: operational test mode disabled" in response.text


def test_dashboard_renders_test_execution_blocker_next_best_action(db_session):
    message, _ = _message_with_attention(
        db_session, source_type="gmail", source_id="dash-exec-blocker", score=77
    )
    execution = ExecutionRecord(
        action_type=ExecutionActionType.SEND_GMAIL_REPLY,
        attempt_number=1,
        status=ExecutionStatus.PENDING_REVIEW,
        payload_json=f'{{"to":"{message.sender_email}"}}',
        provider_name="mock",
    )
    db_session.add(execution)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Phase 19 test execution blocked" in response.text
    assert "Blocked: operational test mode disabled" in response.text


def _message_with_attention(
    db_session,
    *,
    source_type: str,
    source_id: str,
    score: int,
    contact_id: int | None = None,
) -> tuple[Message, AttentionItem]:
    thread = MessageThread(
        source_type=source_type,
        source_thread_id=f"thread-{source_id}",
        contact_id=contact_id,
        unread_count=1,
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=f"message-{source_id}",
        sender_email=f"{source_id}@example.com",
        sender_display_name="Operator Test",
        source_channel="email",
        source_confidence=Decimal("0.950"),
        received_at=datetime.now(UTC),
        subject=f"Operational {source_id}",
        snippet="Please review this operational workflow item.",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            requires_reply=True,
            is_human_personal=True,
            classification_reason="Needs operator review",
        )
    )
    item = AttentionItem(
        contact_id=contact_id,
        thread_id=thread.id,
        message_id=message.id,
        attention_score=score,
        reason="Needs operator review",
        recommended_action="Reply",
    )
    db_session.add(item)
    db_session.flush()
    return message, item


def _review_package(db_session, message: Message) -> ProposedActionReviewPackage:
    summary = ConversationSummary(
        thread_id=message.thread_id,
        summary_text="Operator workflow summary.",
        provider_name="mock",
    )
    db_session.add(summary)
    db_session.flush()
    package = ProposedActionReviewPackage(
        thread_id=message.thread_id,
        message_id=message.id,
        conversation_summary_id=summary.id,
        action_type=ProposedActionType.REPLY,
        explanation="Reply is recommended.",
        confidence=Decimal("0.8800"),
        status=ReviewPackageStatus.PENDING,
        provider_name="mock",
    )
    db_session.add(package)
    db_session.flush()
    return package
