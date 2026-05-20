# Phase 22 — Live Operational Smoke and Regression Harness

## Objective

Make repeated real-provider smoke testing safe, scripted, and auditable.

After Gmail draft creation, calendar test execution, Outlook sync, and Azure AI diagnostics are all wired, the operator needs a repeatable way to prove the system still works without manually remembering every step.

## Scope

### Smoke checklist page or script

Add a manual smoke checklist page or CLI/script covering:

- route smoke
- provider status smoke
- Azure AI test
- Microsoft Graph delegated test
- Outlook sync
- Gmail draft dry-run
- Gmail draft live test for allowlisted recipients
- Gmail send dry-run/readiness only
- Google Calendar dry-run
- Google Calendar live test event for safe disposable events

### Test artifact conventions

Use consistent disposable artifact naming:

```text
CommsDesk Test - Safe to Delete
```

### Smoke results

Persist local smoke results with:

- test name
- provider/action
- timestamp
- status
- sanitized result/error
- external_write_performed flag
- artifact id where safe

### Cleanup guidance

Add guidance for cleaning up test drafts/events without enabling broad destructive automation.

## Out of scope

- Auto-deleting external test artifacts.
- New provider features.
- Outlook send/calendar implementation.
- Teams implementation.
- Production monitoring service.

## Acceptance criteria

- Operator can run or follow a single smoke workflow after changes.
- Results are visible locally and sanitized.
- Live writes remain Phase 19 test-mode/allowlist gated.
- No secrets, tokens, or private message bodies are logged in smoke results.
- Docs include a repeatable smoke runbook.

## Documentation updates required

Update:

- `README.md` if needed
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file
