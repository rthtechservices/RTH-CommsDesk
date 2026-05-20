from __future__ import annotations

import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.models.entities import (
    DraftReply,
    DraftStatus,
    ExecutionActionType,
    ExecutionRecord,
    ExecutionStatus,
    InferenceStatus,
    Message,
    MessageThread,
    VoiceGuidance,
    VoiceProfile,
)
from app.services.backup_service import create_local_backup
from app.services.draft_service import list_drafts
from app.services.execution_service import prepare_execution_for_draft


def test_outlook_draft_prepare_blocks_before_gmail_execution(db_session: Session):
    draft = _seed_draft(db_session, source_type="outlook", suffix="outlook-block")

    try:
        prepare_execution_for_draft(db_session, draft.id)
    except ValueError as exc:
        assert str(exc) == "Outlook draft creation is not implemented or not enabled."
    else:
        raise AssertionError("Outlook draft preparation should fail closed")

    assert db_session.query(ExecutionRecord).count() == 0


def test_outlook_draft_review_page_shows_platform_readiness(db_session: Session):
    draft = _seed_draft(db_session, source_type="outlook", suffix="outlook-page")

    response = _client_get(db_session, f"/drafts/{draft.id}")

    assert response.status_code == 200
    assert "<strong class=\"label\">Source</strong>" in response.text
    assert ">outlook</span>" in response.text
    assert "Outlook draft creation is not implemented or not enabled." in response.text
    assert "Prepare external Gmail draft execution</button>" in response.text
    assert "disabled" in response.text


def test_draft_lifecycle_controls_hide_cancelled_and_deleted_by_default(db_session: Session):
    active = _seed_draft(db_session, suffix="active")
    _seed_draft(db_session, suffix="cancelled", status=DraftStatus.CANCELLED)
    _seed_draft(db_session, suffix="deleted", status=DraftStatus.DELETED)

    active_rows = list_drafts(db_session)
    assert [draft.id for draft in active_rows] == [active.id]

    all_response = _client_get(db_session, "/drafts?status=all")
    assert all_response.status_code == 200
    assert "Phase 27 active" in all_response.text
    assert "Phase 27 cancelled" in all_response.text
    assert "Phase 27 deleted" in all_response.text
    assert "Cancel local draft" in all_response.text
    assert "Delete local record" in all_response.text


def test_executions_default_pending_tabs_and_all_access(db_session: Session):
    pending = ExecutionRecord(
        action_type=ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
        status=ExecutionStatus.PENDING_REVIEW,
        provider_name="mock",
        payload_json=json.dumps({"to": "pending@example.com"}),
    )
    executed = ExecutionRecord(
        action_type=ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT,
        status=ExecutionStatus.EXECUTED,
        provider_name="mock",
        payload_json=json.dumps({"to": "executed@example.com"}),
    )
    db_session.add_all([pending, executed])
    db_session.commit()

    default_response = _client_get(db_session, "/executions")
    assert default_response.status_code == 200
    assert "Pending Review" in default_response.text
    assert "Executed</span>" not in default_response.text
    assert "Pending" in default_response.text
    assert "Executed" in default_response.text

    all_response = _client_get(db_session, "/executions?status=all")
    assert all_response.status_code == 200
    assert "Pending Review" in all_response.text
    assert "Executed</span>" in all_response.text


def test_voice_buttons_return_html_200_and_create_profile_form_works(db_session: Session):
    new_response = _client_get(db_session, "/voice-calibration/new")
    import_response = _client_get(db_session, "/voice-calibration/import-sent")

    assert new_response.status_code == 200
    assert "Create Voice Profile" in new_response.text
    assert "profile name" in new_response.text.lower()
    assert import_response.status_code == 200
    assert "Import Sent Mail Samples" in import_response.text

    create_response = _client_post(
        db_session,
        "/voice-calibration/new",
        data={
            "profile_name": "Phase 27 Voice",
            "description": "Concise local test voice",
            "default_signoff": "Regards",
            "enabled": "true",
        },
    )
    assert create_response.status_code == 200
    created = db_session.query(VoiceProfile).filter_by(name="Phase 27 Voice").one()
    assert created.is_enabled is True
    assert created.signoff_style == "Regards"


