# Phase 09 — Calendar Availability and Scheduling Recommendations

## Objective

Make RTH CommsDesk able to reason about scheduling requests and reminder-worthy dates. The app should be able to say whether the user appears available and prepare a proposed calendar action for review.

## Required implementation

- [x] Add provider-neutral calendar availability service.
- [x] Add mock calendar provider for tests and local development.
- [x] Add Google Calendar read-only availability integration if OAuth scope/configuration is available.
- [x] Add Outlook Calendar read-only availability integration if Microsoft auth exists or is introduced.
- [x] Detect proposed meeting dates/times from conversation summaries or message bodies.
- [x] Detect due dates and reminder-worthy dates, such as registration renewal due dates.
- [x] Prepare local proposed calendar actions:
  - create_reminder
  - create_meeting
  - offer_availability
  - ask_for_time_clarification
- [x] Show availability reasoning in review packages.
- [x] Show conflicts and available windows in a user-friendly way.
- [x] Add tests with mocked calendar data for availability, conflict detection, due-date reminders, and meeting proposal handling.

## Product behavior examples

### Friend proposes dinner

Expected result:

- The app detects the proposed day/time.
- The app checks calendar availability.
- The app recommends a response and a proposed calendar event if available.
- No event is created externally in this phase.

### ICBC renewal

Expected result:

- The app detects the renewal due date.
- The app proposes a reminder one week before the due date.
- The proposed reminder is visible in the review package.

## Out of scope

- Creating or sending calendar events externally.
- Sending email replies.
- Microsoft 365 mail/Teams connectors unless needed only for calendar read configuration.
- Fully autonomous scheduling.

## Documentation updates required

- [x] `docs/IMPLEMENTATION_LOG.md`
- [x] `docs/LESSONS_LEARNED.md`
- [x] `docs/HELP.md`
- [x] This phase file with completion notes

## Acceptance criteria

- [x] `pytest -q` passes.
- [x] Mock calendar availability tests pass.
- [x] Review packages can show proposed calendar/reminder actions.
- [x] The app can explain why a time is available or conflicted.
- [x] No external calendar writes occur in this phase.

## Completion notes

Status: completed on 2026-05-15.

Implemented:

- Added provider-neutral `calendar_availability_service` with mock provider and read-only Google/Outlook provider shapes.
- Added local `calendar_action_proposals` persistence linked to review packages.
- Integrated calendar recommendation logic into analysis flow for due-date reminders and schedule proposals.
- Added availability/conflict reasoning and proposal timing to review package UI/API output.
- Added tests for reminder recommendation, availability offer flow, and conflict clarification flow.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 62 tests.

Safety boundary confirmed:

- No external calendar events/reminders are created in this phase.
- Calendar recommendations remain local review artifacts only.
