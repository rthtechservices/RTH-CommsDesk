from app.triage.deterministic_classifier import MessagePayload, classify_message


def test_newsletter_detection():
    result = classify_message(
        MessagePayload(
            sender_email="news@updates.com",
            subject="General update",
            snippet="Hello there",
            headers={"List-Unsubscribe": "<mailto:unsubscribe@updates.com>"},
        )
    )
    assert result.is_newsletter is True
    assert result.is_marketing is True
    assert result.requires_reply is False
    assert "list-unsubscribe header" in result.classification_reason


def test_requires_reply_detection():
    result = classify_message(
        MessagePayload(
            sender_email="person@gmail.com",
            subject="Can you review this today?",
            snippet="Please let me know by tomorrow.",
        )
    )
    assert result.requires_reply is True
    assert result.urgency_level >= 2


def test_client_work_detection():
    result = classify_message(
        MessagePayload(
            sender_email="pm@clientcorp.com",
            subject="Client deliverable milestone",
            snippet="Can you send the proposal?",
        )
    )
    assert result.is_client_work is True
