from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Contact


def test_database_model_creation():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        contact = Contact(display_name="Test", primary_email="test@example.com")
        session.add(contact)
        session.commit()
        assert contact.id is not None
