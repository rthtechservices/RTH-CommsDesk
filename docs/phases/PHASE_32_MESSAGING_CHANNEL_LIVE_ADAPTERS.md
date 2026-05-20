# Phase 32 — Messaging Channel Live Adapter Sprint

## Goal

Implement the first practical live messaging adapter(s) selected from Phase 30/31 findings.

This phase should connect the normalized omnichannel foundation to a real provider path where possible. Candidate provider families include Meta Graph APIs, Twilio, or another provider selected during Phase 30.

## Prerequisite

Complete Phase 30 and Phase 31 first.

## Scope

- Select the live provider target(s) based on documented prerequisites and available accounts.
- Add configuration flags and provider status for the selected adapter(s).
- Implement webhook verification and inbound event parsing.
- Implement replay-safe ingestion into the normalized channel model.
- Add setup documentation for local tunneling/webhook testing if needed.
- Add operational smoke checks for provider configuration and last inbound event.
- Keep outbound replies disabled unless explicitly included and fully gated.

## Live provider requirements

For each selected provider, document and implement where applicable:

- required account/app/page/phone setup;
- required scopes/permissions;
- webhook verification handshake;
- webhook signature validation;
- event/message id mapping;
- sender/contact id mapping;
- rate-limit/error behavior;
- token storage expectations;
- local dev test mode;
- safe failure messages.

## Safety requirements

- No production webhook secret or token in repo.
- No private raw media stored by default.
- No outbound send by default.
- All live-provider statuses must distinguish disabled, missing config, test-mode, live-ready, failed, and not implemented.

## Tests

Focused tests only:

- provider webhook verification success/failure;
- signature validation success/failure;
- valid inbound event creates expected local message/thread;
- duplicate inbound event is ignored or updates safely;
- missing config reports blocked state;
- provider status/operational smoke rows are accurate.

## Acceptance criteria

- At least one selected messaging provider can ingest inbound live/test webhook events safely.
- The ingested messages appear in the existing operator triage/review flow.
- Provider status and smoke pages show actionable setup/readiness state.
- No external messaging sends are enabled by default.
- Phase 33 has a clear path to review/execution for messaging replies.

## Status

Planned.
