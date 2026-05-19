from app.core.config import Settings
from app.models.entities import ExecutionActionType, ExecutionRecord
from app.services.execution_test_policy import (
    parse_execution_test_allowlist,
    readiness_for_execution,
    recipient_is_allowlisted,
)


def test_allowlist_parsing_normalizes_exact_addresses_and_domains():
    entries = parse_execution_test_allowlist(" Test@Example.COM , @RTHTechServices.com, ")

    assert [entry.value for entry in entries] == ["test@example.com", "@rthtechservices.com"]
    assert [entry.is_domain for entry in entries] == [False, True]


def test_exact_email_allowlist_match():
    entries = parse_execution_test_allowlist("test@example.com")

    assert recipient_is_allowlisted("Test <TEST@example.com>", entries) is True
    assert recipient_is_allowlisted("other@example.com", entries) is False


def test_domain_allowlist_match_is_explicit():
    entries = parse_execution_test_allowlist("@rthtechservices.com")

    assert recipient_is_allowlisted("person@rthtechservices.com", entries) is True
    assert recipient_is_allowlisted("person@example.com", entries) is False


def test_empty_allowlist_blocks_streamlined_email_execution():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT, '{"to":"test@example.com"}'),
        _settings(operational_test_mode=True, execution_test_email_allowlist=""),
    )

    assert readiness.allowed is False
    assert readiness.blocked_reason == (
        "Blocked: allowlist empty. Set EXECUTION_TEST_EMAIL_ALLOWLIST to test recipients."
    )


def test_operational_test_mode_disabled_blocks_streamlined_execution():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT, '{"to":"test@example.com"}'),
        _settings(operational_test_mode=False, execution_test_email_allowlist="test@example.com"),
    )

    assert readiness.allowed is False
    assert readiness.blocked_reason == (
        "Blocked: operational test mode disabled. Set OPERATIONAL_TEST_MODE=true."
    )


def test_non_allowlisted_recipient_is_blocked():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT, '{"to":"other@example.com"}'),
        _settings(operational_test_mode=True, execution_test_email_allowlist="test@example.com"),
    )

    assert readiness.allowed is False
    assert readiness.blocked_reason == "Blocked: recipient not allowlisted."


def test_allowlisted_draft_can_proceed_through_dry_run_readiness_path():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.CREATE_EXTERNAL_GMAIL_DRAFT, '{"to":"test@example.com"}'),
        _settings(
            operational_test_mode=True,
            execution_test_email_allowlist="test@example.com",
            gmail_write_enabled=True,
            gmail_draft_create_enabled=True,
            external_write_dry_run=True,
        ),
    )

    assert readiness.allowed is True
    assert readiness.dry_run is True
    assert readiness.next_action == (
        "Approve and confirm to record a dry-run; no external Gmail draft will be created."
    )


def test_gmail_send_is_blocked_when_dry_run_enabled():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.SEND_GMAIL_REPLY, '{"to":"test@example.com"}'),
        _settings(
            operational_test_mode=True,
            execution_test_email_allowlist="test@example.com",
            gmail_write_enabled=True,
            gmail_send_enabled=True,
            external_write_dry_run=True,
        ),
    )

    assert readiness.allowed is False
    assert "dry-run still enabled" in (readiness.blocked_reason or "")


def test_google_calendar_test_execution_does_not_require_email_allowlist():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.CREATE_CALENDAR_EVENT, '{"summary":"Test"}'),
        _settings(
            operational_test_mode=True,
            execution_test_email_allowlist="",
            google_calendar_write_enabled=True,
        ),
    )

    assert readiness.allowed is True
    assert readiness.target == "primary"


def test_outlook_and_teams_actions_remain_unavailable():
    readiness = readiness_for_execution(
        _record(ExecutionActionType.APPLY_GMAIL_LABEL_ARCHIVE, '{"to":"test@example.com"}'),
        _settings(
            operational_test_mode=True,
            execution_test_email_allowlist="test@example.com",
        ),
    )

    assert readiness.allowed is False
    assert "unsupported provider/action" in (readiness.blocked_reason or "")


def _settings(**overrides) -> Settings:
    base = {
        "execution_provider": "external",
        "external_write_dry_run": True,
        "gmail_write_enabled": False,
        "gmail_draft_create_enabled": False,
        "gmail_send_enabled": False,
        "google_calendar_write_enabled": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _record(action_type: ExecutionActionType, payload: str) -> ExecutionRecord:
    return ExecutionRecord(action_type=action_type, payload_json=payload, provider_name="mock")
