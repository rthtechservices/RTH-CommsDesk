# RTH CommsDesk Roadmap After Phase 29 Pause

## Current position

Development is paused after Phase 29 because credits are low.

Phase 29 implemented Microsoft Graph write parity: Outlook draft creation, Outlook send/reply, Outlook mail modify, and Outlook calendar event creation. All are behind explicit feature flags, provider-aware routing, approval/confirmation/audit, and dry-run posture.

Outlook integration is only half smoke-tested. Treat it as implemented but not operationally trusted until Phase 30 completes smoke testing.

## Important correction

The old roadmap said one phase remained before release candidate. That is no longer accurate.

Phase 30 is not deployment and not release-candidate hardening. The app still needs a practical path for these channels before production readiness:

- WhatsApp;
- Facebook Messenger;
- Instagram Messaging;
- SMS text messages.

## End goal

RTH CommsDesk should be a local-first daily communications console:

1. sync Gmail, Outlook, and selected messaging channels;
2. show one practical operator queue;
3. recommend the next useful action;
4. prepare drafts, replies, calendar actions, cleanup actions, or local review outcomes;
5. require approval and final confirmation before external changes;
6. execute through the correct provider/channel;
7. audit every attempt;
8. provide backup, recovery, and reauth guidance;
9. show persistent life-to-date value metrics from the go-live baseline onward.

## Active next phases

| Phase | Name | Purpose |
| --- | --- | --- |
| 30 | Outlook Integration Smoke Completion and Omnichannel Planning | Finish Outlook smoke testing and decide the practical channel strategy for WhatsApp, Messenger, Instagram, and SMS. |
| 31 | Omnichannel Connector Foundation Sprint | Add normalized inbound messaging-channel foundation and safe sample ingestion for all requested channel families. |
| 32 | Messaging Channel Live Adapter Sprint | Implement the first selected live/test provider adapter(s), webhook verification, replay-safe ingestion, and provider status. |
| 33 | Omnichannel Review and Execution Sprint | Extend review packages, drafting, and guarded execution for messaging replies where provider APIs allow it. |
| 34 | Daily-Use Release Candidate Hardening | Harden startup, backup, reauth, config checks, route smoke, docs, and daily-use runbook after Outlook and messaging work settle. |

## Phase 30 stance

Phase 30 should be a smoke-and-decision sprint, not a timid documentation pass.

It should produce:

- exact Outlook smoke results;
- exact Graph scope/token status;
- fixes for cheap smoke blockers;
- current test failure posture;
- a clear chosen direction for messaging channels;
- adjusted Phase 31 scope if the channel decision changes.

## What not to do immediately

- Do not deploy.
- Do not start production hardening.
- Do not create another tiny Microsoft visibility-only phase.
- Do not run expensive full validation repeatedly for docs-only changes.
- Do not enable external writes by default.
- Do not add Teams unless it materially improves daily triage and does not distract from the requested channels.

## Success state before release candidate

The app is release-candidate ready only when Rohan can open the dashboard, sync current mail/messages, process the next important item, prepare/review/approve an action, execute it safely where configured, recover/audit what happened, and see persistent lifetime value metrics without digging through raw routes or logs.
