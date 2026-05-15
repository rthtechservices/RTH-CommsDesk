# Phase 07 — Search, Reporting, and Daily Briefing

## Objective

Turn stored communications into a practical daily workflow. The user should be able to search, review, and get a concise picture of what needs attention.

## Required implementation

- Add search by contact, source, label, status, date, and text snippet.
- Add a daily briefing view.
- Add neglected-contact detection.
- Add waiting-on-me and waiting-on-them concepts if enough data exists.
- Add export or printable summary if straightforward.
- Add tests for search and briefing generation.

## Out of scope

- New connectors.
- Sending, archiving, or deleting messages.
- Production deployment.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- User can search and filter communications.
- Daily briefing shows important, urgent, needs-reply, neglected, and noise-summary sections.
- Briefing logic is explainable and tested.
