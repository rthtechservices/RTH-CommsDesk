# Phase 03 — Contact Intelligence and Relationship-Aware Triage

## Objective

Make RTH CommsDesk understand who matters and why. Attention scoring should use explicit contact knowledge, relationship type, aliases, and user corrections.

## Required implementation

- Add or refine contact profile fields:
  - display name
  - primary email
  - aliases
  - relationship type
  - importance tier
  - preferred channel
  - notes
  - VIP/noise status
- Add supported relationship types such as partner, close_friend, friend, family, client, prospect, vendor, newsletter, system, unknown.
- Add contact management views.
- Add contact edit actions.
- Show contact importance context on message detail pages.
- Recalculate attention when contact profile fields change.
- Add contact correction history or feedback summary.
- Add tests for relationship-aware scoring and alias handling.

## Out of scope

- New connectors.
- AI-generated replies.
- Sending/archive/delete behavior.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Contact management is usable from the dashboard or detail pages.
- [x] Contact relationship and importance affect scoring predictably.
- [x] Existing messages recalculate when relevant contact settings change.

## Completion notes

Completed on 2026-05-15.

- Contact profiles now support display name, primary email, aliases, relationship type, importance tier, preferred channel, notes, and normal/VIP/noise status in the web UI.
- Supported relationship types are partner, close_friend, friend, family, client, prospect, vendor, newsletter, system, and unknown.
- Gmail sync resolves senders by primary email or alias before creating a new contact.
- Contact profile edits record local feedback/history and recalculate matching existing messages.
- Message detail pages show contact status, relationship, importance tier, preferred channel, aliases, and recent contact history.
- Added tests for relationship-aware scoring, alias handling, contact profile recalculation, and contact management rendering.

## Validation

- `python -m pytest -q` — passed, 33 tests.
- `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8013` — started successfully.
- Dashboard and Contacts pages returned HTTP 200 during startup smoke.

## Human review checklist

- Open `/contacts` and verify the contact list is understandable with real Gmail-derived contacts.
- Edit a contact alias and confirm messages from that alias appear under the profile.
- Change a contact relationship or importance tier and confirm the related attention scores move in the expected direction.
- Confirm no send, archive, delete, Outlook, Teams, SMS, WhatsApp, Messenger, notification connector, or AI reply behavior was added.
