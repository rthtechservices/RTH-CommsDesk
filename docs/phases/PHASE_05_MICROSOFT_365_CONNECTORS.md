# Phase 05 — Gmail Conversation Context and Full-Content Ingestion

## Objective

Stop treating isolated snippets as enough context. RTH CommsDesk must understand whole Gmail conversations before it can summarize, recommend actions, or draft credible responses.

The immediate failure this phase should address: if Christian cancels a dinner in a group email thread and Michael replies only "No worries, thanks for the heads up", the app must understand that Michael is replying inside a broader conversation and should usually recommend no response instead of drafting a vague reply to Michael alone.

## Required implementation

- Fetch Gmail thread/conversation data, not only individual inbox items.
- Store clear thread/conversation membership for each message.
- Retrieve all available messages in a Gmail thread when a message is selected or synced.
- Store enough content to understand context using a configurable body policy:
  - metadata_only
  - snippet_only
  - plain_text_body
  - plain_text_body_with_trimmed_quotes
- Extract normalized plain text from Gmail MIME payloads.
- Strip/sanitize HTML before storage or display.
- Preserve sender, recipients, CC, BCC if available, dates, subject, and message order.
- Preserve enough quoted/reply structure or quote markers to understand who said what, while avoiding endless duplicated quote chains where practical.
- Add a conversation timeline on message detail pages.
- Show the current selected message in relation to the full thread.
- Add a manual "fetch full conversation" or equivalent action if full content is not already present.
- Add historical backfill controls so the app can move beyond repeatedly showing the same 100 items.
- Add queue filters for unreviewed, needs reply, important, noise, reviewed, date range, sender/contact, and source.
- Make Reviewed/Noise status remove items from the default active queue so the user can progress through thousands of messages.
- Add sync/backfill diagnostics that show progress through the Gmail backlog.
- Add tests for thread grouping, body extraction, conversation timeline ordering, reviewed/noise queue progression, and historical pagination.

## Product behavior examples

### Group dinner cancellation

Input thread:

- Christian cancels dinner.
- Michael replies: "No worries, thanks for the heads up! ❤️"

Expected Phase 05 result:

- The message detail page shows the full thread timeline.
- The app can see Christian's cancellation and Michael's acknowledgement.
- No draft quality claim is required in this phase, but the stored context must make a later AI phase capable of recommending "no response needed".

### Renewal notice

Input:

- ICBC message says registration is due on a specific date.

Expected Phase 05 result:

- The due date-bearing content is available for later extraction.
- The body text is visible enough for the user to verify the context.

## Out of scope

- AI summarization and recommendation quality improvements beyond making context available.
- Sent-mail learning.
- External send, archive, delete, unsubscribe, or calendar-write behavior.
- Outlook, Teams, SMS, WhatsApp, or Messenger connectors.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- `uvicorn app.main:app --reload` starts successfully.
- Message detail pages can show a Gmail conversation timeline.
- Full thread fetch works through mocked Gmail tests.
- Body extraction is tested for plain text and HTML messages.
- Reviewed/noise items stop dominating the default active queue.
- Historical backfill can fetch beyond the initial 100 messages.
- No external mailbox write behavior is introduced.

## Notes for later phases

Phase 06 should use the full conversation context created here to generate summaries, proposed actions, and better drafts. Phase 07 should use sent-mail learning to calibrate voice and salutation choices.
