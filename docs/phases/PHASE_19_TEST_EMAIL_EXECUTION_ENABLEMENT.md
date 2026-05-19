# Phase 19 — Test Email Execution Enablement

## Objective

Make outbound execution genuinely usable with controlled test emails, without opening broad production-risk write behavior.

This phase should prove that CommsDesk can create/send test Gmail actions and create Google Calendar events through the existing approved execution pipeline, while keeping non-test recipients blocked or fully gated.

## Product intent

The near-term MVP needs to prove that the car moves. The goal is not production automation yet; the goal is reliable operator-driven execution against known test targets.

Target workflow:

```text
Review package or draft
→ prepare execution
→ validate recipient/action against test allowlist
→ approve/confirm with fewer clicks where safe
→ execute Gmail draft/send or Google Calendar event
→ record result and audit trail
```

## Scope

### Test mode and allowlist

Add explicit operational test-mode configuration:

```env
OPERATIONAL_TEST_MODE=false
EXECUTION_TEST_EMAIL_ALLOWLIST=
```

Behavior:

- When `OPERATIONAL_TEST_MODE=true`, allow streamlined execution only for allowlisted test recipients.
- Allowlist values should be comma-separated email addresses or domains if intentionally supported.
- Non-allowlisted recipients must remain blocked or must use the normal full approval/confirmation path.
- Never silently downgrade a blocked live write to mock success.

### Gmail execution fast path

For allowlisted test recipients:

- Make "Create Gmail Draft Now" available from draft/review-package execution when the payload is valid.
- Make "Send Test Reply Now" available only when `GMAIL_SEND_ENABLED=true`, `EXECUTION_PROVIDER=external`, `EXTERNAL_WRITE_DRY_RUN=false`, and the recipient is allowlisted.
- Keep payload preview visible before execution.
- Keep send-ready subject/body separation; no review notes, caveats, or duplicated `Subject:` lines may enter Gmail.

### Google Calendar test execution

For test events:

- Make calendar event/reminder execution easier to trigger from a review package.
- Require `GOOGLE_CALENDAR_WRITE_ENABLED=true`, `EXECUTION_PROVIDER=external`, and `EXTERNAL_WRITE_DRY_RUN=false` for real calendar writes.
- Preserve `GOOGLE_CALENDAR_TIME_ZONE` on both start and end payloads.
- Display the target calendar and final event details before execution.

### Execution diagnostics

Execution failures must report direct, plain-language causes:

- Feature flag disabled.
- Dry-run still enabled.
- Provider not external.
- Missing OAuth scopes.
- Token expired or unreadable.
- Recipient not allowlisted in operational test mode.
- Provider HTTP failure.

### Audit trail

- Every streamlined test execution still creates an immutable execution attempt.
- Every attempt must log prepare, approve/confirm/execute, provider result, and failure details where applicable.
- Rerun/clone/new-attempt behavior from earlier phases must remain intact.

## Out of scope

- Outlook send.
- Outlook calendar write.
- Teams writes.
- Auto-send without operator action.
- Production allowlist/approval policy.
- Broad destructive mailbox actions.

## Acceptance criteria

Automated validation must pass:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Manual smoke checklist:

1. Configure test allowlist with the operator's own test recipient.
2. Confirm provider status shows external execution and dry-run state accurately.
3. Prepare Gmail draft execution from a test review package.
4. Execute create-draft against an allowlisted recipient.
5. Confirm Gmail draft contains only send-ready subject/body.
6. Prepare send-reply execution against an allowlisted test thread.
7. Execute send only after explicit operator action.
8. Prepare and execute a test Google Calendar event/reminder.
9. Confirm blocked recipient behavior for a non-allowlisted address.
10. Confirm audit trail and provider result/error are visible for each attempt.

## Documentation updates required

Update:

- `.env.example`
- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file

## Codex notes

Do not weaken the existing safety model globally. Add an explicit test-mode path that makes local/operator testing less painful while keeping non-test recipients and unsupported providers blocked. Prefer clear failure messages over permissive fallback.

## Completion notes — 2026-05-19

Status: Completed for human review.

Implemented:

- Added `OPERATIONAL_TEST_MODE=false` and `EXECUTION_TEST_EMAIL_ALLOWLIST=` defaults.
- Added centralized allowlist parsing and readiness policy in `app/services/execution_test_policy.py`.
- Supports comma-separated exact addresses and explicit `@domain` entries with case/whitespace normalization.
- Blocks empty allowlists, non-allowlisted recipients, disabled operational test mode, non-external provider mode, disabled feature flags, Gmail send dry-run, and unsupported actions before external provider writes.
- Allows Gmail draft and Google Calendar dry-run test execution to record `external_write_performed=false`; Gmail send requires dry-run disabled.
- Preserved send-ready Gmail subject/body sanitization and Google Calendar timezone payload behavior.
- Added Test Execution Readiness UI on `/operational-smoke`, execution detail, draft review, review package detail, and dashboard next-best/ready-execution areas.
- Kept Outlook send, Outlook calendar, and Teams disabled/not implemented.

Validation:

- Focused policy/execution/operational tests passed during implementation.
- Final full validation and route smoke results are recorded in `docs/IMPLEMENTATION_LOG.md`.

Human review notes:

- Live external Gmail/Calendar writes were not performed in this session.
- To live-smoke safely, configure one controlled allowlisted test recipient, review the execution payload, then approve and confirm one Gmail draft or Calendar event attempt.
