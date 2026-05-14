from app.models.entities import AttentionItem, AttentionStatus
from app.services.attention_service import build_attention_queue


def test_attention_queue_excludes_reviewed_by_default(db_session):
    db_session.add_all(
        [
            AttentionItem(thread_id=1, attention_score=80, status=AttentionStatus.NEW),
            AttentionItem(thread_id=2, attention_score=90, status=AttentionStatus.REVIEWED),
            AttentionItem(thread_id=3, attention_score=70, status=AttentionStatus.DISMISSED),
        ]
    )
    db_session.commit()

    queue = build_attention_queue(db_session)
    assert len(queue) == 1
    assert queue[0].status == AttentionStatus.NEW


def test_attention_queue_can_include_reviewed(db_session):
    db_session.add_all(
        [
            AttentionItem(thread_id=1, attention_score=80, status=AttentionStatus.NEW),
            AttentionItem(thread_id=2, attention_score=90, status=AttentionStatus.REVIEWED),
        ]
    )
    db_session.commit()

    queue = build_attention_queue(db_session, include_reviewed=True)
    assert len(queue) == 2
