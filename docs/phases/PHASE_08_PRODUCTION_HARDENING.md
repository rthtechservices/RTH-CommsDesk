# Phase 08 — Bulk Triage and Noise Automation

## Objective

Make RTH CommsDesk useful for a large backlog, such as 7,000+ emails. The user should be able to process large volumes quickly instead of repeatedly seeing the same small batch.

This phase should introduce bulk triage, queue progression, noise detection, unsubscribe candidates, and safe automation candidates.

## Required implementation

- Add a backlog/bulk triage mode.
- Support pagination and progress tracking across large Gmail history.
- Add queue controls for:
  - unreviewed
  - needs reply
  - important
  - proposed actions
  - noise candidates
  - unsubscribe candidates
  - reviewed
- Ensure reviewed/noise/ignored items leave the default active queue.
- Add bulk actions with clear confirmation and undo where practical:
  - mark reviewed
  - mark noise
  - mark important
  - assign contact relationship
  - approve no-response-needed recommendation locally
- Detect repeated low-value senders and newsletter patterns.
- Detect likely unsubscribe links in stored/sanitized message bodies.
- Generate unsubscribe_review candidates when evidence supports it.
- Detect never-opened, never-replied, or low-engagement sender patterns where Gmail data supports it.
- Generate archive_candidate and delete_candidate records with reasons and confidence.
- Add an automation candidate dashboard that shows what the app recommends and why.
- Require explicit approval before any destructive or external action is executed.
- Add tests for bulk pagination, queue progression, candidate generation, and bulk status updates.

## Product behavior examples

### Repeated marketing sender

Expected result:

- The app identifies the sender as a likely newsletter/marketing source.
- The app explains the evidence.
- The app offers mark_noise and unsubscribe_review as proposed actions.

### Stale low-value messages

Expected result:

- The app can group stale messages by sender/category.
- The app can propose archive_candidate or delete_candidate.
- The app does not delete externally until a later approved execution phase.

## Out of scope

- Actually deleting, archiving, labeling, or unsubscribing in Gmail unless moved to a separate explicitly approved execution subphase.
- Sending email.
- Calendar write actions.
- New communication connectors.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Backlog mode can progress beyond the first 100 messages.
- Bulk status updates work and are tested.
- Automation candidates are visible with reasons and confidence.
- Reviewed/noise items do not keep resurfacing in the default active queue.
- Unsubscribe candidates can be detected from mocked message bodies.
- No external destructive action is executed without a later approved execution phase.
