# LLM Session Guide

This guide is the first file every LLM implementation session must read.

## Mission

Implement one phase of RTH CommsDesk at a time. Keep scope tight, preserve privacy guarantees, update documentation, and stop for human review.

## Required reading order

Before changing code, read:

1. `README.md`
2. `docs/PROJECT_TRACKING.md`
3. `docs/PHASE_PLAN.md`
4. The assigned file in `docs/phases/`
5. `docs/IMPLEMENTATION_LOG.md`
6. `docs/LESSONS_LEARNED.md`
7. `docs/HELP.md`
8. Relevant source files and tests for the assigned phase

## How to determine what is complete

- Review `docs/IMPLEMENTATION_LOG.md` from newest to oldest.
- Review the assigned phase file and its checklist.
- Check Git history and open issues/PR comments if available.
- Run the test suite before making broad assumptions.
- Inspect existing behavior locally rather than guessing.

## How to document completion

At the end of the session, update `docs/IMPLEMENTATION_LOG.md` with:

- Date/time if known.
- Phase number and title.
- Summary of completed work.
- Files changed.
- Tests run and results.
- Manual smoke tests run and results.
- Known issues or incomplete items.
- Recommended next actions.

Update `docs/LESSONS_LEARNED.md` with durable gotchas or project rules discovered during the work.

Update `docs/HELP.md` for user-visible features only. Keep it clear, short, and practical.

## Coding rules

- Keep changes focused to the assigned phase.
- Prefer small, testable service functions over large route handlers.
- Add tests for behavior changes.
- Preserve the Gmail read-only posture.
- Do not add new external services unless the phase explicitly asks for them.
- Keep the deterministic classifier understandable and auditable.
- Use Alembic for schema changes.
- Do not commit generated local databases, OAuth credentials, token files, or private message data.

## Privacy and safety rules

Never implement or enable these without an explicit future phase:

- Sending email or messages.
- Replying automatically.
- Archiving or deleting external messages.
- Scraping private social platforms.
- Storing full message bodies by default.
- Logging full message bodies, OAuth secrets, refresh tokens, or private user content.

## Session completion response template

When finished, report:

```text
Phase completed: <phase number/title>
Summary: <brief summary>
Tests: <command and result>
Smoke tests: <manual checks and result>
Docs updated: <files>
Known issues: <bullets>
Next recommended phase: <phase number/title>
```

Do not begin the next phase in the same session unless explicitly instructed after human review.
