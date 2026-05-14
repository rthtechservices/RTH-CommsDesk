from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.entities import Contact, Message, MessageClassification, MessageThread
from app.services.attention_service import calculate_attention_score


def test_attention_score_increases_for_vip_and_urgency():
    contact = Contact(importance_tier=4, relationship_type="client", is_vip=True, is_noise=False)
    thread = MessageThread(source_type="gmail", source_thread_id="t1", unread_count=2)
    message = Message(source_type="gmail", source_message_id="m1", thread_id=1, received_at=datetime.now(UTC) - timedelta(hours=8))
    classification = MessageClassification(
        message_id=1,
        requires_reply=True,
        urgency_level=3,
        is_client_work=True,
        is_marketing=False,
        is_newsletter=False,
        confidence=Decimal("0.9"),
    )

    score = calculate_attention_score(contact, thread, message, classification)
    assert score >= 100


def test_attention_score_penalizes_noise():
    contact = Contact(importance_tier=1, relationship_type="vendor", is_vip=False, is_noise=True)
    thread = MessageThread(source_type="gmail", source_thread_id="t2", unread_count=1)
    message = Message(source_type="gmail", source_message_id="m2", thread_id=1, received_at=datetime.now(UTC))
    classification = MessageClassification(
        message_id=2,
        requires_reply=False,
        urgency_level=0,
        is_client_work=False,
        is_marketing=True,
        is_newsletter=True,
        confidence=Decimal("0.8"),
    )

    score = calculate_attention_score(contact, thread, message, classification)
    assert score == 0
