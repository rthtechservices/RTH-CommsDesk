from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import get_db
from app.main import app
from app.models.entities import (
    OperationalSmokeCheck,
    OperationalSmokeRun,
)
from app.services import backup_service
from app.services.operational_smoke_runner import run_operational_smoke, smoke_run_to_dict
from app.services.provider_status_service import provider_status_rows


def test_smoke_runner_persists_sanitized_checks_without_external_writes(db_session):
    run = run_operational_smoke(
        db_session,
        settings=Settings(
            ai_provider="mock",
            execution_provider="external",
            external_write_dry_run=True,
            operational_test_mode=False,
        ),
    )

    assert run.id is not None
    assert db_session.query(OperationalSmokeRun).count() == 1
    assert db_session.query(OperationalSmokeCheck).count() >= 12
    assert all(check.external_write_performed is False for check in run.checks)
    detail = smoke_run_to_dict(run, include_checks=True)
    assert detail["id"] == run.id
    serialized = str(detail).lower()
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


def test_api_smoke_run_endpoints_persist_and_return_detail(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            created = client.post("/api/operational-smoke/run")
            runs = client.get("/api/operational-smoke/runs")
            detail = client.get(f"/api/operational-smoke/runs/{created.json()['run_id']}")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 200
    assert created.json()["run_id"] == 1
    assert created.json()["summary"]["external_write_performed"] is False
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["checks"]


def test_backup_service_excludes_sensitive_files(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "commsdesk.db").write_text("sqlite-placeholder", encoding="utf-8")
    (tmp_path / ".env.example").write_text("APP_NAME=RTH CommsDesk", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    (tmp_path / "gmail_token.json").write_text('{"access_token":"secret"}', encoding="utf-8")
    (tmp_path / "client_secret.json").write_text('{"client_secret":"secret"}', encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
    (tmp_path / "docs" / "HELP.md").write_text("# Help", encoding="utf-8")
    monkeypatch.setattr(backup_service, "PROJECT_ROOT", tmp_path)

    result = backup_service.create_local_backup(
        Settings(database_url=f"sqlite:///{tmp_path / 'commsdesk.db'}")
    )

    with zipfile.ZipFile(result.backup_path) as archive:
        names = set(archive.namelist())
    assert "commsdesk.db" in names
    assert ".env.example" in names
    assert ".env" not in names
    assert "gmail_token.json" not in names
    assert "client_secret.json" not in names
    assert ".env" in result.excluded_sensitive_files
    assert "gmail_token.json" in result.excluded_sensitive_files


def test_admin_and_smoke_routes_render_after_phase_22_changes(db_session):
    for path in ("/", "/admin", "/operational-smoke"):
        response = _client_get(db_session, path)
        assert response.status_code == 200, path
    assert "Start Here Today" in _client_get(db_session, "/").text
    assert "Create Local Backup" in _client_get(db_session, "/admin").text
    assert "Run Smoke Now" in _client_get(db_session, "/operational-smoke").text


def test_microsoft_write_boundaries_remain_disabled():
    rows = {row.key: row for row in provider_status_rows(Settings())}
    assert rows["microsoft_graph_outlook_mail_send"].state == "disabled"
    assert rows["outlook_calendar_read"].state == "disabled"
    assert rows["microsoft_graph_teams"].state == "disabled"
    assert rows["microsoft_graph_outlook_mail_send"].classification == "not implemented"


def test_reauth_script_documents_expected_token_files_and_scopes():
    text = Path("scripts/reauth-commsdesk.ps1").read_text(encoding="utf-8")
    assert "gmail_token.json" in text
    assert "google_calendar_token.json" in text
    assert "microsoft_graph_token.json" in text
    assert "https://www.googleapis.com/auth/gmail.compose" in text
    assert "https://www.googleapis.com/auth/calendar.events" in text
    assert "User.Read Mail.Read offline_access" in text
    assert "Client secrets and .env were not deleted." in text


def _client_get(db_session, path: str):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            return client.get(path)
    finally:
        app.dependency_overrides.clear()
