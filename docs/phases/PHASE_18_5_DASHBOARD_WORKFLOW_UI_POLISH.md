# Phase 18.5 — Dashboard and Workflow UI Polish

## Objective

Improve the existing operator UI before Phase 19 test-email execution. This phase makes the current workflow clearer, denser, more responsive, and safer to operate without adding new execution capability.

## Scope

- Consolidate the dashboard into compact status, command-center, and source/runtime cards.
- Add green/amber/red/grey status-light treatment for operational, warning/manual/dry-run, blocking, and disabled/not-implemented states.
- Increase usable dashboard width and make the attention queue denser on wide displays while preserving narrow-screen behavior.
- Keep right-side dashboard widgets but make them compact operator widgets instead of a long secondary page.
- Fix message detail timeline/body wrapping so long conversation content remains inside the main column and scrolls within its card.
- Group message detail actions into Message, Conversation/AI, Contact, and Draft/execution sections.
- Hide redundant contact actions based on current contact state.
- Add concise workflow breadcrumb/help text to dashboard, message detail, review packages, executions, provider status, and operational smoke.
- Add configuration guidance panels for provider and operational smoke pages without editing `.env`.

## Out of scope

- No new Gmail send, draft, archive, label, delete, or calendar execution behavior.
- No Outlook send.
- No Outlook calendar.
- No Teams sync/write.
- No direct `.env` editing from the UI.
- No auto-execution.

## Completion notes — 2026-05-19

Status: Completed for human review.

Implemented:

- Added shared UI styling in `app/web/ui.css` with compact panels, status lights, badges, workflow breadcrumbs, configuration cards, and responsive table/layout helpers.
- Reworked the dashboard into consolidated operational status, command-center, and source/runtime cards.
- Made the attention queue denser and more table-like with score, source, sender/contact, subject, recommended action, status/date, and primary actions.
- Reduced sidebar visual weight for Proposed Actions, Ready For Approval, Calendar Candidates, Noise/Unsub Candidates, VIP Contacts, Recent Human Messages, and Suspected Noise.
- Rebuilt message detail layout so timeline/body content wraps and scrolls inside the main content column.
- Grouped message detail actions and made contact actions context-aware:
  - VIP contacts no longer show "Mark Contact VIP".
  - Noise contacts no longer show "Mark Sender as Noise".
  - Reset appears only for VIP/noise contacts.
- Added concise workflow help/breadcrumb text to the required operator pages.
- Added provider and operational configuration guidance snippets while preserving the no-live-edit boundary.
- Kept Microsoft write boundaries visible as disabled/not implemented.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 129 tests.
- `python -m alembic upgrade head` — passed.
- Local Uvicorn route smoke on port 8765 returned HTTP 200 for `/`, `/operational-smoke`, `/providers`, `/review-packages`, `/executions`, `/admin`, and `/healthz`.

Known issues:

- This phase intentionally does not streamline or enable real outbound test execution. That remains Phase 19.
- Provider guidance is copy/paste documentation only; the UI does not edit `.env` or restart the app.

Recommended next actions:

- Human review of Phase 18.5 UI behavior.
- Next recommended phase: Phase 19 — Test Email Execution Enablement.
