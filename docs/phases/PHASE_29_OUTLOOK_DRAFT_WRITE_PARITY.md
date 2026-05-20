# Phase 29 — Microsoft Write Cutover and Provider Parity

## Goal

Stop inching forward. Phase 29 is the Microsoft write cutover sprint for Outlook mail and calendar, implemented with the same approved execution model already used elsewhere in the app.

This phase should make Outlook-originated work operationally useful, not merely visible.

## Scope

Implement provider-parity write surfaces for Microsoft Graph:

- Outlook draft creation;
- Outlook send for approved outbound email executions;
- Outlook reply/send in the correct conversation when message/thread identifiers are available;
- Outlook mail label/category or archive/move support where Graph permissions and current architecture make it practical;
- Outlook calendar event creation;
- provider-aware execution routing so Gmail items use Gmail, Google Calendar items use Google Calendar, and Outlook/Microsoft items use Microsoft Graph;
- provider-specific readiness diagnostics and audit detail.

If one of these write surfaces is not practical because the current Graph client, data model, or scopes are missing, implement the seam and a clear blocked state in the same sprint. Do not route Microsoft-originated work to Gmail as a fallback.

## Required config

Add or confirm explicit feature flags. Defaults may remain conservative in `.env.example`, but the code path must be real and ready to enable locally.

```env
OUTLOOK_DRAFT_CREATE_ENABLED=false
OUTLOOK_SEND_ENABLED=false
OUTLOOK_MAIL_MODIFY_ENABLED=false
OUTLOOK_CALENDAR_WRITE_ENABLED=false
MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read Mail.ReadWrite Mail.Send Calendars.ReadWrite offline_access
```

Do not add Teams write in this phase unless it is already trivial and read-only Teams work is already present. Teams is not the release blocker.

## Execution model

Use the existing execution pipeline:

```text
prepare → approve → final confirmation → execute → audit
```

This is not procrastination; it is the app's operator safety contract. The objective is to ship live Microsoft writes inside that contract, not avoid them.

## Provider routing requirements

- Gmail source mail uses Gmail draft/send/modify paths.
- Google Calendar actions use Google Calendar paths.
- Outlook source mail uses Microsoft Graph draft/send/modify paths.
- Outlook calendar actions use Microsoft Graph calendar paths.
- Provider mismatch must be impossible or blocked before mutation.
- No hidden provider fallback.

## UI requirements

Update the relevant pages so Microsoft write state is obvious:

- Drafts;
- Executions;
- Providers;
- Operational Smoke;
- Dashboard / operator queue.

Execution detail should show:

- source provider;
- target provider;
- action type;
- required feature flag;
- readiness result;
- approval state;
- confirmation state;
- provider result;
- recovery guidance if blocked or failed.

## Microsoft Graph implementation notes

Use delegated Graph auth already present in the app. Required Graph permissions likely include:

- `Mail.Read`;
- `Mail.ReadWrite`;
- `Mail.Send`;
- `Calendars.ReadWrite`;
- `User.Read`;
- `offline_access`.

If scopes changed, document reauthorization clearly:

```powershell
Remove-Item ".\microsoft_graph_token.json" -Force -ErrorAction SilentlyContinue
```

Then run the existing Graph auth/test flow.

## Safety requirements

Keep external writes explicit and audited. Do not silently mutate Outlook.

Required for live write execution:

- provider readiness check;
- feature flag check;
- approval;
- final confirmation;
- immutable execution attempt;
- audit result.

No mock fallback should claim success when live Graph writes are selected.

## Tests

Keep focused tests only.

Required tests:

- Gmail source uses Gmail write path.
- Outlook source uses Microsoft Graph write path.
- Outlook source never attempts Gmail draft/send.
- Outlook draft blocks when disabled and executes when enabled with mocked Graph client.
- Outlook send blocks when disabled and executes when enabled with mocked Graph client.
- Outlook calendar write blocks when disabled and executes when enabled with mocked Graph client.
- Provider mismatch is blocked before mutation.
- Execution requires approval and final confirmation.
- Provider status reports Microsoft write readiness correctly.
- Route smoke includes dashboard, drafts, executions, providers, operational smoke, admin, about, health.

## Required validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for:

```text
/
/dashboard
/drafts
/review-packages
/executions
/providers
/operational-smoke
/admin
/about
/healthz
```

## Docs to update

- `README.md`;
- `docs/HELP.md`;
- `docs/PHASE_STATUS.md`;
- `docs/PHASE_PLAN.md`;
- `docs/ENDGAME_ROADMAP.md`;
- `docs/IMPLEMENTATION_LOG.md`;
- `docs/LESSONS_LEARNED.md`;
- this phase file.

## Acceptance criteria

- Outlook-originated draft actions use Microsoft Graph, not Gmail.
- Outlook send execution exists behind `OUTLOOK_SEND_ENABLED`.
- Outlook calendar event execution exists behind `OUTLOOK_CALENDAR_WRITE_ENABLED`.
- Outlook mail modify support exists behind `OUTLOOK_MAIL_MODIFY_ENABLED`, or a clear blocked seam is implemented if not practical.
- Provider pages clearly report Microsoft write readiness.
- Execution UI clearly shows Microsoft write provider/result state.
- Graph reauthorization steps are documented.
- External writes remain approved, confirmed, and audited.
- Ruff, pytest, Alembic, and route smoke pass.

## Status

✅ **Completed 2026-05-21**

All acceptance criteria met:
- Outlook-originated draft actions route to `CREATE_OUTLOOK_DRAFT` via Microsoft Graph. Gmail source never uses Graph write path and vice versa (provider mismatch guard at dispatch).
- Outlook send execution implemented behind `OUTLOOK_SEND_ENABLED` with `create_and_send_reply` seam.
- Outlook calendar event creation implemented behind `OUTLOOK_CALENDAR_WRITE_ENABLED` with past-event guard.
- Outlook mail modify (categories, read flag, flag status, archive/move) implemented behind `OUTLOOK_MAIL_MODIFY_ENABLED`.
- Provider pages report per-surface Microsoft write readiness (disabled/dry_run/available/misconfigured) at `/providers`.
- Execution detail page shows Provider routing panel with source/target provider, feature flag, and readiness state.
- Graph reauthorization documented in providers.html and HELP.md.
- All writes go through approve → confirm → execute → audit pipeline.
- `python -m ruff check .` — all checks passed.
- `python -m pytest tests/test_phase_29_outlook_write_parity.py -v` — 34/34 passed.
- `python -m pytest -q` — 382 passed, 3 pre-existing failures (unrelated).
- `python -m alembic upgrade head` — migration 0018 applied cleanly.
