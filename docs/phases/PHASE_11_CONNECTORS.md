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
