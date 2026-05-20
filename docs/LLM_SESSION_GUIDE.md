# LLM Session Guide

This guide is the first file every LLM implementation session must read after `README.md` and `docs/RESUME_HANDOFF.md` when resuming from the Phase 29 pause.

## Mission

Implement one phase of RTH CommsDesk at a time. From Phase 30 onward, phases must be large, operator-facing acceleration sprints. Preserve privacy guarantees, update documentation, and stop for human review.

## Current pause warning

Development is paused after Phase 29. Outlook integration is only half smoke-tested. Phase 30 is Outlook smoke completion and omnichannel planning, not deployment.

Do not resurrect the old Phase 30 release-candidate/deploy plan. It is superseded.

## Required reading order

Before changing code, read:

1. `README.md`
2. `docs/RESUME_HANDOFF.md`
3. `docs/PROJECT_TRACKING.md`
4. `docs/PHASE_PLAN.md`
5. `docs/PHASE_STATUS.md`
6. The assigned file in `docs/phases/`
7. `docs/IMPLEMENTATION_LOG.md`
8. `docs/LESSONS_LEARNED.md`
9. `docs/HELP.md`
10. Relevant source files and tests for the assigned phase

For Phase 30, also read:

- `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md`
- `docs/phases/PHASE_29_OUTLOOK_DRAFT_WRITE_PARITY.md`

## How to determine what is complete

- Review `docs/RESUME_HANDOFF.md` for the current restart point.
- Review `docs/IMPLEMENTATION_LOG.md` from newest to oldest.
- Review the assigned phase file and its checklist.
- Check Git history and open issues/PR comments if available.
- Inspect existing behavior locally rather than guessing.
- Run focused tests for the area being changed before running broad validation.

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

Update `README.md`, `docs/PHASE_PLAN.md`, and `docs/PHASE_STATUS.md` when current status or next-phase direction changes.

## Coding rules

- Keep changes focused to the assigned phase, but make the phase meaningful and complete.
- Prefer practical operator-facing functionality over tiny visibility-only changes.
- Prefer small, testable service functions over large route handlers.
- Add focused tests for behavior changes.
- Use Alembic for schema changes.
- Do not commit generated local databases, OAuth credentials, token files, `.env`, or private message data.
- Do not make local development depend on paid AI credentials.

## Validation rules

- Use focused tests during implementation.
- Run full `python -m pytest -q` at major integration cut points or before final handoff if code changed materially.
- Do not burn time/credits repeatedly running full test suites for docs-only or copy-only changes.
- If tests fail, report exact test names and whether failures are pre-existing or caused by the phase.

## Privacy and safety rules

Never implement or enable these without an explicit assigned phase:

- Sending email or messages.
- Replying automatically.
- Archiving or deleting external messages.
- Scraping private social platforms.
- Storing full message bodies by default.
- Logging full message bodies, OAuth secrets, refresh tokens, or private user content.

External actions must remain gated:

```text
prepare → approve → confirm → execute → audit
```

No hidden live sends. No provider fallback that pretends success. No external-write flags on by default.

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
