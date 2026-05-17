# Phase 13 — Stabilization, Real-Data Smoke Testing, and Regression Cleanup

## Objective

Stabilize the overnight Phase 06-12 implementation before adding more features. Copilot implemented a large amount of functionality quickly, much of it with mocked providers and automated tests only. This phase is a deliberate quality gate.

The goal is to prove that the app works against Rohan's real local Gmail data, real SQLite migrations, real browser workflows, and real user expectations before wiring live AI, live outbound execution, or production connectors.

## Required implementation

- Run and document a full local reset, migration, and startup test from a clean database.
- Run and document an upgrade test from an existing pre-Phase-06 database if one is available.
- Smoke-test every major page from the browser:
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
- Verify that queue filters and reviewed/noise status progression behave correctly with real Gmail data.
- Verify that historical backfill advances through Gmail pages and document how many messages each click or run fetches.
- Verify that full conversation fetch behaves correctly for multi-person threads.
- Verify that full body storage settings are understandable and do not surprise the user.
- Review all new Phase 06-12 UI for broken links, unclear labels, dead-end buttons, duplicate navigation, and incorrect status wording.
- Run `python -m ruff check .` and `python -m pytest -q`.
- Fix any defects found during the smoke test before moving to live-provider phases.
- Add or update tests for any real bugs found.

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

- `python -m ruff check .` passes.
- `python -m pytest -q` passes.
- The app starts locally with `python -m uvicorn app.main:app --reload`.
- Rohan can complete the smoke-test checklist above using real Gmail data.
- Backfill behavior is documented clearly enough that the user knows what each run does.
- Any defects found during real smoke testing are either fixed or logged as explicit follow-up work.
