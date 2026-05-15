# Phase 10 — Approved Outbound Execution

## Objective

Allow RTH CommsDesk to execute selected communication actions after explicit user approval. This is where the app becomes an assistant that can send and schedule for the user, but only through a visible approval workflow.

## Required implementation

- Add an execution engine for approved proposed actions/review packages.
- Add execution status fields:
  - pending_review
  - approved
  - executing
  - executed
  - failed
  - cancelled
- Add duplicate-execution prevention for each proposed action.
- Add final confirmation UI for external writes.
- Add audit records for:
  - who/what approved the action
  - timestamp
  - source message/thread
  - exact outbound content or action payload
  - provider result
  - error if failed
- Implement mocked provider tests for:
  - Gmail reply send
  - Gmail external draft creation if selected
  - Google Calendar event/reminder creation
  - archive/label actions if included
- Add real Gmail send only after explicit OAuth scope/config review.
- Add real calendar write only after explicit OAuth scope/config review.
- Add user-visible warnings for destructive actions such as delete/unsubscribe.
- Make execution idempotent: refreshing or double-clicking must not send twice.

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

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Mock execution tests pass for supported action types.
- Final confirmation UI is present for external writes.
- Approved actions execute once and only once.
- Audit trail is visible.
- Real provider write scopes are documented before use.
