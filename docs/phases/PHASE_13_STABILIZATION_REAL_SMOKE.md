# Phase 13 — Stabilization, Real-Data Smoke Testing, and Regression Cleanup

## Objective

Stabilize the overnight Phase 06-12 implementation before adding more features. Copilot implemented a large amount of functionality quickly, much of it with mocked providers and automated tests only. This phase is a deliberate quality gate.

The goal is to prove that the app works against Rohan's real local Gmail data, real SQLite migrations, real browser workflows, and real user expectations before wiring live AI, live outbound execution, or production connectors.

## Status

Completed on 2026-05-16. This phase stayed within stabilization/regression scope and did not add new product workflows.

## Required implementation

- [x] Run and document a full local reset, migration, and startup test from a clean database.
- [x] Run and document an upgrade test from an existing pre-Phase-06 database if one is available.
- [x] Smoke-test every major page from the browser:
  - dashboard
  - message detail
  - full conversation timeline
  - review packages
  - drafts
  - contacts
  - voice calibration
  - bulk triage
  - calendar proposals
  - executions
  - connectors, admin, and auth pages where applicable
- [x] Verify that queue filters and reviewed/noise status progression behave correctly with real Gmail data.
- [x] Verify that historical backfill advances through Gmail pages and document how many messages each click or run fetches.
- [x] Verify that full conversation fetch behaves correctly for multi-person threads.
- [x] Verify that full body storage settings are understandable and do not surprise the user.
- [x] Review all new Phase 06-12 UI for broken links, unclear labels, dead-end buttons, duplicate navigation, and incorrect status wording.
- [x] Run `python -m ruff check .` and `python -m pytest -q`.
- [x] Fix any defects found during the smoke test before moving to live-provider phases.
- [x] Add or update tests for any real bugs found.

## Specific scenarios to test

### Dinner cancellation thread

- Christian cancels dinner.
- Michael replies with an acknowledgement.
- Expected result: full thread context is visible; review package recommends `no_response_needed`; no generic reply is suggested by default.

### ICBC renewal

- ICBC sends renewal or registration due date.
- Expected result: due date is visible; review package proposes a calendar reminder candidate; no calendar event is created externally.

### Bulk triage progression

- Mark a batch as reviewed or noise.
- Expected result: those items leave the default active queue and the app can proceed deeper into the backlog.

### Voice calibration

- Review a known friend/contact.
- Expected result: inferred salutation and tone guidance are visible, editable, and not overly formal.

## Completion notes

- Clean migration validation used a disposable SQLite database and reached Alembic head `0011_connector_source_confidence`.
- Upgrade validation used a disposable database upgraded first to `0005_gmail_conversation_context`, then to `0011_connector_source_confidence`.
- Real Gmail incremental sync fetched 26 messages, inserted 25 local rows, skipped 1 duplicate, and updated 25 threads.
- Real Gmail backfill fetched one Gmail page: 100 messages inserted locally, 97 threads updated, and the persisted `nextPageToken` advanced for the next backfill run.
- Backfill behavior is one Gmail results page per click/run. The maximum page size is `GMAIL_READ_MAX_RESULTS`, default 100.
- Full conversation fetch completed for the dinner-cancellation and renewal smoke examples without external writes.
- Dinner-cancellation analysis produced `no_response_needed` and no draft response.
- Renewal analysis produced `create_calendar_reminder` and no external calendar action.
- Sent-mail learning fetched 200 sent messages and refreshed existing calibration rows.
- Reviewed and noise queue progression were verified with bulk actions, and both smoke mutations were undone through bulk undo.
- A review package status roundtrip to `snoozed` and back to `pending` worked.
- One mock execution record was prepared from a review package to verify execution queue/detail rendering; no execution was approved or confirmed.
- Browser smoke covered dashboard, message details, full conversation timelines, review packages, drafts, contacts, voice calibration, bulk triage, executions, admin, and local-auth routing. A local link scan checked 377 discovered links with no broken local GET links.
- Final `python -m uvicorn app.main:app --reload` startup smoke returned dashboard HTTP 200 on the default local port.
- Fixed `/admin` and auth-enabled `/login` `TemplateResponse` regressions and added regression tests.
- Added dashboard provider/storage status for AI provider, calendar provider, execution provider, and Gmail full-body sync state.

## Out of scope

- Adding new AI providers.
- Real outbound Gmail actions.
- Real Microsoft Graph OAuth.
- Production deployment.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/PHASE_STATUS.md`
- This phase file with completion notes

## Acceptance criteria

- [x] `python -m ruff check .` passes.
- [x] `python -m pytest -q` passes.
- [x] The app starts locally with `python -m uvicorn app.main:app --reload`.
- [x] Rohan can complete the smoke-test checklist above using real Gmail data.
- [x] Backfill behavior is documented clearly enough that the user knows what each run does.
- [x] Any defects found during real smoke testing are either fixed or logged as explicit follow-up work.

## Remaining gaps for later phases

- Live AI provider integration and prompt quality are Phase 14 scope.
- Live Gmail/Calendar/Microsoft external provider wiring remains Phase 15 scope.
- Microsoft Graph live OAuth/client setup remains deployment-specific.
