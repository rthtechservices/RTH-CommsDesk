from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base


@pytest.fixture(autouse=True)
def default_mock_ai_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("EXECUTION_PROVIDER", "mock")
    monkeypatch.setenv("EXTERNAL_WRITE_DRY_RUN", "true")
    monkeypatch.setenv("GMAIL_WRITE_ENABLED", "false")
    monkeypatch.setenv("GMAIL_DRAFT_CREATE_ENABLED", "false")
    monkeypatch.setenv("GMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("GMAIL_LABEL_ARCHIVE_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_CALENDAR_WRITE_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_CALENDAR_READ_ENABLED", "false")
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    monkeypatch.setenv("OPERATIONAL_TEST_MODE", "false")
    monkeypatch.setenv("EXECUTION_TEST_EMAIL_ALLOWLIST", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
