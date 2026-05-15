from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.entities import (
    AttentionItem,
    AttentionStatus,
    AutomationCandidate,
    Contact,
    Message,
    MessageClassification,
    MessageThread,
    ProposedActionReviewPackage,
    ProposedActionType,
    ReviewPackageStatus,
)
from app.services.bulk_triage_service import (
    apply_bulk_action,
    get_bulk_backlog_page,
    refresh_automation_candidates,
    undo_bulk_action,
)


def test_bulk_backlog_pagination_goes_beyond_first_100_items(db_session):
    for index in range(1, 231):
        thread = MessageThread(source_type="gmail", source_thread_id=f"bulk-thread-{index}")
        db_session.add(thread)
        db_session.flush()
        message = Message(
            thread_id=thread.id,
            source_type="gmail",
            source_message_id=f"bulk-message-{index}",
            sender_email=f"sender{index}@example.com",
            subject=f"Message {index}",
            snippet="bulk",
        )
        db_session.add(message)
        db_session.flush()
        db_session.add(
            MessageClassification(
                message_id=message.id,
                is_human_personal=True,
                classification_reason="fixture",
            )
        )
        db_session.add(
            AttentionItem(
                thread_id=thread.id,
                message_id=message.id,
                attention_score=50,
                status=AttentionStatus.NEW,
            )
        )
    db_session.commit()

    first_page = get_bulk_backlog_page(db_session, page=1, page_size=100, queue_filter="unreviewed")
    third_page = get_bulk_backlog_page(db_session, page=3, page_size=100, queue_filter="unreviewed")

    assert first_page.total_count == 230
    assert len(first_page.items) == 100
    assert len(third_page.items) == 30


def test_refresh_automation_candidates_detects_noise_unsubscribe_and_stale_items(db_session):
    contact = Contact(
        display_name="Marketing Sender",
        primary_email="marketing@example.com",
        relationship_type="newsletter",
    )
    db_session.add(contact)
    db_session.flush()
    for index in range(1, 5):
        thread = MessageThread(
            source_type="gmail",
            source_thread_id=f"newsletter-thread-{index}",
            contact_id=contact.id,
        )
        db_session.add(thread)
        db_session.flush()
        message = Message(
            thread_id=thread.id,
            source_type="gmail",
            source_message_id=f"newsletter-message-{index}",
            sender_email="marketing@example.com",
            received_at=datetime.now(UTC) - timedelta(days=150),
            subject="Weekly deals",
            snippet="unsubscribe and manage preferences inside",
            body_text="Limited time promotion. Click unsubscribe to manage preferences.",
            is_unread=True,
        )
        db_session.add(message)
        db_session.flush()
        db_session.add(
            MessageClassification(
                message_id=message.id,
                is_marketing=True,
                is_newsletter=True,
                is_group_noise=True,
                classification_reason="newsletter",
            )
        )
        db_session.add(
            AttentionItem(
                thread_id=thread.id,
                message_id=message.id,
                contact_id=contact.id,
                attention_score=10,
                status=AttentionStatus.NEW,
            )
        )
    db_session.commit()

    changed = refresh_automation_candidates(db_session)
    types = {
        package.candidate_type.value
        for package in db_session.query(ProposedActionReviewPackage).all()
    }
    # ProposedActionReviewPackage types remain independent in this phase.
    assert changed > 0
    candidate_types = {
        row.candidate_type.value for row in db_session.query(AutomationCandidate).all()
    }
    assert "mark_noise" in candidate_types
    assert "unsubscribe_review" in candidate_types
    assert "archive_candidate" in candidate_types
    assert "delete_candidate" in candidate_types
    assert types == set()


def test_bulk_status_update_and_undo_restores_previous_state(db_session):
    thread = MessageThread(source_type="gmail", source_thread_id="undo-thread")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="undo-message",
        sender_email="person@example.com",
        subject="Need this reviewed",
        snippet="please review",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            requires_reply=True,
            classification_reason="fixture",
        )
    )
    item = AttentionItem(
        thread_id=thread.id,
        message_id=message.id,
        attention_score=42,
        status=AttentionStatus.NEW,
    )
    db_session.add(item)
    db_session.commit()

    log = apply_bulk_action(
        db_session,
        attention_ids=[item.id],
        action_type="mark_reviewed",
        queue_filter="unreviewed",
    )
    db_session.refresh(item)
    assert item.status == AttentionStatus.REVIEWED
    assert log.item_count == 1

    undo_bulk_action(db_session, log.id)
    db_session.refresh(item)
    assert item.status == AttentionStatus.NEW


def test_bulk_approve_no_response_needed_updates_review_package_status(db_session):
    thread = MessageThread(source_type="gmail", source_thread_id="nrn-thread")
    db_session.add(thread)
    db_session.flush()
    message = Message(
        thread_id=thread.id,
        source_type="gmail",
        source_message_id="nrn-message",
        sender_email="friend@example.com",
        subject="No worries",
        snippet="Thanks for the heads up.",
    )
    db_session.add(message)
    db_session.flush()
    db_session.add(
        MessageClassification(
            message_id=message.id,
            is_human_personal=True,
            classification_reason="fixture",
        )
    )
    item = AttentionItem(
        thread_id=thread.id,
        message_id=message.id,
        attention_score=28,
        status=AttentionStatus.NEW,
    )
    db_session.add(item)
    package = ProposedActionReviewPackage(
        thread_id=thread.id,
        message_id=message.id,
        action_type=ProposedActionType.NO_RESPONSE_NEEDED,
        explanation="No response needed",
        confidence=Decimal("0.9000"),
        status=ReviewPackageStatus.PENDING,
        provider_name="mock",
        is_external_action=False,
    )
    db_session.add(package)
    db_session.commit()

    apply_bulk_action(
        db_session,
        attention_ids=[item.id],
        action_type="approve_no_response_needed",
        queue_filter="proposed_actions",
    )
    db_session.refresh(package)
    assert package.status == ReviewPackageStatus.APPROVED
