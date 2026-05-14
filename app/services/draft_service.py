from sqlalchemy.orm import Session

from app.models.entities import DraftReply, DraftStatus, Message


def generate_draft_placeholder(db: Session, message: Message) -> DraftReply:
    draft = DraftReply(
        thread_id=message.thread_id,
        message_id=message.id,
        status=DraftStatus.GENERATED,
        draft_text=(
            "Draft placeholder only.\n"
            "- Acknowledge sender\n"
            "- Confirm understanding\n"
            "- Share next steps\n"
            "(Manual review required; no auto-send.)"
        ),
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
