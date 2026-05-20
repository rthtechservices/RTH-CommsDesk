# RTH CommsDesk Phase Plan

This plan breaks the build into bounded phases suitable for separate LLM sessions. Each session should complete one phase, update documentation, and stop.

## Product target

RTH CommsDesk is an assistant-grade communications operations console. It should not be limited to a feed of snippets and manual VIP/noise buttons.

The intended end-state is:

```text
High-volume communication ingestion
→ full thread/conversation context
→ AI-assisted summaries and recommendations
→ historical learning from sent mail and user corrections
→ bulk triage and noise automation
→ calendar-aware scheduling recommendations
→ user-approved outbound execution
```

Every phase should move toward useful automation and insight while keeping actions explainable, auditable, and under explicit user control when external systems are modified.

## Current direction

Phases 01 through 20 built the operational foundation: Gmail ingestion, Outlook mail read through delegated Graph, contact intelligence, full Gmail thread context, Azure OpenAI analysis, review packages, sent-mail learning, bulk triage, calendar recommendations, approved execution records, provider/operational smoke status, a dark command-center UI, an operational test-mode lane for controlled Gmail/Calendar execution, and the first assistant-quality pass for voice, calendar reasoning, and teachable recommendations.

The next product goal is not to add more connectors. The next product goal is to make CommsDesk become recognizably the operator's assistant:

```text
Understand the conversation
→ recommend the correct next action
→ reason about dates/times safely
→ draft in Rohan's real voice
→ learn from sent mail and corrections
→ execute only when explicitly approved and safely gated
```

Recent live smoke lessons to address next:

- Gmail draft execution works, but draft quality still shows generic placeholders such as `[Your Name]`.
- The assistant should learn stable operator voice traits from sent mail, including recurring sign-off style such as `Cheers, Rohan.` when approved evidence supports it.
- Calendar reasoning must not create reminders or events in the past.
- A message asking to meet on a date with no time should generally become a clarifying reply or an all-day tentative candidate, not an invented timed reminder.
- Phase 19 test-mode and allowlist controls must remain intact while intelligence improves.

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

## Next phases

## Phase 21 — Voice Memory and Assistant Personalization Console

Primary outcome: turn voice learning from hidden inference into a visible, editable personalization system.

Scope:

- Add an Assistant Profile / Voice Memory page.
- Show approved global writing traits, recurring sign-off, tone preferences, avoided phrases, and relationship-specific overrides.
- Allow approving, rejecting, editing, and disabling learned traits.
- Show evidence counts and recent examples without exposing full private sent-mail bodies unnecessarily.
- Add a draft preview tool: given a sample context, show how current voice memory changes the draft.
- Keep all outbound execution gated by Phase 19 controls.

Assigned file to create later: `docs/phases/PHASE_21_VOICE_MEMORY_ASSISTANT_PERSONALIZATION.md`.

## Phase 22 — Live Operational Smoke and Regression Harness

Primary outcome: make repeated real-provider smoke testing safe, scripted, and auditable.

Scope:

- Add a manual smoke checklist page or CLI/script for Gmail draft, Gmail send dry-run, calendar dry-run/live test event, Outlook sync, Azure AI test, and route smoke.
- Add disposable test artifact naming conventions, e.g. `CommsDesk Test - Safe to Delete`.
- Add one-click cleanup guidance for test calendar events/drafts where feasible without destructive automation.
- Persist smoke results locally for operator review.
- Keep live sends/drafts/calendar writes test-mode and allowlist gated.

Assigned file to create later: `docs/phases/PHASE_22_LIVE_OPERATIONAL_SMOKE_HARNESS.md`.

## Phase 23 — Outlook Mail Draft/Send Planning, Not Implementation

Primary outcome: prepare for Microsoft write support without adding it prematurely.

Scope:

- Audit Graph delegated permissions and app registration needs for Outlook draft/send.
- Design the Outlook execution provider seam to mirror Gmail's test-mode and allowlist controls.
- Document payload shape, provider status, error handling, and audit requirements.
- Add disabled UI guidance only. Do not implement Outlook send yet.

Assigned file to create later: `docs/phases/PHASE_23_OUTLOOK_WRITE_PLANNING_ONLY.md`.

## Phase 24 — Production Readiness and Packaging Review

Primary outcome: decide how this local-first app should be run day-to-day without becoming fragile.

Scope:

- Review local service startup options, backups, token handling, logging, retention, and database maintenance.
- Add operator runbook for normal use, smoke testing, reset, reauthorization, and troubleshooting.
- Confirm `.env` editing remains manual unless an explicit config-management phase is opened.
- Confirm secrets and token files remain local and gitignored.

Assigned file to create later: `docs/phases/PHASE_24_PRODUCTION_READINESS_PACKAGING.md`.

## Later backlog ideas

- Outlook send after Gmail/Calendar intelligence and test execution are stable.
- Outlook calendar read/write after Google Calendar behavior is stable.
- Teams read-only ingestion after Outlook mail read is stable and useful.
- Browser extension for quick triage.
- Mobile-friendly approval console.
- Notification digest.
- Local LLM option for analysis and drafting.
- Vector search over approved reply examples.
- Contact/project/client tagging.
- Reporting dashboard for communication volume, response backlog, noise rate, and automation time saved.