def test_assistant_profile_is_useful_without_voice_profiles(db_session: Session):
    db_session.add_all(
        [
            VoiceGuidance(
                relationship_type="client",
                tone_notes="Use direct status updates.",
                evidence_excerpt="approved sample",
                status=InferenceStatus.APPROVED,
                is_active=True,
            ),
            VoiceGuidance(
                relationship_type="vendor",
                tone_notes="Avoid extra detail.",
                evidence_excerpt="rejected sample",
                status=InferenceStatus.REJECTED,
            ),
        ]
    )
    db_session.commit()

    response = _client_get(db_session, "/assistant-profile")

    assert response.status_code == 200
    assert "Assistant Readiness" in response.text
    assert "Active voice profile" in response.text
    assert "Create voice profile" in response.text
    assert "Approved guidance" in response.text
    assert "Rejected/disabled" in response.text


def test_backup_includes_sqlite_and_redacted_config_by_default(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "commsdesk-test.db"
    db_path.write_text("sqlite placeholder", encoding="utf-8")
    backup_dir = Path.cwd() / "_backups"

    settings = Settings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        gmail_token_file="gmail_token.json",
        google_calendar_token_file="google_calendar_token.json",
        microsoft_graph_token_file="microsoft_graph_token.json",
        gmail_client_secret_file="client_secret.json",
        openai_api_key="secret-test-key",
    )

    metadata = create_local_backup(settings)

    assert metadata.database_included is True
    assert metadata.oauth_tokens_included is False
    assert metadata.env_snapshot_status == "redacted"
    assert metadata.filename.endswith(".zip")
    assert metadata.size_bytes > 0

    archive_path = Path(metadata.backup_path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            assert db_path.name in names
            assert "config-snapshot.redacted.json" in names
            assert "gmail_token.json" not in names
            config = json.loads(archive.read("config-snapshot.redacted.json").decode("utf-8"))
            assert config["openai_api_key"] == "[redacted]"
            assert config["backup_include_oauth_tokens"] is False
    finally:
        archive_path.unlink(missing_ok=True)
        try:
            backup_dir.rmdir()
        except OSError:
            pass


def test_global_nav_highlights_current_page(db_session: Session):
    response = _client_get(db_session, "/drafts")

    assert response.status_code == 200
    assert 'class="active" href="/drafts"' in response.text


def _seed_draft(
    db_session: Session,
    *,
    source_type: str = "gmail",
    suffix: str = "draft",
    status: DraftStatus = DraftStatus.GENERATED,
) -> DraftReply:
    thread = MessageThread(
        source_type=source_type,
        source_thread_id=f"phase-27-thread-{suffix}",
        normalized_subject=f"Phase 27 {suffix}",
    )
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type=source_type,
        source_message_id=f"phase-27-message-{suffix}",
        sender_email=f"{suffix}@example.com",
        subject=f"Phase 27 {suffix}",
        snippet="Please send a quick update.",
    )
    db_session.add(message)
    db_session.flush()
    profile = VoiceProfile(
        name=f"Phase 27 Voice {suffix}",
        audience_type="client",
        signoff_style="Best",
    )
    db_session.add(profile)
    db_session.flush()
    draft = DraftReply(
        thread_id=thread.id,
        message_id=message.id,
        voice_profile_id=profile.id,
        draft_text=f"Draft body for {suffix}",
        send_ready_subject=f"Re: Phase 27 {suffix}",
        send_ready_body=f"Ready body for {suffix}",
        status=status,
        provider_name="mock",
    )
    db_session.add(draft)
    db_session.commit()
    return draft


def _client_get(db_session: Session, path: str):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.get(path)
    finally:
        app.dependency_overrides.clear()


def _client_post(db_session: Session, path: str, data: dict[str, str]):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.post(path, data=data)
    finally:
        app.dependency_overrides.clear()
