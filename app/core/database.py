from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import entities  # noqa: F401

settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    run_migrations()


def run_migrations() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    database_url = get_settings().database_url
    config.attributes["database_url"] = database_url
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
