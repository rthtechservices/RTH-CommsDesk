# Phase 15 — Real Provider Wiring for Gmail, Calendar, and Microsoft Graph

## Objective

Turn the current provider shapes into working live integrations where appropriate. The overnight implementation added valuable adapter seams, but several connectors and execution providers are still mock-backed or require injected services.

This phase wires real provider clients behind the existing abstractions while preserving test mocks and explicit user approval flows.

## Required implementation

- Audit every connector/provider and classify it as:
  - live-ready
  - mock-only
  - adapter-shape-only
  - partially wired
- Add a provider status/admin page showing configuration readiness for:
  - Gmail read
  - Gmail external draft creation
  - Gmail send reply
  - Gmail label/archive
  - Google Calendar read
  - Google Calendar write
  - Microsoft Graph Outlook mail
  - Microsoft Graph Teams
  - Outlook Calendar read
  - notification webhook
- Implement live Gmail execution provider methods where OAuth scopes are configured and explicitly enabled.
- Implement live Google Calendar read/write providers where OAuth scopes are configured and explicitly enabled.
- Implement Microsoft Graph OAuth/client setup or document the exact missing deployment prerequisites.
- Keep provider methods disabled unless required configuration and explicit feature flags are present.
- Add safe dry-run mode for external write actions.
- Add integration-test seams so live provider tests can be skipped unless credentials are configured.
- Update `.env.example` with provider settings and feature flags.

## Required safeguards

- Mock provider remains available for tests.
- Live external writes require explicit feature flags.
- Execution engine approval and confirmation flow must remain mandatory.
- Provider status should fail closed: missing config disables external write actions.
- No secrets are logged.

## Out of scope

- Redesigning the whole UI.
- Adding new communication channels.
- Fully autonomous execution.

## Documentation updates required

- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/HELP.md`
- `.env.example`
- `docs/DEPLOYMENT.md`
- This phase file with completion notes

## Acceptance criteria

- `python -m ruff check .` passes.
- `python -m pytest -q` passes.
- Provider status page clearly shows what is live, mock, missing config, or disabled.
- External writes remain unavailable unless explicitly enabled.
- Dry-run mode works for outbound execution providers.
- At least Gmail read and full-thread fetch remain working.
