from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import VoiceProfile

VOICE_SEEDS = [
    {
        "name": "Client Voice",
        "audience_type": "client",
        "tone_description": "direct, competent, warm, concise",
        "formality_level": 4,
        "humor_level": 1,
        "apology_style": "Use 'Thanks for your patience' instead of excessive apology",
        "signoff_style": "include clear next steps",
    },
    {
        "name": "Friend Voice",
        "audience_type": "friend",
        "tone_description": "casual, warm, lightly funny",
        "formality_level": 2,
        "humor_level": 3,
        "apology_style": "acknowledge delay briefly without overexplaining",
        "signoff_style": "friendly and short",
    },
    {
        "name": "Partner Voice",
        "audience_type": "partner",
        "tone_description": "warm, direct, emotionally present",
        "formality_level": 2,
        "humor_level": 2,
        "apology_style": "be accountable and present",
        "signoff_style": "avoid corporate language",
    },
    {
        "name": "Vendor Voice",
        "audience_type": "vendor",
        "tone_description": "brief, transactional, clear",
        "formality_level": 3,
        "humor_level": 0,
        "apology_style": "short and practical",
        "signoff_style": "clear action request",
    },
    {
        "name": "Short Acknowledgement",
        "audience_type": "short_acknowledgement",
        "tone_description": "very brief, polite, confirms receipt only",
        "formality_level": 3,
        "humor_level": 0,
        "apology_style": "avoid apology unless needed",
        "signoff_style": "short thanks",
        "max_length_preference": 80,
    },
]


def seed_voice_profiles() -> None:
    db: Session = SessionLocal()
    try:
        existing = {item.name for item in db.query(VoiceProfile).all()}
        for seed in VOICE_SEEDS:
            if seed["name"] not in existing:
                db.add(VoiceProfile(**seed))
        db.commit()
    finally:
        db.close()
