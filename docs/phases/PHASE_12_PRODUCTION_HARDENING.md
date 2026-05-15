# Phase 12 — Deployment, Authentication, and Production Hardening

## Objective

Make RTH CommsDesk safe, secure, and maintainable beyond local development.

This phase should happen after the core assistant workflow is useful: conversation context, proposed actions, voice learning, bulk triage, calendar recommendations, approved execution, and connector expansion.

## Required implementation

- Add application authentication.
- Decide and document target database path, such as Azure SQL or another managed database.
- Add environment-specific configuration.
- Add structured logging without sensitive content.
- Add backup and restore guidance.
- Add CI workflow for tests and linting.
- Add deployment documentation.
- Add production security checklist.
- Add secret handling guidance for OAuth credentials and tokens.
- Add data retention controls for stored message bodies, sent examples, and audit records.
- Add admin tools for clearing local cached content without damaging external accounts.

## Security requirements

- Do not log private message bodies, OAuth tokens, or secrets.
- Do not commit local databases or real user message exports.
- Require authentication before exposing the app beyond localhost.
- Protect external write actions behind approval, confirmation, audit, and duplicate-execution safeguards.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- CI runs tests.
- Local development remains usable.
- Deployment steps are clear enough to repeat.
- Secrets are not logged or committed.
- Backup/restore and data retention guidance are documented.

## Completion notes (2026-05-15)

- Added application authentication controls:
  - Web login/logout session auth (`/login`, `/logout`)
  - API token auth via `X-API-Key` or Bearer token
  - Runtime auth configuration validation for non-local environments
- Added environment-specific hardening settings in `app/core/config.py` and `.env.example`.
- Added structured logging with sensitive-value redaction in `app/core/logging_config.py`.
- Added admin retention/cache-control service and routes:
  - `/admin` (web)
  - `/api/admin/retention/run`
  - `/api/admin/cache/clear`
- Added deployment and security docs:
  - `docs/DEPLOYMENT.md`
  - `docs/SECURITY_CHECKLIST.md`
- Added CI workflow (`.github/workflows/ci.yml`) running `ruff` and `pytest`.
- Added tests for auth flow/middleware and retention admin logic.
- Validation result: `python -m ruff check .` and `python -m pytest -q` both passed (75 tests).
