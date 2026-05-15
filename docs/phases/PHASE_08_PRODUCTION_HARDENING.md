# Phase 08 — Deployment, Authentication, and Production Hardening

## Objective

Make RTH CommsDesk safe and maintainable beyond local development.

## Required implementation

- Add application authentication.
- Decide and document target database path, such as Azure SQL or another managed database.
- Add environment-specific configuration.
- Add structured logging without sensitive content.
- Add backup and restore guidance.
- Add CI workflow for tests and linting.
- Add deployment documentation.
- Add production security checklist.

## Out of scope

- New end-user features unrelated to deployment.
- Sending, archiving, or deleting external messages unless a future reviewed phase explicitly allows it.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- CI runs tests.
- Secrets are not logged or committed.
- Deployment steps are clear enough to repeat.
- Local development remains usable.
