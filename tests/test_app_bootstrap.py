from fastapi.testclient import TestClient

from app.main import app


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


def test_sync_endpoint_returns_clear_oauth_error(monkeypatch):
    def _raise_missing_credentials(_db):
        raise FileNotFoundError("missing client secret")

    monkeypatch.setattr("app.api.routes.sync_gmail_messages", _raise_missing_credentials)
    with TestClient(app) as client:
        response = client.post("/api/sync/gmail")
    assert response.status_code == 400
    assert "client secrets file is missing" in response.json()["detail"].lower()
