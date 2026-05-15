# Phase 08 — Bulk Triage and Noise Automation

## Objective

Make RTH CommsDesk useful for a large backlog, such as 7,000+ emails. The user should be able to process large volumes quickly instead of repeatedly seeing the same small batch.

This phase should introduce bulk triage, queue progression, noise detection, unsubscribe candidates, and safe automation candidates.

## Required implementation

- [x] Add a backlog/bulk triage mode.
- [x] Support pagination and progress tracking across large Gmail history.
- [x] Add queue controls for:
  - unreviewed
  - needs reply
  - important
  - proposed actions
  - noise candidates
  - unsubscribe candidates
  - reviewed
- [x] Ensure reviewed/noise/ignored items leave the default active queue.
- [x] Add bulk actions with clear confirmation and undo where practical:
  - mark reviewed
  - mark noise
  - mark important
  - assign contact relationship
  - approve no-response-needed recommendation locally
- [x] Detect repeated low-value senders and newsletter patterns.
- [x] Detect likely unsubscribe links in stored/sanitized message bodies.
- [x] Generate unsubscribe_review candidates when evidence supports it.
- [x] Detect never-opened, never-replied, or low-engagement sender patterns where Gmail data supports it.
- [x] Generate archive_candidate and delete_candidate records with reasons and confidence.
- [x] Add an automation candidate dashboard that shows what the app recommends and why.
- [x] Require explicit approval before any destructive or external action is executed.
- [x] Add tests for bulk pagination, queue progression, candidate generation, and bulk status updates.

## Product behavior examples

### Repeated marketing sender

Expected result:

- The app identifies the sender as a likely newsletter/marketing source.
- The app explains the evidence.
- The app offers mark_noise and unsubscribe_review as proposed actions.

### Stale low-value messages

Expected result:

- The app can group stale messages by sender/category.
- The app can propose archive_candidate or delete_candidate.
- The app does not delete externally until a later approved execution phase.

## Out of scope

- Actually deleting, archiving, labeling, or unsubscribing in Gmail unless moved to a separate explicitly approved execution subphase.
- Sending email.
- Calendar write actions.
- New communication connectors.

## Documentation updates required

- [x] `docs/IMPLEMENTATION_LOG.md`
- [x] `docs/LESSONS_LEARNED.md`
- [x] `docs/HELP.md`
- [x] This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Backlog mode can progress beyond the first 100 messages.
- [x] Bulk status updates work and are tested.
- [x] Automation candidates are visible with reasons and confidence.
- [x] Reviewed/noise items do not keep resurfacing in the default active queue.
- [x] Unsubscribe candidates can be detected from mocked message bodies.
- [x] No external destructive action is executed without a later approved execution phase.

## Completion notes

Status: completed on 2026-05-15.

Implemented:

- Added bulk triage persistence models for automation candidates and bulk action logs/undo snapshots.
- Added `bulk_triage_service` for paginated backlog retrieval, deterministic candidate generation, bulk action application, and undo.
- Added dashboard bulk-triage link and a dedicated `/bulk-triage` UI with queue controls, pagination, progress stats, candidate panel, and action log undo.
- Added API endpoints for candidate refresh/listing, backlog page retrieval, bulk action apply, and bulk undo.
- Added tests for >100-item pagination, candidate generation heuristics, bulk status update + undo, and no-response-needed bulk approvals.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 59 tests.

Safety boundary confirmed:

- No external archive/delete/unsubscribe/send behavior was added.
- All destructive behavior remains local recommendation or local-status workflow only.
