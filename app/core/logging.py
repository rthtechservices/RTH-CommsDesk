def redact_text(value: str | None, keep: int = 32) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "[REDACTED]"
    return f"{value[:keep]}...[REDACTED]"
