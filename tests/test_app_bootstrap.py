from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.core.database import get_db
from app.main import app
from app.models.entities import Message, MessageClassification, MessageThread


def test_app_imports_successfully():
    assert app.title == "RTH CommsDesk"


def test_form_route_dependency_is_available():
    with TestClient(app) as client:
        response = client.post("/api/contacts/noise")
    assert response.status_code == 422


def test_dashboard_loads():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200


def test_voice_calibration_route_loads():
    with TestClient(app) as client:
        response = client.get("/voice-calibration")
    assert response.status_code == 200


def test_bulk_triage_route_loads():
    with TestClient(app) as client:
        response = client.get("/bulk-triage")
    assert response.status_code == 200


def test_executions_route_loads():
    with TestClient(app) as client:
        response = client.get("/executions")
    assert response.status_code == 200


def test_message_detail_route_loads(db_session):
    thread = MessageThread(source_type="gmail", source_thread_id="route-t1", unread_count=1)
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="route-m1",
        sender_email="person@example.com",
        subject="Route detail",
        snippet="A small detail page test.",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(MessageClassification(message_id=message.id, classification_reason="test"))
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
    assert "Route detail" in response.text


def test_sync_endpoint_returns_clear_oauth_error(monkeypatch):
    def _raise_missing_credentials(*_args, **_kwargs):
        raise FileNotFoundError("missing client secret")

    monkeypatch.setattr("app.api.routes.sync_gmail_messages", _raise_missing_credentials)
    with TestClient(app) as client:
        response = client.post("/api/sync/gmail")
    assert response.status_code == 400
    assert "client secrets file is missing" in response.json()["detail"].lower()


def test_alembic_bootstrap_creates_current_local_schema(tmp_path, monkeypatch):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.core import database

    db_file = tmp_path / "bootstrap.db"
    database_url = f"sqlite:///{db_file.as_posix()}"

    class TmpSettings:
        pass

    TmpSettings.database_url = database_url

    monkeypatch.setattr(database, "get_settings", lambda: TmpSettings())

    database.run_migrations()

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    assert "source_sync_states" in inspector.get_table_names()
    assert "messages" in inspector.get_table_names()

    with engine.connect() as connection:
        version = connection.execute(text("select version_num from alembic_version")).scalar_one()
    alembic_cfg = Config(str(database.PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(database.PROJECT_ROOT / "alembic"))
    assert version == ScriptDirectory.from_config(alembic_cfg).get_current_head()
