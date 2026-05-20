# RTH CommsDesk Project Tracking

This repository is managed as a phased LLM-assisted build. The original rule was one phase per LLM session. That still applies, but the phase size must be larger from Phase 30 onward: each phase should deliver an operator-facing chunk, not one tiny status tweak.

## Current pause point

Development is paused after Phase 29 because credits are low.

Phase 29 implemented Microsoft Graph write parity, but Outlook integration is only half smoke-tested. The next session must resume with Phase 30: Outlook integration smoke completion and omnichannel planning.

Do not deploy next. Do not treat Phase 30 as release-candidate hardening. The app is still missing first-class messaging channels:

- WhatsApp;
- Facebook Messenger;
- Instagram Messaging;
- SMS text messages.

## Product direction

RTH CommsDesk is intended to become a personal communications operations console for Rohan.

The end goal is not a passive inbox viewer and not a generic draft textbox. The end goal is an assistant-grade workflow that can ingest large volumes of communication across email and messaging channels, understand conversation context, identify what matters, suppress or automate noise, learn Rohan's communication style from historical sent mail, summarize what happened, recommend the next action, prepare the response or calendar/task/action, and execute only after approval and final confirmation.

Target workflow:

```text
Ingest messages and conversations
→ group by thread/conversation
→ fetch enough content to understand context
→ classify and prioritize
→ summarize conversation state
→ infer whether action is required
→ recommend the next action
→ draft response or prepare calendar/task/noise/message action
→ present a review package
→ user approves, edits, rejects, snoozes, or confirms execution
→ execute through the correct provider/channel
→ audit every attempt
```

## Acceleration rules

The project took too long and consumed too many credits through small phases. Future work should move faster:

- Build large, practical chunks.
- Avoid visibility-only phases unless they unblock live operation.
- Avoid giant test matrices for documentation/copy-only changes.
- Use focused tests for changed behavior and full suite only at meaningful integration cut points.
- Fix cheap smoke blockers inside the current phase instead of creating another tiny follow-up.
- Keep documentation current enough for the next agent to resume without archaeology.

## Current baseline

The app currently supports or has implemented seams for:

- Gmail read sync/backfill/full-thread fetch;
- Outlook mail read via delegated Microsoft Graph;
- Azure/OpenAI live AI provider with mock fallback;
- deterministic local analysis and review packages;
- voice/sign-off learning and Assistant Profile;
- bulk triage and mailbox cleanup candidates;
- guarded Gmail draft/send/label/archive seams;
- guarded Google Calendar freebusy/write seams;
- Phase 29 Microsoft Graph write seams for Outlook draft/send/mail modify/calendar;
- execution lifecycle with prepare → approve → confirm → execute → audit;
- provider status, operational smoke, persisted smoke history, backup, reauth scripts, and About statistics.

Known rough edges at pause:

- Outlook Phase 29 smoke testing is incomplete.
- Phase 29 reported three pre-existing full-suite failures that need re-checking before broad new work.
- Messaging channels are not first-class yet.
- Teams remains disabled/not implemented.
- External write flags must remain off by default.

## Operating model

1. A human assigns one phase to an LLM session.
2. The LLM reads `README.md`, `docs/RESUME_HANDOFF.md`, `docs/LLM_SESSION_GUIDE.md`, this file, `docs/PHASE_PLAN.md`, the relevant phase file, `docs/IMPLEMENTATION_LOG.md`, `docs/LESSONS_LEARNED.md`, and `docs/HELP.md`.
3. The LLM implements that phase as a large, coherent chunk.
4. The LLM updates documentation before finishing.
5. The human and reviewer smoke-test the result.
6. The next phase is adjusted if needed.
7. A new LLM session receives the next phase.

## Documentation responsibilities

Every implementation phase must update these files when relevant:

- `README.md` — first-read status, current blockers, setup, and next-step posture.
- `docs/RESUME_HANDOFF.md` — only when the pause/resume point changes.
- `docs/IMPLEMENTATION_LOG.md` — what changed, files touched, tests run, smoke-test notes, open issues.
- `docs/LESSONS_LEARNED.md` — gotchas, environment issues, architecture decisions, shortcuts to avoid.
- `docs/HELP.md` — user-facing features and usage instructions.
- `docs/PHASE_PLAN.md` and `docs/PHASE_STATUS.md` — roadmap/status updates.
- Relevant phase file under `docs/phases/` — mark completed items and add notes.

## Hard rules

- Do not commit OAuth client secrets, token files, private Gmail/Outlook/message data, screenshots containing sensitive data, or local SQLite data.
- Do not enable external send/archive/delete/unsubscribe/calendar/message-write behavior by default.
- When a phase adds external write behavior, require clear user approval, final confirmation, audit records, duplicate-execution protection, and visible execution results.
- Do not expand channels during a phase that is not about connectors/channels.
- Do not replace explainable deterministic logic with opaque AI-only behavior; AI may assist, but decisions must remain visible and reviewable.
- Do not make schema changes without an Alembic migration.
- Do not leave broken tests without documenting exact failure names and reasons.
- Do not make local development depend on paid AI credentials.
- Do not scrape private social platforms.

## Definition of done for every phase

A phase is complete only when:

- The requested functionality is implemented or the blocker is documented precisely.
- Focused tests for changed behavior pass.
- Full suite is run at integration cut points or failures are documented with reasons.
- Alembic upgrade passes when schema/config persistence changes are involved.
- The app starts locally or startup blockers are documented.
- Documentation has been updated.
- Known limitations and next-step recommendations are recorded.
- No secrets or private message data are committed.
- New automation has visible status, auditability, and tests.

## Phase index

See `docs/PHASE_PLAN.md` for the active roadmap.

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
- Phase 13 — Stabilization, real-data smoke testing, and regression cleanup.
- Phase 14 — Live AI provider integration and prompt quality.
- Phase 15 — Real provider wiring for Gmail, Calendar, and Microsoft Graph.
- Phase 16 — Product UX and workflow consolidation.
- Phase 17 — Microsoft Graph delegated OAuth and Outlook mail smoke.
- Phase 18 — Operational inbox workflow smoke and fast-path UX.
- Phase 18.5 — Dashboard and workflow UI polish.
- Phase 18.6 — Visual design system and dashboard polish.
- Phase 18.7 — Interaction hierarchy, triage ergonomics, and RTH palette alignment.
- Phase 19 — Test email execution enablement.
- Phase 20 — Assistant Intelligence, Voice, and Calendar Reasoning Quality.
- Phase 21 — Product Acceleration Sprint.
- Phase 22 — Daily Operations Hardening and Persistent Smoke Sprint.
- Phase 23 — Mailbox Cleanup, Sender Noise Automation, and Outlook Write Planning.
- Phase 24 — Mailbox Cleanup Live Hardening, Real-Inbox Smoke, and Operator Trust Pass.
- Phase 25 — Controlled Live Gmail Cleanup Execution and Recovery.
- Phase 26 — Bulk Triage Live Smoke and Execution Verification.
- Phase 27 — Operator Polish and Daily-Use Hardening.
- Phase 28 — Daily-Use Cutover and Operator Console.
- Phase 29 — Microsoft Write Cutover and Provider Parity.
- Phase 30 — Outlook Integration Smoke Completion and Omnichannel Planning.
- Phase 31 — Omnichannel Connector Foundation Sprint.
- Phase 32 — Messaging Channel Live Adapter Sprint.
- Phase 33 — Omnichannel Review and Execution Sprint.
- Phase 34 — Daily-Use Release Candidate Hardening.
