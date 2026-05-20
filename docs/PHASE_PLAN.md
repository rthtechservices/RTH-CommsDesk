# RTH CommsDesk Phase Plan

This plan tracks phased LLM-assisted delivery.

Earlier phases were too small for the cost/credit burn. From this point forward, phases must be acceleration sprints: large, operator-facing chunks that materially move the app toward daily use. Avoid copy-only phase churn, cosmetic-only work, and repeated full-suite test runs when a focused validation pass is enough for the change type.

## Product target

RTH CommsDesk is a local-first communications operations console:

```text
sync Gmail + Outlook + future messaging channels
→ capture full thread/context where APIs permit
→ classify and prioritize
→ summarize and recommend next actions
→ draft in approved voice
→ prepare calendar/cleanup/reply/message actions
→ approve and confirm external changes
→ execute through the correct provider/channel
→ audit every attempt
→ show persistent life-to-date value metrics
```

## Pause / resume checkpoint

Development is paused after Phase 29 because credits are low.

Phase 29 implemented Microsoft Graph write parity, but Outlook integration is only half smoke-tested. The next session must resume with Outlook smoke completion before starting new channel implementation.

Phase 30 is **not** deployment and is **not** release-candidate hardening. The app still needs a decision and implementation path for WhatsApp, Facebook Messenger, Instagram Messaging, and SMS text messages before production readiness.

## Current active / next phase

| Phase | Title | Status |
| --- | --- | --- |
| 30 | Outlook Integration Smoke Completion and Omnichannel Planning | Next |

## Next acceleration phases

| Phase | Title | Outcome |
| --- | --- | --- |
| 30 | Outlook Integration Smoke Completion and Omnichannel Planning | Finish Outlook smoke testing; document exact Graph readiness, scopes, dry-run/live posture, known failures, and the practical channel strategy for WhatsApp/Facebook Messenger/Instagram/SMS. |
| 31 | Omnichannel Connector Foundation Sprint | Add a normalized messaging-channel model and webhook/provider abstraction for WhatsApp, Messenger, Instagram, and SMS-style messages. Ingest safe sample payloads into the existing thread/message/review pipeline with source confidence and provider status. |
| 32 | Messaging Channel Live Adapter Sprint | Implement the first practical live channel adapter(s) based on available accounts/APIs, likely Twilio/Meta Graph or another chosen provider. Include OAuth/token posture, webhook verification, replay-safe ingestion, provider status, and focused tests. |
| 33 | Omnichannel Review and Execution Sprint | Extend review packages, drafts, voice guidance, and execution records for messaging replies where provider APIs allow outbound messaging. Keep all sends gated by prepare → approve → confirm → execute → audit. |
| 34 | Daily-Use Release Candidate Hardening | Only after Outlook smoke and messaging-channel direction are stable: harden startup, backup, reauth, config checks, route smoke, docs, and daily-use runbook for a first release candidate. |

## Phase documents

- `docs/RESUME_HANDOFF.md`
- `docs/phases/PHASE_30_OUTLOOK_SMOKE_AND_OMNICHANNEL_PLANNING.md`
- `docs/phases/PHASE_31_OMNICHANNEL_CONNECTOR_FOUNDATION.md`
- `docs/phases/PHASE_32_MESSAGING_CHANNEL_LIVE_ADAPTERS.md`
- `docs/phases/PHASE_33_OMNICHANNEL_REVIEW_EXECUTION.md`
- `docs/phases/PHASE_34_RELEASE_CANDIDATE_HARDENING.md`

Older endgame documents may still exist for history, but the active plan above supersedes any older Phase 30 deployment/release-candidate language.

## Delivery rules from resume point forward

- Large chunks only. Each phase should deliver an operator-facing capability bundle, not a tiny breadcrumb.
- Outlook smoke completion comes before new channel implementation.
- No deployment/release-candidate work until the messaging-channel strategy is decided and implemented enough to validate.
- Use focused tests for changed behavior; run full suite at major integration cut points.
- Do not create giant test matrices for doc-only or copy-only edits.
- Keep external-provider changes gated, visible, and audited.
- Do not enable destructive or external-write actions by default.
- Microsoft/Meta/SMS outbound actions must follow prepare → approve → confirm → execute → audit.
- Do not add hidden mock fallback that looks like a successful live provider call.
- Do not leak review notes/internal caveats into external drafts/messages.

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
| 27 | Operator Polish and Daily-Use Hardening | Completed |
| 28 | Daily-Use Cutover and Operator Console | Completed |
| 29 | Microsoft Write Cutover and Provider Parity | Implemented / Outlook smoke incomplete |
