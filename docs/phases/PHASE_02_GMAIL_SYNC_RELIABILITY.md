# Phase 02 — Durable Gmail Sync and Local Data Reliability

## Objective

Make Gmail ingestion repeatable, safe, and predictable. The user should be able to run sync multiple times without duplicate side effects and understand what happened.

## Required implementation

- Add persistent sync metadata/high-water mark.
- Add a safe manual resync option.
- Improve duplicate handling and thread metadata updates.
- Add sync result diagnostics:
  - fetched count
  - inserted count
  - skipped duplicate count
  - updated thread count
  - errors if any
- Resolve or clearly separate the `init_db()` versus Alembic lifecycle.
- Make local SQLite reset steps explicit and safe.
- Add tests for incremental sync, duplicate protection, and thread metadata updates.

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

- `pytest -q` passes.
- Repeated sync does not create duplicate messages or duplicate attention items.
- Sync status is visible enough for the user to know what happened.
- Local migration/bootstrap process is documented and does not surprise the user.
