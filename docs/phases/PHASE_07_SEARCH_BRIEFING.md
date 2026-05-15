# Phase 07 — Sent-Mail Learning, VIP Inference, and Voice Calibration

## Objective

Make RTH CommsDesk learn how Rohan actually communicates instead of relying on generic voice labels.

The system should inspect historical sent mail, infer important contacts, learn greeting/name preferences, and derive tone guidance by contact and relationship type. This is required before draft replies can feel natural.

## Required implementation

- [x] Add Gmail Sent Mail ingestion for learning data.
- [x] Store sent-mail learning records separately from inbound triage records where appropriate.
- [x] Ingest selected sent-message metadata and configurable body content needed for style learning.
- [x] Infer likely VIP contacts from:
  - sent frequency
  - recency
  - reply patterns
  - manual VIP/important/noise corrections
  - contact relationship type
- [x] Learn contact-specific salutation preferences:
  - no greeting
  - first name
  - nickname/manual display name
  - full name
  - formal greeting
- [x] Learn relationship-level tone patterns:
  - close friend
  - friend
  - partner
  - client
  - prospect
  - vendor
  - family
- [x] Add a voice calibration screen showing:
  - inferred VIP candidates
  - inferred salutation style
  - inferred tone notes
  - example sent messages used as evidence, without overexposing sensitive content
  - approve/reject/edit controls for inferred guidance
- [x] Store approved voice guidance locally.
- [x] Feed approved voice guidance into draft/review-package generation.
- [x] Prevent generic phrases from being used when a more specific learned style exists.
- [x] Add tests for VIP inference, salutation selection, friend-tone guidance, client-tone guidance, and use of approved voice notes in drafts.

## Product behavior examples

### Friend reply

If historical sent mail shows Rohan writes casually to Michael and never uses "Michael Frolick" as a greeting, drafts should not start with "Hey Michael Frolick".

Expected result:

- The app uses first name, nickname, or no greeting based on observed/approved preference.
- The draft avoids generic corporate filler such as "I wanted to acknowledge this directly".

### Client reply

If historical sent mail to a client is concise but professional, the app should preserve that pattern.

Expected result:

- The draft uses the appropriate greeting and degree of formality.
- The tone guidance is visible in the review package.

## Out of scope

- Sending email.
- Calendar write actions.
- Microsoft 365 connectors.
- Fully autonomous inference without review; inferred guidance should be reviewable/editable.

## Documentation updates required

- [x] `docs/IMPLEMENTATION_LOG.md`
- [x] `docs/LESSONS_LEARNED.md`
- [x] `docs/HELP.md`
- [x] This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Sent-mail learning can run against mocked Gmail sent-message data.
- [x] VIP/contact importance candidates are visible for review.
- [x] Salutation preferences are inferred and editable.
- [x] Approved voice guidance affects generated drafts.
- [x] The Michael/Friend example does not use full-name corporate language when friend-tone guidance exists.
- [x] No external send/archive/delete behavior is introduced.

## Completion notes

Status: completed on 2026-05-15.

Implemented:

- Added Sent-mail learning storage (`sent_mail_learning_records`) with separate local ingestion from Gmail `in:sent`.
- Added VIP inference candidates (`vip_inference_candidates`) using sent frequency, recency, reply ratio, relationship weight, and correction history.
- Added voice guidance records (`voice_guidance`) for contact and relationship scopes with approve/reject/edit workflow.
- Added Voice Calibration UI (`/voice-calibration`) and API endpoints for learning refresh and inference review state updates.
- Updated local draft generation to apply approved salutation/tone guidance and remove generic filler when guidance requests it.
- Added tests for mocked sent-mail inference, friend salutation behavior, client formal salutation behavior, and approved guidance draft impact.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 54 tests.

Safety boundary confirmed:

- No external send, archive, delete, or unsubscribe behavior was added.
- Inference evidence on calibration pages uses excerpted text only.
