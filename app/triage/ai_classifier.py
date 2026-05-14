from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.triage.deterministic_classifier import ClassificationResult, MessagePayload


@dataclass
class CompactMessagePayload:
    sender_email: str | None
    subject: str | None
    snippet: str | None


class AIClassifier(Protocol):
    def classify(self, payload: CompactMessagePayload) -> ClassificationResult:
        ...


class MockAIClassifier:
    def classify(self, payload: CompactMessagePayload) -> ClassificationResult:
        return ClassificationResult(
            requires_reply=False,
            urgency_level=0,
            is_human_personal=True,
            is_client_work=False,
            is_marketing=False,
            is_newsletter=False,
            is_receipt=False,
            is_group_noise=False,
            is_system_notification=False,
            confidence=Decimal("0.50"),
            classification_reason="Mock AI classifier fallback",
        )
