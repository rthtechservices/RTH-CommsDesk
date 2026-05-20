# Phase 27: Operator Polish and Daily-Use Hardening

## Goal

Fix the Phase 26 smoke-test friction in one practical sprint, focused on daily-use reliability, safe external writes, and operator clarity.

## Completed

- Made draft preparation platform-aware. Gmail-originated drafts continue through the guarded Gmail draft lifecycle; Outlook-originated drafts now block before mutation with: "Outlook draft creation is not implemented or not enabled."
- Added local draft lifecycle controls for cancel and soft-delete. Drafts hides cancelled/deleted local records by default and provides Active/Pending, Created/Completed, Cancelled, Failed, and All filters.
- Updated Executions to default to pending work with Pending, Executed, Failed, Cancelled/Blocked, and All tabs with counts. Completed execution records remain accessible and immutable.
- Repaired Voice Calibration actions so Create New Profile and Import Sent Mail Samples return HTML 200 pages instead of raw JSON 404 responses.
- Improved Assistant Profile empty-state usefulness with readiness, active voice-profile state, sign-off/guidance counts, profile-management links, and local-only preview.
- Completed local backup contents: SQLite database, redacted config snapshot, DB-contained operational data, `.env.example`, and docs. OAuth tokens and `.env` are excluded by default behind explicit false-by-default flags.
- Cleaned navigation by enlarging the global nav, highlighting the current page, and reducing duplicate page-level nav/action bars.
- Cleaned the dashboard Start Here Today row to daily operator actions: Sync Gmail, Sync Outlook, Process next, Review packages, Executions, and Run smoke.

## Safety Boundaries

- No Outlook send, Outlook calendar write, or Teams write was enabled.
- No hidden mock fallback was added.
- No destructive or external-write action is enabled by default.
- The existing prepare -> approve -> confirm -> execute -> audit lifecycle remains intact.
- Operational test mode, allowlist checks, feature flags, readiness checks, approval, final confirmation, and audit boundaries remain in force.
- Cancel/delete draft controls are local-only and do not delete provider-side Gmail or Outlook drafts.

## Validation

- `python -m pytest tests/test_phase_27_operator_polish.py -q`
- `python -m ruff check .`
- `python -m pytest -q`
- `python -m alembic upgrade head`
- Route smoke across dashboard, drafts, executions, voice, assistant, admin, providers, review packages, operational smoke, and health routes.

## Known Limitations

- Outlook draft creation is still not implemented or enabled; the app blocks clearly before creating a Gmail draft execution for Outlook-originated mail.
- Outlook send, Outlook calendar write, and Teams write remain disabled/not implemented.
- Import Sent Mail Samples depends on sent-mail learning prerequisites and reports config-required state through HTML when unavailable.
- Backups exclude OAuth tokens and `.env` by default; including them requires explicit local opt-in.
