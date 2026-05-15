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

- `pytest -q` passes.
- Contact management is usable from the dashboard or detail pages.
- Contact relationship and importance affect scoring predictably.
- Existing messages recalculate when relevant contact settings change.
