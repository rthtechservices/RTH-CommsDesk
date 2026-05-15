# Phase 10 — Approved Outbound Execution

## Objective

Allow RTH CommsDesk to execute selected communication actions after explicit user approval. This is where the app becomes an assistant that can send and schedule for the user, but only through a visible approval workflow.

## Required implementation

- [x] Add an execution engine for approved proposed actions/review packages.
- [x] Add execution status fields:
  - pending_review
  - approved
  - executing
  - executed
  - failed
  - cancelled
- [x] Add duplicate-execution prevention for each proposed action.
- [x] Add final confirmation UI for external writes.
- [x] Add audit records for:
  - who/what approved the action
  - timestamp
  - source message/thread
  - exact outbound content or action payload
  - provider result
  - error if failed
- [x] Implement mocked provider tests for:
  - Gmail reply send
  - Gmail external draft creation if selected
  - Google Calendar event/reminder creation
  - archive/label actions if included
- [x] Add real Gmail send only after explicit OAuth scope/config review.
- [x] Add real calendar write only after explicit OAuth scope/config review.
- [x] Add user-visible warnings for destructive actions such as delete/unsubscribe.
- [x] Make execution idempotent: refreshing or double-clicking must not send twice.

## Initial executable action types

Implement in this priority order:

1. Create external Gmail draft from approved local draft.
2. Send Gmail reply from approved review package.
3. Create Google Calendar reminder/event from approved proposed calendar action.
4. Apply Gmail label/archive from approved action.
5. Delete/unsubscribe only if separately reviewed and strongly confirmed.

## Product behavior example

Review package:

- Michael needs help with his laptop and proposed Tuesday evening.
- Calendar availability shows Tuesday evening is free.
- Draft reply says Rohan is available.
- Proposed calendar invite is prepared.

Expected result:

- User clicks approve.
- Final confirmation shows the exact email and calendar payload.
- After confirmation, the app sends the email and creates/sends the calendar event.
- Audit log records the execution.
- The same package cannot be executed twice.

## Out of scope

- Fully autonomous unsupervised sending/deleting.
- New connectors unrelated to executing already-approved proposed actions.
- Background execution without visible status.

## Documentation updates required

- [x] `docs/IMPLEMENTATION_LOG.md`
- [x] `docs/LESSONS_LEARNED.md`
- [x] `docs/HELP.md`
- [x] This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Mock execution tests pass for supported action types.
- [x] Final confirmation UI is present for external writes.
- [x] Approved actions execute once and only once.
- [x] Audit trail is visible.
- [x] Real provider write scopes are documented before use.

## Completion notes

Status: completed on 2026-05-15.

Implemented:

- Added `execution_records` and `execution_audit_logs` for staged outbound execution lifecycle and auditability.
- Added execution service with prepare/approve/confirm/cancel flows and deterministic mock provider operations.
- Added duplicate-prevention constraints and idempotent confirm behavior.
- Added execution pages (`/executions`, `/executions/{id}`) with final confirmation payload preview and destructive-action warnings.
- Added draft/review-package controls to prepare execution records directly from local artifacts.
- Added API endpoints for execution prepare/approve/confirm/cancel/list/detail and audit retrieval.
- Added tests for external draft creation, send reply, calendar execution, label/archive execution, and duplicate protection.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 68 tests.

Safety boundary confirmed:

- Execution requires explicit approval and final confirmation.
- Mock provider remains the local default; production write scope/configuration must be explicitly reviewed before real providers are enabled.
