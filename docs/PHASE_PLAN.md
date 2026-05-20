# RTH CommsDesk Phase Plan

This plan tracks focused LLM-assisted delivery. Earlier phases used small reviewable increments while OAuth, provider status, execution safety, and audit trails were still unstable. That era is done.

Going forward, phases are large acceleration sprints. The project is now in the endgame track documented in `docs/ENDGAME_ROADMAP.md`.

## Product target

RTH CommsDesk is a local-first communications operations console:

```text
sync Gmail + Outlook
→ capture full thread context
→ classify and prioritize
→ summarize and recommend next actions
→ draft in approved voice
→ prepare calendar/cleanup/reply actions
→ approve and confirm external changes
→ execute through the correct provider
→ audit every attempt
```

## Current active phase

| Phase | Title | Status |
| --- | --- | --- |
| 27 | Operator Polish and Daily-Use Hardening | In progress |

Phase 27 is expected to fix the Phase 26 smoke-test friction: platform-aware drafts, draft lifecycle controls, execution filtering, repaired Voice/Assistant routes, complete local backups, and navigation/dashboard cleanup.

## Remaining endgame phases

| Phase | Title | Outcome |
| --- | --- | --- |
| 28 | Daily-Use Cutover and Operator Console | One dashboard-led morning workflow: readiness, sync, process-next, local review actions, live smoke, backup/restore verification, and reauth guidance. |
| 29 | Outlook Draft Write and Cross-Provider Parity | Safe Outlook draft creation only, behind explicit flags and approval/confirmation. Outlook send/calendar/Teams write remain parked. |
| 30 | Release Candidate and Production Readiness | Scope freeze, hardening, route smoke, runbook, config sanity, backup/restore/reauth guidance, and first daily-use release candidate. |

## Phase documents

- `docs/ENDGAME_ROADMAP.md`
- `docs/phases/PHASE_28_DAILY_USE_CUTOVER_OPERATOR_CONSOLE.md`
- `docs/phases/PHASE_29_OUTLOOK_DRAFT_WRITE_PARITY.md`
- `docs/phases/PHASE_30_RELEASE_CANDIDATE_PRODUCTION_READINESS.md`

## Delivery rule

- No cosmetic-only phases.
- No tiny visibility-only phases.
- No broad new side quests before release candidate.
- Keep focused tests, not giant test matrices.
- Keep docs useful and current.
- Keep external-provider changes gated, visible, and audited.

## Completed phases

| Phase | Title | Status |
| --- | --- | --- |
| 01 | Usability and structured feedback loop | Completed |
| 02 | Durable Gmail sync and local data reliability | Completed |
| 03 | Contact intelligence and relationship-aware triage | Completed |
| 04 | Safe draft reply generation and voice profiles | Completed |
| 05 | Gmail conversation context and full-content ingestion | Completed |
| 06 | AI summarization and proposed action intelligence | Completed |
| 07 | Sent-mail learning, VIP inference, and voice calibration | Completed |
| 08 | Bulk triage and noise automation | Completed |
| 09 | Calendar availability and scheduling recommendations | Completed |
| 10 | Approved outbound execution | Completed |
| 11 | Microsoft 365 and additional communication connectors | Completed |
| 12 | Deployment, authentication, and production hardening | Completed |
| 13 | Stabilization, real-data smoke testing, and regression cleanup | Completed |
| 14 | Live AI provider integration and prompt quality | Completed |
| 15 | Real provider wiring for Gmail, Calendar, and Microsoft Graph | Completed |
| 16 | Product UX and workflow consolidation | Completed |
| 17 | Microsoft Graph delegated OAuth and Outlook mail smoke | Completed |
| 18 | Operational inbox workflow smoke and fast-path UX | Completed |
| 18.5 | Dashboard and workflow UI polish | Completed |
| 18.6 | Visual design system and dashboard polish | Completed |
| 18.7 | Interaction hierarchy, triage ergonomics, and RTH palette alignment | Completed |
| 19 | Test email execution enablement | Completed |
| 20 | Assistant Intelligence, Voice, and Calendar Reasoning Quality | Completed |
| 21 | Product Acceleration Sprint | Completed |
| 22 | Daily Operations Hardening and Persistent Smoke Sprint | Completed |
| 23 | Mailbox Cleanup, Sender Noise Automation, and Outlook Write Planning | Completed |
| 24 | Mailbox Cleanup Live Hardening, Real-Inbox Smoke, and Operator Trust Pass | Completed |
| 25 | Controlled Live Gmail Cleanup Execution and Recovery | Completed |
| 26 | Bulk Triage Live Smoke and Execution Verification | Completed / smoke-reviewed |
