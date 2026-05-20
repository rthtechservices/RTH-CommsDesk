from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.entities import (
    ExecutionRecord,
    InferenceStatus,
    SentMailLearningRecord,
    VoiceGuidance,
)


def test_assistant_profile_route_displays_preferred_signoff_and_traits(db_session):
    _seed_global_voice_guidance(db_session)

    response = _client_get(db_session, "/assistant-profile")

    assert response.status_code == 200
    assert "Assistant Profile" in response.text
    assert "Preferred Sign-Off" in response.text
    assert "Cheers," in response.text
    assert "Rohan." in response.text
    assert "Will drafts use it?" in response.text
    assert "Approved global traits" in response.text
    assert "Avoided phrases" in response.text


def test_assistant_profile_preview_is_local_only_and_creates_no_execution_records(db_session):
    _seed_global_voice_guidance(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/assistant-profile/preview",
                data={
                    "sender_name": "Jordan Client",
                    "sender_email": "jordan@example.com",
                    "relationship": "client",
                    "subject": "Proposal",
                    "message_text": "Can you confirm the next step?",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Local preview only" in response.text
    assert "No Gmail draft, send, calendar item, or execution record was created." in response.text
    assert "Cheers," in response.text
    assert "Rohan." in response.text
    assert db_session.query(ExecutionRecord).count() == 0


def test_assistant_profile_can_disable_and_reset_voice_guidance(db_session):
    guidance = _seed_global_voice_guidance(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            disabled = client.post(
                f"/assistant-profile/guidance/{guidance.id}",
                data={"action": "disable"},
                follow_redirects=False,
            )
            db_session.refresh(guidance)
            reset = client.post(
                f"/assistant-profile/guidance/{guidance.id}",
                data={"action": "reset"},
                follow_redirects=False,
            )
            db_session.refresh(guidance)
    finally:
        app.dependency_overrides.clear()

    assert disabled.status_code == 303
    assert reset.status_code == 303
    assert guidance.status == InferenceStatus.PENDING
    assert guidance.is_active is False
    assert guidance.tone_notes is None


def test_operational_smoke_renders_phase_21_checklist_and_routes(db_session):
    response = _client_get(db_session, "/operational-smoke")

    assert response.status_code == 200
    assert "Operator Smoke Checklist" in response.text
    assert "Route smoke paths" in response.text
    assert "/assistant-profile" in response.text
    assert "Azure/OpenAI AI test" in response.text
    assert "Microsoft Graph delegated test" in response.text
    assert "Outlook sync readiness" in response.text
    assert "Gmail draft dry-run readiness" in response.text
    assert "Google Calendar dry-run/live readiness" in response.text
    assert "Outlook send" in response.text
    assert "Teams" in response.text


def test_phase_21_key_routes_return_200(db_session):
    for path in (
        "/",
        "/assistant-profile",
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
    ):
        response = _client_get(db_session, path)
        assert response.status_code == 200, path


def _client_get(db_session, path: str):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.get(path)
    finally:
        app.dependency_overrides.clear()


def _seed_global_voice_guidance(db_session) -> VoiceGuidance:
    guidance = VoiceGuidance(
        contact_id=None,
        relationship_type="global_operator",
        tone_notes="concise, professional; avoid corporate filler; preferred sign-off: Cheers,\nRohan.",
        evidence_excerpt="Cheers, Rohan. appears repeatedly in sent mail.",
        status=InferenceStatus.APPROVED,
        is_active=True,
        source="global_sent_inference",
    )
    db_session.add(guidance)
    for index in range(3):
        db_session.add(
            SentMailLearningRecord(
                source_type="gmail",
                source_message_id=f"phase21-sent-{index}",
                recipient_email=f"person{index}@example.com",
                body_excerpt="Thanks for this.\n\nCheers,\nRohan.",
            )
        )
    db_session.commit()
    return guidance
