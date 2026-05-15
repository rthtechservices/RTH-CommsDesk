# Phase 09 — Calendar Availability and Scheduling Recommendations

## Objective

Make RTH CommsDesk able to reason about scheduling requests and reminder-worthy dates. The app should be able to say whether the user appears available and prepare a proposed calendar action for review.

## Required implementation

- Add provider-neutral calendar availability service.
- Add mock calendar provider for tests and local development.
- Add Google Calendar read-only availability integration if OAuth scope/configuration is available.
- Add Outlook Calendar read-only availability integration if Microsoft auth exists or is introduced.
- Detect proposed meeting dates/times from conversation summaries or message bodies.
- Detect due dates and reminder-worthy dates, such as registration renewal due dates.
- Prepare local proposed calendar actions:
  - create_reminder
  - create_meeting
  - offer_availability
  - ask_for_time_clarification
- Show availability reasoning in review packages.
- Show conflicts and available windows in a user-friendly way.
- Add tests with mocked calendar data for availability, conflict detection, due-date reminders, and meeting proposal handling.

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

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Mock calendar availability tests pass.
- Review packages can show proposed calendar/reminder actions.
- The app can explain why a time is available or conflicted.
- No external calendar writes occur in this phase.
