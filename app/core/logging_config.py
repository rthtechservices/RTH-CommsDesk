from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from app.core.config import Settings

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;]+)"),
)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        if record.args:
            record.args = tuple(redact_text(str(arg)) for arg in record.args)
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    if settings.log_format.strip().lower() == "json" or settings.normalized_env in {
        "staging",
        "production",
        "prod",
    }:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)

    level_name = settings.log_level.strip().upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = True


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted
