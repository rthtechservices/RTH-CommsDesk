# Phase 11 — Microsoft 365 and Additional Communication Connectors

## Objective

Expand source coverage after Gmail intelligence, conversation context, proposed actions, and approval flows are useful.

This phase should not distract from the Gmail-first assistant workflow. Add additional sources only after the core communication intelligence loop works.

## Required implementation

- Add Microsoft Graph OAuth/configuration path.
- Add Outlook mail ingestion.
- Add Teams message ingestion if permissions and API shape are clear.
- Normalize Microsoft messages into the existing source/thread/message/review-package model.
- Preserve provider identifiers, thread IDs, timestamps, and source channel.
- Add optional phone notification webhook for SMS/WhatsApp/Messenger-style notification summaries.
- Store notification-derived items as lower-confidence summaries, not full-fidelity messages.
- Add dedupe rules for repeated notifications.
- Add source confidence indicators in the UI.
- Add connector tests with mocked Graph and webhook responses.
- Document required permissions and setup steps.

## Safety boundary

- Do not scrape private platforms.
- Do not attempt to bypass platform restrictions.
- Do not reply through notification-only sources.
- Do not add external write behavior unless routed through the approved execution engine from Phase 10.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Outlook messages can be ingested through mocked tests.
- Notification-source ingestion works through mocked/local requests.
- UI clearly identifies source and confidence level.
- No connector bypasses the proposed-action and approved-execution architecture.

## Completion notes (2026-05-15)

- Added connector adapters:
  - `app/connectors/outlook/client.py`
  - `app/connectors/teams/client.py`
  - `app/connectors/notifications/webhook.py`
- Added `source_channel` and `source_confidence` metadata on `messages` with Alembic migration `0011_connector_source_confidence`.
- Added sync orchestration in `app/services/external_connectors_service.py` and wired API/web routes for Outlook, Teams, and notification webhook ingestion.
- Added UI source filter options and source-confidence display on dashboard/message detail pages.
- Added mocked tests for Outlook ingestion, Teams ingestion, and notification webhook duplicate-safe behavior.
- Validation result: `python -m pytest -q` passed (71 tests).
