from app.models.entities import Message, MessageClassification
from app.triage.ai_classifier import AIClassifier, CompactMessagePayload
from app.triage.deterministic_classifier import MessagePayload, classify_message


def classify_and_persist(
    message: Message, ai_classifier: AIClassifier | None = None
) -> MessageClassification:
    deterministic = classify_message(
        MessagePayload(
            sender_email=message.sender_email,
            subject=message.subject,
            snippet=message.snippet,
            headers=None,
        )
    )

    if ai_classifier:
        ai_result = ai_classifier.classify(
            CompactMessagePayload(
                sender_email=message.sender_email,
                subject=message.subject,
                snippet=message.snippet,
            )
        )
        result = deterministic if deterministic.confidence >= ai_result.confidence else ai_result
    else:
        result = deterministic

    return MessageClassification(
        message_id=message.id,
        requires_reply=result.requires_reply,
        urgency_level=result.urgency_level,
        is_human_personal=result.is_human_personal,
        is_client_work=result.is_client_work,
        is_marketing=result.is_marketing,
        is_newsletter=result.is_newsletter,
        is_receipt=result.is_receipt,
        is_group_noise=result.is_group_noise,
        is_system_notification=result.is_system_notification,
        confidence=result.confidence,
        classification_reason=result.classification_reason,
    )
