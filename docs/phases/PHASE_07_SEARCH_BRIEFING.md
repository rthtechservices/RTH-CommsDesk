# Phase 07 — Sent-Mail Learning, VIP Inference, and Voice Calibration

## Objective

Make RTH CommsDesk learn how Rohan actually communicates instead of relying on generic voice labels.

The system should inspect historical sent mail, infer important contacts, learn greeting/name preferences, and derive tone guidance by contact and relationship type. This is required before draft replies can feel natural.

## Required implementation

- Add Gmail Sent Mail ingestion for learning data.
- Store sent-mail learning records separately from inbound triage records where appropriate.
- Ingest selected sent-message metadata and configurable body content needed for style learning.
- Infer likely VIP contacts from:
  - sent frequency
  - recency
  - reply patterns
  - manual VIP/important/noise corrections
  - contact relationship type
- Learn contact-specific salutation preferences:
  - no greeting
  - first name
  - nickname/manual display name
  - full name
  - formal greeting
- Learn relationship-level tone patterns:
  - close friend
  - friend
  - partner
  - client
  - prospect
  - vendor
  - family
- Add a voice calibration screen showing:
  - inferred VIP candidates
  - inferred salutation style
  - inferred tone notes
  - example sent messages used as evidence, without overexposing sensitive content
  - approve/reject/edit controls for inferred guidance
- Store approved voice guidance locally.
- Feed approved voice guidance into draft/review-package generation.
- Prevent generic phrases from being used when a more specific learned style exists.
- Add tests for VIP inference, salutation selection, friend-tone guidance, client-tone guidance, and use of approved voice notes in drafts.

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

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Sent-mail learning can run against mocked Gmail sent-message data.
- VIP/contact importance candidates are visible for review.
- Salutation preferences are inferred and editable.
- Approved voice guidance affects generated drafts.
- The Michael/Friend example does not use full-name corporate language when friend-tone guidance exists.
- No external send/archive/delete behavior is introduced.
