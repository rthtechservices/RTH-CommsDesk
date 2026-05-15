# Phase 06 — Additional Notification-Source Ingestion

## Objective

Add a safe local ingestion path for message summaries from notification-style sources that do not have clean APIs.

## Required implementation

- Define a local webhook endpoint for notification summaries.
- Store these records as notification-derived messages.
- Include source channel, sender/display text, timestamp, title, body snippet, and confidence/limitations.
- Add dedupe rules for repeated notifications.
- Add source confidence indicators so the user understands these are not full-fidelity messages.
- Add tests for webhook ingestion and dedupe.
- Document setup and limitations.

## Safety boundary

- Do not scrape private platforms.
- Do not attempt to bypass platform restrictions.
- Do not send or reply to messages through notification sources.
- Do not store more content than needed for triage.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Notification-source ingestion works through mocked/local requests.
- Duplicate notification spam is controlled.
- UI clearly indicates notification-derived items are lower-confidence summaries.
