# Phase 05 — Microsoft 365 Connectors

## Objective

Add read-only ingestion for Microsoft 365 communications, starting with Outlook and optionally Teams if permissions and APIs allow.

## Required implementation

- Add Microsoft Graph configuration and OAuth notes.
- Add read-only Outlook mail connector.
- Add Teams connector only if permissions and API shape are clear.
- Normalize Microsoft messages into existing source/thread/message models.
- Preserve source identifiers and thread IDs.
- Preserve privacy defaults.
- Add connector tests using mocked Graph responses.
- Document required permissions and setup steps.

## Out of scope

- Sending email.
- Replying to Teams messages.
- Archiving or deleting messages.
- Production deployment.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- This phase file with completion notes

## Acceptance criteria

- `pytest -q` passes.
- Outlook messages can be ingested through mocked tests.
- Real setup steps are documented clearly.
- No write permissions are introduced unless explicitly justified and reviewed.
