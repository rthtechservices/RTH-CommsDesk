# Phase 31 — Omnichannel Connector Foundation Sprint

## Goal

Add the normalized foundation for WhatsApp, Facebook Messenger, Instagram Messaging, and SMS-style message ingestion in one large sprint.

The goal is not to perfect one channel in isolation. The goal is to make messaging channels first-class citizens in the same local triage/review pipeline as Gmail and Outlook.

## Prerequisite

Complete Phase 30 first. Use its Outlook smoke results and omnichannel strategy decision to adjust this phase before implementation.

## Scope

Build the channel foundation:

- Add provider-neutral messaging channel types for:
  - WhatsApp;
  - Facebook Messenger;
  - Instagram Messaging;
  - SMS.
- Normalize inbound payloads into the existing local source/thread/message model or a clearly documented extension of it.
- Preserve source/provider identifiers for replay-safe deduplication.
- Add channel/source confidence so low-fidelity notification summaries are not over-trusted.
- Add webhook/provider abstraction for inbound messaging payloads.
- Add provider status rows for each messaging channel.
- Add local sample payload fixtures for each channel family.
- Add route/API seams for safe local ingestion testing.
- Update dashboard/source filters so messaging channels do not disappear into generic notification rows.
- Keep outbound messaging disabled in this phase unless Phase 30 explicitly says a selected provider makes it trivial and safe.

## Data rules

Required normalized fields:

- source/channel type;
- provider name;
- provider account/page/phone id where applicable;
- external message id;
- external thread/conversation id where available;
- sender id/address/handle/phone;
- recipient id/address/handle/phone;
- timestamp;
- subject/title if available;
- text/snippet/body according to storage settings;
- attachment/media metadata only, not raw media by default;
- source confidence;
- dedupe key.

Do not store secrets, webhook signing keys, raw access tokens, or private media blobs.

## Safety requirements

- Inbound webhook endpoints must support signature/secret verification where provider supports it.
- Local development can allow explicit test-mode bypass, but it must be visible and disabled by default.
- No outbound messaging in this phase unless explicitly approved by Phase 30 notes.
- No scraping private platforms.
- No hidden mock fallback that looks like live ingestion.

## UI requirements

Update operator-facing pages where useful:

- dashboard source counts;
- attention queue source badges/filters;
- provider status;
- operational smoke;
- message detail source metadata;
- docs/help for local sample webhook testing.

## Tests

Focused tests only:

- sample WhatsApp payload normalizes correctly;
- sample Messenger payload normalizes correctly;
- sample Instagram payload normalizes correctly;
- sample SMS payload normalizes correctly;
- duplicate external ids do not create duplicate messages;
- invalid webhook signature/secret fails closed;
- source filters/counts include messaging channels;
- provider status reports disabled/missing/test-ready states.

## Acceptance criteria

- Messaging channels can be represented consistently in local storage.
- Safe sample payloads for all four requested channel families ingest into local triage/review flow.
- Provider status and operational smoke make channel readiness visible.
- No external sends are enabled by default.
- Phase 32 has a clear live-adapter target based on Phase 30 findings.

## Status

Planned.
