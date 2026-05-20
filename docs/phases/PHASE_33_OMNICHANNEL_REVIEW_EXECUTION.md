# Phase 33 — Omnichannel Review and Execution Sprint

## Goal

Extend the existing review, draft, voice, and execution lifecycle to messaging channels after inbound channel ingestion is stable.

This phase should make messaging channels useful inside the operator workflow without allowing unreviewed outbound sends.

## Prerequisite

Complete Phase 31 and Phase 32 first.

## Scope

- Extend review packages to support messaging-channel conversations.
- Add channel-aware draft/reply generation where message context is available.
- Apply approved voice guidance while respecting short-message norms.
- Add messaging reply execution records where a provider supports outbound replies.
- Keep all outbound messages behind prepare → approve → confirm → execute → audit.
- Add provider-aware routing so WhatsApp/Messenger/Instagram/SMS replies cannot fall back to email providers.
- Show channel-specific recovery/blocker guidance on execution detail.
- Add operator UI copy distinguishing email drafts from messaging replies.

## Execution model

Outbound messaging must use the existing staged lifecycle:

```text
prepare → approve → final confirmation → execute → audit
```

No one-click send. No automatic reply. No hidden provider fallback.

## Provider routing requirements

- Gmail-originated work routes to Gmail.
- Outlook-originated work routes to Microsoft Graph.
- WhatsApp-originated work routes to the configured WhatsApp provider.
- Messenger-originated work routes to the configured Messenger provider.
- Instagram-originated work routes to the configured Instagram provider.
- SMS-originated work routes to the configured SMS provider.
- Missing provider support must block clearly before mutation.

## UI requirements

Update as needed:

- review package detail;
- draft/reply preview;
- executions list/detail;
- providers;
- operational smoke;
- dashboard source/action badges;
- help/runbook.

## Tests

Focused tests only:

- messaging review package can prepare a reply execution;
- disabled messaging send flag blocks;
- dry-run returns audit-friendly result;
- provider mismatch is blocked;
- email providers are not used for messaging-originated work;
- execution detail shows channel routing and recovery guidance.

## Acceptance criteria

- Messaging-channel conversations can produce local review packages and reply candidates.
- Messaging reply execution exists only for configured provider(s), behind explicit flags and dry-run.
- Provider routing is safe and visible.
- External messaging sends remain disabled by default.
- Audit records capture prepare/approve/confirm/execute/fail lifecycle.

## Status

Planned.
