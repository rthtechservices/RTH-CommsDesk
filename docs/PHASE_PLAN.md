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

Phases 01 through 17 built the core scaffolding: Gmail ingestion, contact intelligence, full Gmail thread context, AI review packages, sent-mail learning, bulk triage, calendar recommendations, approved execution records, provider status, live Azure OpenAI support, guarded Gmail/Google Calendar external execution seams, and delegated Microsoft Graph Outlook mail read.

The next round should prioritize a functional, intuitive, working local product over adding more connector surfaces. The current target is a useful test-email workflow:

```text
Sync Gmail/Outlook test inboxes
→ identify messages needing attention
→ analyze conversations
→ review proposed actions
→ prepare drafts/calendar/mailbox actions
→ execute approved test actions
→ audit what happened
```

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

## Next round phases

## Phase 18 — Operational Inbox Workflow Smoke and Fast-Path UX

Primary outcome: make the current Gmail, Outlook, AI analysis, review package, draft, and execution pieces usable as one practical daily workflow.

Scope:

- Add or refine a single operational dashboard path from sync to review package to execution.
- Make Gmail and Outlook source items behave consistently in queue/detail views.
- Add obvious source filters and counts.
- Add a process-next style path for reviewing and analyzing backlog items.
- Add a smoke-test page or dashboard panel showing provider/test readiness.
- Keep Outlook send, Outlook calendar, and Teams disabled.

Assigned file: `docs/phases/PHASE_18_OPERATIONAL_INBOX_WORKFLOW_SMOKE.md`.

## Phase 19 — Test Email Execution Enablement

Primary outcome: make outbound execution usable against controlled test recipients and calendars without enabling broad production-risk writes.

Scope:

- Add explicit operational test mode and execution email allowlist settings.
- Streamline Gmail draft/send execution for allowlisted test recipients only.
- Streamline Google Calendar test event/reminder execution.
- Keep immutable execution attempts and audit trails.
- Report exact blockers such as dry-run, missing flags, missing OAuth scopes, token problems, or non-allowlisted recipients.
- Keep Outlook send/calendar and Teams out of scope.

Assigned file: `docs/phases/PHASE_19_TEST_EMAIL_EXECUTION_ENABLEMENT.md`.

## Phase 20 — Inbox Intelligence Quality Pass

Primary outcome: improve AI and rules recommendation quality using concrete realistic email scenarios after the workflow is operational.

Scope:

- Add fixture conversations for client requests, friendly updates, scheduling, reminders, noise, vague action requests, and changed-thread-context cases.
- Improve review-package correction capture.
- Tune prompts and rules against actual failure patterns.
- Improve recommendation evidence and correction controls in review package detail.
- Preserve structured output validation and mock fallback.

Assigned file: `docs/phases/PHASE_20_INBOX_INTELLIGENCE_QUALITY_PASS.md`.

## Later backlog ideas

- Outlook send after Gmail and Google Calendar test execution are proven.
- Outlook calendar read/write after Google Calendar test execution is stable.
- Teams read-only ingestion after Outlook mail read is stable and useful.
- Browser extension for quick triage.
- Mobile-friendly approval console.
- Notification digest.
- Local LLM option for analysis and drafting.
- Vector search over approved reply examples.
- Contact/project/client tagging.
- Reporting dashboard for communication volume, response backlog, noise rate, and automation time saved.
