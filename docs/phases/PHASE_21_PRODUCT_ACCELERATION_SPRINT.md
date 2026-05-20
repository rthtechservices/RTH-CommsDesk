# Phase 21 — Product Acceleration Sprint

## Objective

Stop slicing the remaining MVP into tiny incremental phases. Deliver the next useful product chunk in one focused sprint.

Phase 20 should make intelligence, voice, and calendar reasoning materially better. Phase 21 should combine the next practical work that would otherwise have been split across separate visibility, smoke, and personalization phases.

## Product target

After this sprint, CommsDesk should be noticeably more usable day-to-day:

- the assistant profile/voice memory is visible and editable;
- learned writing traits can be approved and applied;
- live smoke testing is repeatable from one place;
- Gmail draft/calendar test execution is easier to validate safely;
- operator runbook/troubleshooting is current;
- Outlook write support remains planned only, not implemented.

## Scope

### 1. Assistant Profile / Voice Memory

Add a practical Assistant Profile page that shows and allows editing of:

- preferred sign-off;
- approved global voice traits;
- pending learned traits;
- avoided phrases;
- tone/brevity guidance;
- relationship-specific overrides where current models support it;
- evidence counts and safe excerpts.

Keep it simple. This does not need to become a full CRM or vector-memory system.

### 2. Draft Preview Tool

Add a local preview tool that shows how the current voice memory affects a sample draft.

- No external Gmail draft is created from preview.
- No send action is exposed from preview.
- Show which approved traits influenced the draft where practical.

### 3. Live Smoke Harness

Add a practical smoke surface or script for repeatable local validation:

- route smoke;
- Azure AI test;
- Microsoft Graph delegated test;
- Outlook sync;
- Gmail draft dry-run;
- Gmail draft live test readiness;
- Google Calendar dry-run/live test readiness;
- execution audit check.

Persist or display sanitized results locally where feasible. Do not log secrets, tokens, authorization headers, or private bodies.

### 4. Operator Runbook Refresh

Update the docs so the operator can run the app without reconstructing the last 20 phases from memory.

Include:

- daily startup;
- sync/test workflow;
- dry-run/live write posture;
- OAuth reauthorization;
- test allowlist use;
- safe Gmail draft test;
- safe calendar test;
- common blockers and fixes.

### 5. Outlook Write Planning Only

Keep Outlook send/calendar parked. Document what would be needed later, but do not implement Graph write calls.

## Out of scope

- Outlook send implementation.
- Outlook calendar implementation.
- Teams implementation.
- Vector memory/search.
- Direct `.env` editing from UI.
- Auto-send, auto-calendar, auto-archive, auto-delete.
- Removing Phase 19 test-mode/allowlist controls.

## Testing expectations

Do not create a massive test matrix for every copy change. Add tests for meaningful behavior only:

- voice memory page route/render;
- trait lifecycle if implemented;
- draft preview does not create external execution;
- smoke harness returns sanitized statuses;
- Phase 19 execution gating still passes;
- Microsoft write boundaries remain disabled.

Run:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for the major pages.

## Documentation expectations

Keep docs updated, but avoid repetitive boilerplate. Update only the files that materially change:

- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_STATUS.md`
- this phase file
- `README.md` only if setup/run behavior changed.

## Acceptance criteria

- Assistant Profile / Voice Memory page exists and is useful.
- Operator can inspect and manage learned voice traits.
- Draft preview shows voice-memory effect without external writes.
- Smoke harness/checklist reduces manual test friction.
- Operator runbook is current.
- Outlook write remains disabled/not implemented.
- Phase 19 safety controls remain intact.

## Codex notes

This is an acceleration sprint. Prefer pragmatic, usable implementation over perfect architecture. Do not split visibility, preview, smoke, and docs into separate future phases unless a hard technical blocker appears.
