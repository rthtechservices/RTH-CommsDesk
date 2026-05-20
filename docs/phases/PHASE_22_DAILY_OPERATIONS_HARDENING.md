# Phase 22 — Daily Operations Hardening and Persistent Smoke Sprint

## Objective

Move RTH CommsDesk from feature-complete enough to inspect to usable every day without babysitting.

This phase intentionally combines startup, persistent smoke, backup, OAuth reauthorization guidance, provider readiness, and daily operator workflow into one sprint.

## Scope

- Persist sanitized operational smoke runs and per-check results.
- Add an operational smoke runner that never performs external writes by default.
- Add smoke run API endpoints and web smoke history/detail pages.
- Add local backup service, admin backup API, and admin UI.
- Add Windows scripts for startup, smoke, backup, and OAuth/token reauthorization.
- Improve provider readiness guidance with exact reauth commands and required scopes.
- Add a dashboard "Start Here Today" lane for morning operation.
- Document the fast local live-data workflow.
- Preserve Gmail/Calendar execution gates and keep Outlook send, Outlook Calendar write, and Teams disabled/not implemented.

## Implementation notes

- `OperationalSmokeRun` and `OperationalSmokeCheck` store only operational metadata, booleans, status, counts, sanitized summaries, and sanitized payload fragments.
- Smoke checks include routes, providers, AI readiness, Graph delegated auth readiness, Gmail/Calendar readiness, execution audit counts, voice memory counts, database/Alembic health, backup readiness, sync state, token guidance, and Microsoft write boundaries.
- Smoke runner default behavior is non-destructive. It does not create Gmail drafts, send email, write calendar events, archive/label/delete mail, or mutate external providers.
- Backup archives include local SQLite, `.env.example`, and key docs. They exclude `.env`, OAuth token files, and client secrets by default.

## Acceptance checklist

- [x] `/operational-smoke` can run and persist a smoke run.
- [x] Recent smoke history is visible.
- [x] Smoke detail is sanitized and includes per-check status/next action.
- [x] Dashboard has a daily "Start Here Today" lane.
- [x] `/admin` can create a local backup that excludes secrets/tokens.
- [x] Startup, smoke, backup, and reauth PowerShell scripts exist and are documented.
- [x] Provider blockers give exact next-action commands and required scopes.
- [x] Smoke runner does not perform external writes by default.
- [x] Gmail/Calendar execution gates remain intact.
- [x] Outlook send, Outlook calendar write, and Teams remain disabled/not implemented.

## Validation

Completed:

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Results:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 234 tests.
- `python -m alembic upgrade head` — passed.

Route smoke required:

```text
/
/operational-smoke
/providers
/review-packages
/executions
/bulk-triage
/contacts
/drafts
/voice-calibration
/assistant-profile
/admin
/healthz
```

Route smoke result: all listed routes returned HTTP 200 via TestClient.
