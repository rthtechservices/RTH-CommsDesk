# Phase 24 — Mailbox Cleanup Live Hardening, Real-Inbox Smoke, and Operator Trust Pass

## Objective

Harden the Phase 23 mailbox cleanup workflow for safe daily use against real synced Gmail inbox data.

This phase is a hardening pass, not a broad feature sprint.

Primary goals:

- Real-inbox smoke path for mailbox cleanup with non-destructive defaults.
- Lightweight operational readiness checks for mailbox cleanup.
- Clear operator trust copy in cleanup UI and dashboard counts.
- Conservative sender scoring/protection tuning.
- Cleanup execution payload/audit hardening.
- Keep Outlook write planning-only and disabled.

## Hard safety boundaries preserved

- No Outlook send implementation.
- No Outlook calendar write implementation.
- No Teams write implementation.
- No Microsoft Graph write calls added.
- No permanent Gmail delete behavior.
- No direct Gmail mutations from mailbox cleanup pages.
- Prepare -> approve -> confirm -> execute -> audit preserved.
- Dry-run, operational test mode, provider flags, and test policy gates preserved.
- No hidden mock fallback for live provider failures.

## Completed scope

### 1) Real-inbox mailbox cleanup smoke script

Added:

- `scripts/smoke-mailbox-cleanup.ps1`

Script behavior:

- Activates local `.venv` when available.
- Optional Alembic upgrade via `-RunMigrations`.
- Checks Gmail sync status and guides operator, with optional read-only sync/backfill switches.
- Calls mailbox cleanup refresh endpoint (`POST /api/mailbox-cleanup/refresh`).
- Reads mailbox cleanup summary endpoint (`GET /api/mailbox-cleanup/summary`).
- Prints required summary counts:
  - total cleanup candidates
  - high-confidence candidates
  - protected candidates
  - Gmail label-capable candidates
  - Gmail archive-capable candidates
  - delete candidates
  - blocked candidates
- Prints local URL for `/bulk-triage/mailbox-cleanup`.
- Prints cleanup dry-run/live/blocked posture.
- Explicitly states it does not perform external Gmail cleanup writes.

### 2) Operational smoke / readiness extension (lightweight)

Extended readiness data without full mailbox scans:

- Added mailbox cleanup readiness details to `operational_smoke_status`.
- Added cleanup execution posture (`blocked`/`mock`/`dry_run`/`live`) as shared logic.
- Added mailbox cleanup test readiness signal under Phase 19 readiness card.
- Added `/bulk-triage/mailbox-cleanup` to route smoke path lists.

Extended persisted smoke checks (`operational_smoke_runner`) with lightweight checks:

- mailbox cleanup table existence
- mailbox cleanup candidate count query readiness with elapsed time
- Gmail cleanup posture + provider state

### 3) UI trust and ergonomics pass

Updated:

- `app/web/templates/mailbox_cleanup.html`
- `app/web/templates/mailbox_cleanup_detail.html`
- `app/web/templates/dashboard.html`
- `app/web/templates/operational_smoke.html`

Improvements:

- Explicit safety guardrails and non-automatic mutation language.
- Clearer recommendation/protection rationale copy.
- Better visibility into blocked/protected/delete candidate counts.
- Start Here Today cleanup counts stay visible even at zero.
- Cleanup readiness/posture visible on operational smoke page.

### 4) Candidate quality tuning

Updated `app/services/mailbox_cleanup_service.py`:

- Cleanup rollups now focus on Gmail source rows for this workflow.
- Added stronger protection conditions:
  - client-work messages protect sender
  - recent human-personal messages protect sender
- High-confidence cleanup now requires repeated low-value evidence.
- Moderate confidence prefers label-only.
- Delete candidate marking is stricter:
  - requires very high confidence
  - requires repeated volume threshold
- Added case-insensitive sender matching for cleanup message id collection.

### 5) Execution payload / provider audit hardening

Updated:

- `app/services/execution_service.py`
- `app/services/external_provider_clients.py`
- `app/services/execution_test_policy.py`

Hardening changes:

- Cleanup payload routing fails closed for unsupported `cleanup_mode`.
- Gmail cleanup batch provider fails closed for unsupported modes.
- Label-based cleanup modes require explicit `cleanup_label_name`.
- Cleanup batch execution is now explicitly represented in execution test policy readiness checks.
- Cleanup execution readiness returns clear blocked reasons and required flags.

### 6) Flaky test triage

Phase 24 implementation and focused tests did not expose an unrelated flaky test.

Final full-suite run outcome is recorded in `docs/IMPLEMENTATION_LOG.md` for follow-up.

## Files updated in this phase

- `app/services/mailbox_cleanup_service.py`
- `app/services/execution_service.py`
- `app/services/external_provider_clients.py`
- `app/services/execution_test_policy.py`
- `app/services/operational_status_service.py`
- `app/services/operational_smoke_runner.py`
- `app/api/routes.py`
- `app/web/routes.py`
- `app/web/templates/mailbox_cleanup.html`
- `app/web/templates/mailbox_cleanup_detail.html`
- `app/web/templates/dashboard.html`
- `app/web/templates/operational_smoke.html`
- `scripts/smoke-mailbox-cleanup.ps1`
- `tests/test_mailbox_cleanup.py`
- `tests/test_execution_test_policy.py`
- `tests/test_phase_22_daily_operations.py`
- `tests/test_operational_workflow.py`
- `README.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `docs/phases/PHASE_24_MAILBOX_CLEANUP_LIVE_HARDENING.md`

## Validation target for phase close

- `python -m ruff check .`
- `python -m pytest -q`
- `python -m alembic upgrade head`

Route smoke target:

- `/`
- `/operational-smoke`
- `/providers`
- `/review-packages`
- `/executions`
- `/bulk-triage`
- `/bulk-triage/mailbox-cleanup`
- `/contacts`
- `/drafts`
- `/voice-calibration`
- `/assistant-profile`
- `/admin`
- `/healthz`
