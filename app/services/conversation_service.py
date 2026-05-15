from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.entities import BodyStoredMode, Message


@dataclass
class TimelineEntry:
    message: Message
    is_selected: bool
    has_full_body: bool


def conversation_timeline(
    db: Session, thread_id: int, selected_message_id: int
) -> list[TimelineEntry]:
    messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.received_at.asc(), Message.id.asc())
        .all()
    )
    return [
        TimelineEntry(
            message=message,
            is_selected=message.id == selected_message_id,
            has_full_body=message.body_stored_mode == BodyStoredMode.FULL_TEXT
            and bool(message.body_text),
        )
        for message in messages
    ]
