# Phase 28 — Daily-Use Cutover and Operator Console

## Goal

Make RTH CommsDesk usable as the daily morning command center. Phase 28 should consolidate the existing capabilities into one fast operator workflow instead of adding more side screens.

## Target flow

```text
Open dashboard
→ check provider readiness
→ sync current mail
→ process next useful item
→ review recommendation and context
→ approve, dismiss, defer, or prepare action
→ execute only after confirmation when an external provider is changed
→ audit result
→ repeat
```

## Scope

Build one strong operator lane:

- unified queue across Gmail, Outlook read items, review packages, drafts, executions, calendar candidates, and cleanup candidates;
- `Process next` action that selects the highest-value actionable item;
- local actions for reviewed, important, noise, dismiss, and defer/snooze;
- prepare actions for draft reply, calendar candidate, and cleanup candidate;
- dashboard readiness panel that shows provider health, sync age, queue counts, pending executions, failed/blocked items, and last backup;
- one-click live smoke harness for safe provider status, route status, and write-readiness posture;
- startup/check script for the known local Windows paths;
- backup verification and restore guidance;
- stale-token/reauth guidance for Gmail, Google Calendar, and Microsoft Graph.

## Safety requirements

Keep the existing external-action lane:

```text
prepare → approve → final confirmation → execute → audit
```

Do not enable new external-write capability by default. Outlook send, Outlook calendar write, and Teams write stay parked.

## Acceptance criteria

- Dashboard has a single practical operator flow.
- `Process next` works from the dashboard.
- Queue counts are visible and useful.
- Provider readiness is explicit.
- Pending/failed/blocked work is easy to find.
- Local dismiss/defer/review actions do not touch external providers.
- External actions remain gated and audited.
- Startup/check script works on the known local paths or gives clear guidance.
- Backup/restore guidance is visible from Admin or Help.
- Focused tests pass.

## Required validation

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
```

Run route smoke for the dashboard, drafts, review packages, executions, bulk triage, assistant, voice, providers, smoke, admin, and health routes.
