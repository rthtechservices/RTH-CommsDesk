# RTH CommsDesk Project Tracking

This repository is managed as a phased LLM-assisted build. Each LLM session should complete exactly one phase, update the documentation, and stop for human review before the next phase begins.

## Product direction

RTH CommsDesk is intended to become a personal communications triage console for Rohan. The long-term goal is not simply to read email. The goal is to reduce communication overwhelm across channels by identifying what matters, suppressing noise, remembering contact importance, and eventually drafting safe review-only responses in Rohan's preferred voice.

The app must remain privacy-first and auditable. It should store only the data needed to triage communications, make its reasoning visible, and never send, archive, delete, or modify external messages unless a later phase explicitly adds narrowly scoped, reviewed automation.

## Current baseline

The current MVP is Gmail-only and read-only. It can ingest Gmail metadata/snippets, persist sync high-water metadata, avoid duplicate local sync side effects, classify messages with deterministic rules, score attention items, show a basic dashboard, and allow simple corrections such as VIP, noise, requires reply, reviewed, and draft placeholder.

Known rough edges:

- Dashboard is raw and not yet user-friendly.
- Classification labels and reasons are not yet clean enough for regular use.
- Corrections do not yet form a strong structured learning loop.
- Full-body storage is intentionally disabled by default.
- Outlook, Teams, SMS, WhatsApp, Messenger, and Facebook Messenger are not implemented.
- AI-generated replies are not implemented.

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
- Do not add auto-send, archive, delete, or reply behavior without an explicit future phase.
- Do not expand channels during a phase that is not about connectors.
- Do not replace simple deterministic logic with opaque AI-only behavior.
- Do not make schema changes without an Alembic migration.
- Do not leave broken tests.
- Do not make the app depend on external paid services for the local MVP path.

## Definition of done for every phase

A phase is complete only when:

- The requested functionality is implemented.
- `pytest -q` passes, or failures are documented with reasons.
- The app starts with `uvicorn app.main:app --reload`, or startup blockers are documented.
- Documentation has been updated.
- Known limitations and next-step recommendations are recorded.
- No secrets or private message data are committed.

## Phase index

See `docs/PHASE_PLAN.md` for the full roadmap.

- Phase 01 — Usability and structured feedback loop.
- Phase 02 — Durable Gmail sync and local data reliability.
- Phase 03 — Contact intelligence and relationship-aware triage.
- Phase 04 — Safe draft reply generation and voice profiles.
- Phase 05 — Microsoft 365 connectors: Outlook and Teams.
- Phase 06 — Android notification bridge for SMS/WhatsApp/Messenger-style channels.
- Phase 07 — Search, reporting, and daily briefing.
- Phase 08 — Deployment, authentication, and production hardening.
