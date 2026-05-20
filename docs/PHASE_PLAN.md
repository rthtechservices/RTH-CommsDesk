# RTH CommsDesk Phase Plan

This plan tracks focused LLM-assisted delivery. Earlier phases intentionally used small reviewable increments while OAuth, external execution, provider status, and audit safety were still unstable. That phase of the project is over.

Going forward, phases should be larger product acceleration sprints. Avoid tiny single-feature visibility phases. Each sprint should deliver a useful operator-facing capability and only document what materially changed.

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

The next product goal is to make CommsDesk recognizably the operator's assistant, then quickly harden the app for daily use:

```text
Understand the conversation
→ recommend the correct next action
→ reason about dates/times safely
→ draft in Rohan's real voice
→ learn from sent mail and corrections
→ execute only when explicitly approved and safely gated
→ provide one practical smoke/runbook path for daily operation
```

Recent live smoke lessons to address:

- Gmail draft execution works, but draft quality still shows generic placeholders such as `[Your Name]`.
- The assistant should learn stable operator voice traits from sent mail, including recurring sign-off style such as `Cheers, Rohan.` when approved evidence supports it.
- Calendar reasoning must not create reminders or events in the past.
- A message asking to meet on a date with no time should generally become a clarifying reply or an all-day tentative candidate, not an invented timed reminder.
- Phase 19 test-mode and allowlist controls must remain intact while intelligence improves.

## Delivery rule from Phase 21 onward

- Prefer larger practical sprints over tiny incremental phases.
- Keep tests meaningful, not exhaustive for every wording change.
- Keep docs current, not repetitive.
- Do not split UI visibility, smoke checklists, and personalization controls into separate phases when they can ship together.
- Preserve external-write safety controls.
- Stop for review only at useful product checkpoints.

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

## Active phase

No active implementation phase. Phase 25 is complete and ready for human review.

Most recent phase file:

- `docs/phases/PHASE_25_CONTROLLED_LIVE_GMAIL_CLEANUP.md`

## Later acceleration candidates

These should be combined or reordered based on what blocks daily usefulness:

- Daily-use hardening: startup scripts, health checks, backup/reset, token reauth helper guidance, and one-page operator runbook.
- Outlook write implementation only after Gmail/Calendar behavior and voice quality are stable.
- Outlook calendar only after Google Calendar behavior is stable.
- Teams read-only only if it materially improves daily triage.
- Browser/mobile approval console only if desktop workflow is already genuinely useful.
- Search/reporting/analytics only after the inbox/action loop is reliable.
