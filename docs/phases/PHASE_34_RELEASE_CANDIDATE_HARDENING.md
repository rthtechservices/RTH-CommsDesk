# Phase 34 — Daily-Use Release Candidate Hardening

## Goal

Prepare the first daily-use release candidate only after Outlook smoke and omnichannel channel work have reached a stable baseline.

This replaces the old Phase 30 deployment/release-candidate idea.

## Prerequisites

- Phase 30 Outlook smoke completed.
- Phase 31 omnichannel foundation completed.
- Phase 32 live adapter direction implemented or consciously deferred with a documented reason.
- Phase 33 messaging review/execution posture completed or consciously deferred with a documented reason.

## Scope

- Freeze release-candidate scope.
- Validate the daily dashboard-led workflow.
- Validate Gmail, Outlook, selected messaging channels, AI, Calendar, cleanup, and execution audit posture.
- Finalize startup, shutdown, backup, restore, and reauthorization guidance.
- Add or improve config sanity checks.
- Ensure `.env.example` is safe and accurate.
- Remove dead routes, broken buttons, duplicate navigation, and JSON 404s from web UI flows.
- Confirm provider statuses distinguish available, disabled, not implemented, misconfigured, dry-run, and failed.
- Confirm backups include SQLite and exclude secrets/tokens by default.
- Confirm external write actions remain gated.
- Produce a concise daily-use runbook.

## Release-candidate checklist

- Dashboard can drive daily work.
- Sync/channel status is obvious.
- Provider readiness is explicit.
- Pending executions are visible.
- Failed/blocked executions are visible.
- Drafts/replies can be reviewed and cleared locally.
- Voice profile/sign-off state is visible.
- Backup and restore posture is documented.
- Token reauthorization steps are documented.
- No external action can run without approval and final confirmation.
- No destructive action is enabled by default.

## Validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for all primary web routes and `/healthz`.

## Acceptance criteria

- Ruff passes.
- Pytest passes or all remaining failures are explicitly accepted with reasons.
- Alembic upgrade passes.
- Route smoke passes.
- Real-data smoke checklist is documented.
- Daily-use runbook is updated.
- Known limitations are explicit.
- First release-candidate tag/version recommendation is documented.

## Status

Planned.
