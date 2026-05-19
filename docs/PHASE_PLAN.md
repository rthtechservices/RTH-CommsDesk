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

## Current assessment after overnight Copilot run

Phases 01-12 have been implemented in code and documented. The overnight implementation substantially expanded the app, but many Phase 06-12 features were completed quickly, mostly through mocks, deterministic providers, adapter seams, and automated tests rather than real-provider smoke testing.

The next round should not add another pile of features immediately. It should stabilize, validate, wire real providers deliberately, and consolidate the user workflow into a usable product.

Key risks to address next:

- mocked AI analysis and execution can look complete while still not working with real providers;
- real Gmail/backfill/full-thread behavior needs more browser-based testing on real data;
- Outlook/Teams connectors are adapter-shaped but not fully live-auth wired;
- execution flows are mock-backed and must not be mistaken for real sending/calendar actions;
- the app now has many pages and needs workflow consolidation around review packages and next actions.

## Completed phases

## Phase 01 — Usability and structured feedback loop

Status: completed.

## Phase 02 — Durable Gmail sync and local data reliability

Status: completed.

## Phase 03 — Contact intelligence and relationship-aware triage

Status: completed.

## Phase 04 — Safe draft reply generation and voice profiles

Status: completed.

Known limitation: Phase 04 drafts were not sufficiently context-aware by themselves. Later phases added thread context, review packages, and voice learning, but real-world validation is still required.

## Phase 05 — Gmail conversation context and full-content ingestion

Status: completed.

## Phase 06 — AI summarization and proposed action intelligence

Status: completed.

Known limitation: AI analysis is deterministic/mock by default. Live AI provider wiring and prompt quality evaluation belong in Phase 14.

## Phase 07 — Sent-mail learning, VIP inference, and voice calibration

Status: completed.

Known limitation: learning quality needs real sent-mail smoke testing and likely heuristic tuning.

## Phase 08 — Bulk triage and noise automation

Status: completed.

Known limitation: bulk automation is local candidate generation; external mailbox changes require later approved execution/provider wiring.

## Phase 09 — Calendar availability and scheduling recommendations

Status: completed.

Known limitation: provider integrations are shape/read-only oriented and need real-provider wiring.

## Phase 10 — Approved outbound execution

Status: completed.

Known limitation: execution provider is mock-backed by default. Real external write actions require explicit provider wiring, feature flags, dry-run mode, and careful smoke testing.

## Phase 11 — Microsoft 365 and additional communication connectors

Status: completed.

Known limitation: Outlook/Teams connectors rely on injected Graph-service adapters; full Microsoft OAuth/client wiring remains deployment-specific.

## Phase 12 — Deployment, authentication, and production hardening

Status: completed.

Known limitation: deployment readiness still needs a staging rehearsal and operational policy decisions.

## Phase 13 — Stabilization, real-data smoke testing, and regression cleanup

Status: completed.

Known limitation: Phase 13 smoke-tested deterministic/mock AI and execution provider paths only.

## Phase 14 — Live AI provider integration and prompt quality

Status: completed.

Known limitation: live AI provider calls require environment-provided credentials and model selection; Phase 14 added mock fallback and structured validation but did not smoke-test a real provider credential.

## Next round phases

## Phase 15 — Real provider wiring for Gmail, Calendar, and Microsoft Graph

Primary outcome: turn provider shapes into working live integrations where intentionally enabled.

Scope:

- Audit every connector/provider and classify as live-ready, mock-only, adapter-shape-only, or partially wired.
- Add provider readiness/status page.
- Implement live Gmail execution provider methods behind feature flags.
- Implement live Google Calendar read/write providers behind feature flags.
- Implement or fully document Microsoft Graph OAuth/client setup.
- Add dry-run mode for external writes.
- Keep all external writes disabled unless required configuration and explicit feature flags are present.

Assigned file: `docs/phases/PHASE_15_REAL_PROVIDER_WIRING.md`.

## Phase 16 — Product UX and workflow consolidation

Status: completed.

Primary outcome: turn the expanded feature set into a coherent command center.

Scope:

- Make review packages the central unit of work.
- Create/refine a primary command-center dashboard.
- Show item position, summary, recommendation, confidence, context, draft/action payload, and approval controls in one workflow.
- Reduce fragmented navigation and dead-end pages.
- Clearly distinguish local-only actions from external write actions.
- Add empty states, error states, and batch-friendly controls.

Assigned file: `docs/phases/PHASE_16_PRODUCT_UX_AND_WORKFLOW_CONSOLIDATION.md`.

## Phase 17 — Microsoft Graph delegated OAuth and Outlook mail smoke

Status: completed.

Primary outcome: prove read-only Outlook mail ingestion works through delegated Microsoft Graph OAuth before any Microsoft send, calendar, or Teams write/read expansion.

Scope:

- Add delegated Microsoft Graph OAuth for local development with a local token file.
- Preserve the existing app-only Graph client seam.
- Add sanitized `POST /api/graph/test` diagnostics.
- Sync Outlook mail read-only through Graph `/me/messages` or `/users/{MICROSOFT_ACCOUNT}/messages`.
- Normalize Outlook messages into the existing message/thread model.
- Keep Outlook send, Outlook Calendar, and Teams disabled/not implemented.

Assigned file: `docs/phases/PHASE_17_MICROSOFT_GRAPH_DELEGATED_OAUTH_OUTLOOK_MAIL.md`.

## Later backlog ideas

- Browser extension for quick triage.
- Mobile-friendly approval console.
- Notification digest.
- Local LLM option for analysis and drafting.
- Vector search over approved reply examples.
- Contact/project/client tagging.
- SLA-like reminders for important contacts.
- Natural-language command bar, e.g. "show me everything from Michael that I owe a response to".
- Reporting dashboard for communication volume, response backlog, noise rate, and automation time saved.
