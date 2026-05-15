# Phase 04 — Safe Draft Reply Generation and Voice Profiles

## Objective

Generate review-only draft suggestions that fit the message context and the user's preferred tone. Drafts must remain local and unsent.

## Required implementation

- Implement provider-neutral draft generation service.
- Add a mock provider for tests and local development.
- Use voice profiles for different audiences:
  - client
  - friend
  - partner
  - vendor
  - short acknowledgement
- Include message classification, contact relationship, and correction history in draft context.
- Store generated drafts locally with status and source message.
- Add a user-facing draft review page.
- Add tests for draft creation using a mock provider.

## Safety boundary

- Do not send email.
- Do not create external Gmail drafts unless a later phase explicitly approves it.
- Do not store full message bodies by default.
- Do not log private message content.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Draft generation works with a mock provider.
- Drafts are clearly marked as review-only.
- No auto-send or external mailbox modification exists.
