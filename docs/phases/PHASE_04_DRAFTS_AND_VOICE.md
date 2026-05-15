# Phase 04 — Safe Draft Reply Generation and Voice Profiles

## Objective

Generate review-only draft suggestions that fit the message context and the user's preferred tone. Drafts must remain local and unsent.

## Required implementation

- [x] Implement provider-neutral draft generation service.
- [x] Add a mock provider for tests and local development.
- [x] Use voice profiles for different audiences:
  - client
  - friend
  - partner
  - vendor
  - short acknowledgement
- [x] Include message classification, contact relationship, and correction history in draft context.
- [x] Store generated drafts locally with status and source message.
- [x] Add a user-facing draft review page.
- [x] Add tests for draft creation using a mock provider.

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

- [x] `pytest -q` passes.
- [x] Draft generation works with a mock provider.
- [x] Drafts are clearly marked as review-only.
- [x] No auto-send or external mailbox modification exists.

## Completion notes — 2026-05-15

- Added `DraftContext`, `DraftProvider`, and `MockDraftProvider` in `app/services/draft_service.py`.
- Draft context includes subject, sender/contact identity, relationship, importance tier, VIP/noise/normal state, classification summary, attention score/reason, recommended action, and summarized correction/profile feedback.
- Added local draft generation from message detail pages with a selectable voice profile.
- Added local `/drafts` and `/drafts/{draft_id}` review pages. These pages explicitly say drafts are suggestions only, not sent, and not created in Gmail.
- Seeded the missing `Short Acknowledgement` voice profile.
- Added tests in `tests/test_draft_generation.py` for mock-provider draft creation, all required voice styles, draft context construction, and the web review flow.
- Validation: `python -m pytest -q` passed with 37 tests.
- Startup smoke: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8014` started and served `GET /` with HTTP 200.

## Remaining boundaries

- No Gmail send, reply, archive, delete, or external Gmail draft creation was added.
- No Outlook, Teams, SMS, WhatsApp, Messenger, or notification connector work was added.
- Draft generation remains deterministic/mock-only for this phase so local development does not require paid AI credentials.
