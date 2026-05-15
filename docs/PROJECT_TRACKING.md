# RTH CommsDesk Project Tracking

This repository is managed as a phased LLM-assisted build. Each LLM session should complete exactly one phase, update the documentation, and stop for human review before the next phase begins.

## Product direction

RTH CommsDesk is intended to become a personal communications operations console for Rohan.

The end goal is not a passive inbox viewer and not a generic draft textbox. The end goal is an assistant-grade workflow that can ingest large volumes of communication, understand conversation context, identify what matters, suppress or automate noise, learn Rohan's communication style from historical sent mail, summarize what happened, recommend the next action, prepare the response or calendar/task action, and execute only after the user approves the proposed outbound action.

Target workflow:

```text
Ingest messages and conversations
→ group by thread/conversation
→ fetch enough content to understand context
→ classify and prioritize
→ summarize conversation state
→ infer whether action is required
→ recommend the next action
→ draft response or prepare calendar/task/noise action
→ present a review package
→ user approves, edits, rejects, snoozes, or later allows execution
```

A mature review package should be able to say things like:

```text
Item 3 of 17
Michael replied in a Gmail dinner thread after Christian cancelled the event.
The reply is only an acknowledgement: "No worries, thanks for the heads up." No response is needed.
Suggested action: mark reviewed.
```

Or:

```text
ICBC says registration is due on 2026-06-12.
Suggested action: create a reminder one week before the due date.
```

Or:

```text
You have never opened messages from this sender and they appear to be marketing.
Suggested action: mark sender as noise and offer unsubscribe review if a safe unsubscribe link is detected.
```

## Automation philosophy

The app should become useful quickly. It should not remain stuck at 100 snippets and manual VIP/noise toggles. Future phases should introduce real intelligence, full conversation context, historical learning, AI summaries, proposed actions, bulk triage, and approved execution.

Automation is allowed when it is explicitly designed, auditable, and reversible where practical. The roadmap should move toward:

- full thread/conversation context, not isolated snippets;
- message body retrieval with careful storage controls;
- sent-mail learning to infer VIPs and writing style;
- AI-assisted summaries and recommendations;
- bulk triage for thousands of old messages;
- noise suppression, labels, unsubscribe review, and deletion candidates;
- calendar-aware scheduling suggestions;
- approved outbound email/calendar execution.

## Current baseline

The current MVP is Gmail-first. It can ingest Gmail metadata/snippets, persist sync high-water metadata, backfill older Gmail pages, fetch full Gmail thread context on demand, avoid duplicate local sync side effects, classify messages with deterministic rules, score attention items, manage contacts and aliases, track relationship-aware importance, and generate local review-only draft suggestions with deterministic/mock voice profiles.

Known rough edges:

- Drafts are not yet context-aware enough and may produce vague, unnatural replies; Phase 05 makes the raw thread context available, but Phase 06 must use it intelligently.
- Full conversation/thread content is fetched manually on selected Gmail conversations, but automatic summarization is not yet implemented.
- Sent-mail learning and calibration inference are now available, but the guidance quality still depends on explicit review/approval and ongoing inference tuning.
- The system does not yet learn enough from Reviewed/Important/Noise feedback to move large queues quickly.
- Historical Gmail backfill and bulk triage pagination are implemented; additional heuristics and approval flows still need tuning for very large (>7,000) inbox cleanup.
- Outlook Calendar/Gmail Calendar availability checks are not yet implemented.
- Approved outbound send/calendar execution is not yet implemented.
- Unsubscribe, archive, label, and delete automations are not yet implemented.

## Operating model

1. A human assigns one phase to an LLM session.
2. The LLM reads `docs/LLM_SESSION_GUIDE.md`, this file, `docs/PHASE_PLAN.md`, the relevant `docs/phases/PHASE_XX_*.md`, `docs/IMPLEMENTATION_LOG.md`, `docs/LESSONS_LEARNED.md`, and `docs/HELP.md`.
3. The LLM implements only that phase.
4. The LLM updates documentation before finishing.
5. The human and reviewer smoke-test the result.
6. The next phase is adjusted if needed.
7. A new LLM session receives the next phase.

## Documentation responsibilities

Every implementation phase must update these files when relevant:

- `docs/IMPLEMENTATION_LOG.md` — what changed, files touched, tests run, smoke-test notes, open issues.
- `docs/LESSONS_LEARNED.md` — gotchas, environment issues, architecture decisions, shortcuts to avoid.
- `docs/HELP.md` — user-facing features and usage instructions, written simply.
- Relevant phase file under `docs/phases/` — mark completed items and add notes.

## Hard rules

- Do not commit OAuth client secrets, token files, private Gmail data, screenshots containing sensitive data, or local SQLite data.
- Do not add external send, archive, delete, unsubscribe, or calendar-write behavior unless the assigned phase explicitly includes that automation.
- When a phase adds external write behavior, require clear user approval, audit records, duplicate-execution protection, and visible execution results.
- Do not expand channels during a phase that is not about connectors.
- Do not replace explainable deterministic logic with opaque AI-only behavior; AI may assist, but decisions must remain visible and reviewable.
- Do not make schema changes without an Alembic migration.
- Do not leave broken tests.
- Do not make the local development path depend on paid AI credentials; use mocks or provider-neutral interfaces where needed.

## Definition of done for every phase

A phase is complete only when:

- The requested functionality is implemented.
- `pytest -q` passes, or failures are documented with reasons.
- The app starts with `uvicorn app.main:app --reload`, or startup blockers are documented.
- Documentation has been updated.
- Known limitations and next-step recommendations are recorded.
- No secrets or private message data are committed.
- New automation has visible status, auditability, and tests.

## Phase index

See `docs/PHASE_PLAN.md` for the full roadmap.

- Phase 01 — Usability and structured feedback loop.
- Phase 02 — Durable Gmail sync and local data reliability.
- Phase 03 — Contact intelligence and relationship-aware triage.
- Phase 04 — Safe draft reply generation and voice profiles.
- Phase 05 — Gmail conversation context and full-content ingestion.
- Phase 06 — AI summarization and proposed action intelligence.
- Phase 07 — Sent-mail learning, VIP inference, and voice calibration.
- Phase 08 — Bulk triage and noise automation.
- Phase 09 — Calendar availability and scheduling recommendations.
- Phase 10 — Approved outbound execution.
- Phase 11 — Microsoft 365 and additional communication connectors.
- Phase 12 — Deployment, authentication, and production hardening.
