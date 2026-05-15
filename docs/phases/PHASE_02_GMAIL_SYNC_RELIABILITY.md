# Phase 02 — Durable Gmail Sync and Local Data Reliability

## Objective

Make Gmail ingestion repeatable, safe, and predictable. The user should be able to run sync multiple times without duplicate side effects and understand what happened.

## Required implementation

- [x] Add persistent sync metadata/high-water mark.
- [x] Add a safe manual resync option.
- [x] Improve duplicate handling and thread metadata updates.
- [x] Add sync result diagnostics:
  - fetched count
  - inserted count
  - skipped duplicate count
  - updated thread count
  - errors if any
- [x] Resolve or clearly separate the `init_db()` versus Alembic lifecycle.
- [x] Make local SQLite reset steps explicit and safe.
- [x] Add tests for incremental sync, duplicate protection, and thread metadata updates.

## Out of scope

- New connectors.
- UI redesign beyond sync status display.
- AI-generated replies.
- External deployment.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Repeated sync does not create duplicate messages or duplicate attention items.
- [x] Sync status is visible enough for the user to know what happened.
- [x] Local migration/bootstrap process is documented and does not surprise the user.

## Completion notes

Completed on 2026-05-15.

- Added `source_sync_states` for Gmail high-water and last-result diagnostics.
- Added `0003_sync_state_reliability` migration, including a unique attention-item index after deduping any existing duplicate attention rows.
- Normal Gmail sync now uses the persisted high-water mark with a small overlap. Manual "Resync recent" ignores the high-water mark but remains duplicate-safe.
- Repeat sync updates existing local message metadata and recalculates touched thread metadata instead of inserting duplicate messages or attention items.
- Dashboard and `/api/sync/gmail` now expose fetched, inserted, duplicate-skipped, thread-updated, high-water, and error diagnostics.
- Startup uses Alembic migrations instead of direct `create_all()`; reset/setup instructions are documented in `README.md` and `docs/HELP.md`.
- Validation: `python -m pytest -q` passed with 29 tests, and `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8012` returned dashboard HTTP 200.

## Human review checklist

- Run a normal Gmail sync twice and confirm the second run reports duplicates skipped instead of new inserts.
- Use "Resync recent" and confirm message/attention counts do not grow unexpectedly.
- Confirm the dashboard sync status counts are understandable.
- Review local reset instructions before deleting any real local SQLite data.
