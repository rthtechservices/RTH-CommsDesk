# Phase 05 — Gmail Conversation Context and Full-Content Ingestion

Legacy filename note: this file used to describe Microsoft 365 connectors. Phase 05 was reassigned to Gmail conversation context after Phase 04 smoke testing showed draft replies lacked enough thread context.

## Objective

Stop treating isolated Gmail snippets as sufficient context. The app should be able to fetch, store, and display enough Gmail thread history for the next phase to infer what happened and whether any response is needed.

Guiding scenario:

- Christian cancels a dinner in a group email thread.
- Michael replies: "No worries, thanks for the heads up! <3"
- The message detail page must show enough full-thread context for Phase 06 to infer that Christian cancelled dinner, Michael only acknowledged the cancellation, and no response is likely needed.

## Required implementation

- [x] Fetch Gmail thread/conversation data, not just isolated inbox items.
- [x] Store clear thread/conversation membership through Gmail `threadId`.
- [x] Retrieve all available messages in a Gmail thread through a manual full-conversation action.
- [x] Extract normalized plain text from Gmail MIME payloads.
- [x] Strip/sanitize HTML before storage/display.
- [x] Preserve sender, recipients, CC, dates, subject, and message order.
- [x] Preserve quoted/reply structure in normalized text bodies.
- [x] Add a conversation timeline on message detail pages.
- [x] Show the selected message in relation to the full thread.
- [x] Add a manual "fetch full conversation" action if full content is not already present.
- [x] Add historical backfill controls so the app can move beyond repeatedly showing the same 100 items.
- [x] Add queue filters for unreviewed, needs reply, important, noise, reviewed, date range, sender/contact, and source.
- [x] Keep Reviewed/Noise status out of the default active queue.
- [x] Add sync/backfill diagnostics that show progress through the Gmail backlog.
- [x] Add tests for thread grouping, body extraction, conversation timeline ordering, reviewed/noise queue progression, and historical pagination.

## Out of scope

- AI summarization and recommendation quality improvements beyond making context available.
- Sent-mail learning.
- External send, archive, delete, unsubscribe, or calendar-write behavior.
- Outlook, Teams, SMS, WhatsApp, or Messenger connectors.

## Documentation updates required

- [x] `docs/IMPLEMENTATION_LOG.md`
- [x] `docs/LESSONS_LEARNED.md`
- [x] `docs/HELP.md`
- [x] This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] `uvicorn app.main:app --reload` starts successfully.
- [x] Message detail pages can show a Gmail conversation timeline.
- [x] Full thread fetch works through mocked Gmail tests.
- [x] Body extraction is tested for plain text and HTML messages.
- [x] Reviewed/noise items stop dominating the default active queue.
- [x] Historical backfill can fetch beyond the initial 100 messages.
- [x] No external mailbox write behavior is introduced.

## Completion notes

- Implemented on 2026-05-15.
- Validation: `python -m pytest -q` passed with 43 tests.
- Startup smoke: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8028` returned dashboard HTTP 200.
- Next recommended phase: Phase 06 — AI summarization and proposed action intelligence.
