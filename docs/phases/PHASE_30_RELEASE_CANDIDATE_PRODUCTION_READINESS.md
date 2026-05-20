# Phase 30 — Release Candidate and Production Readiness

## Goal

Freeze the first daily-use release candidate. Phase 30 is not a feature grab bag. It is the hardening sprint that turns the app into something safe to run every day.

## Scope

- Freeze scope for the first release candidate.
- Validate the operator flow from dashboard to execution audit.
- Finalize startup, shutdown, backup, restore, and reauthorization guidance.
- Add or improve config sanity checks.
- Ensure `.env.example` is safe and accurate.
- Remove dead routes, broken buttons, duplicate navigation, and JSON 404s from web UI flows.
- Confirm provider statuses distinguish available, disabled, not implemented, misconfigured, and failed.
- Confirm backups include the SQLite database and exclude secrets/tokens by default.
- Confirm external write actions remain gated.
- Produce a concise daily-use runbook.

## Release-candidate checklist

- Dashboard can drive daily work.
- Sync status is obvious.
- Provider readiness is explicit.
- Pending executions are visible.
- Failed/blocked executions are visible.
- Drafts can be reviewed and cleared locally.
- Voice profile/sign-off state is visible.
- Backup and restore posture is documented.
- Token reauthorization steps are documented.
- No external action can run without approval and final confirmation.
- No destructive action is enabled by default.

## Acceptance criteria

- Ruff passes.
- Pytest passes.
- Alembic upgrade passes.
- Route smoke passes.
- Real-data smoke checklist is documented.
- Daily-use runbook is updated.
- Known limitations are explicit.
- First release-candidate tag/version recommendation is documented.

## Required validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for all primary web routes and `/healthz`.
