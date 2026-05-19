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

## Partial completion notes — 2026-05-18 Azure OpenAI support

Status: Azure OpenAI AI-provider portion completed; broader Phase 15 external write-provider work remains planned.

Implemented:

- Added first-class `AI_PROVIDER=azure_openai` support alongside `mock` and `openai`.
- Added Azure OpenAI configuration fields:
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_DEPLOYMENT`
  - `AZURE_OPENAI_API_VERSION`
- Preserved existing OpenAI-compatible Chat Completions support through `AI_PROVIDER=openai`, `OPENAI_API_KEY`, `AI_MODEL`, and `AI_BASE_URL`.
- Split request construction so Azure OpenAI uses:
  - URL: `{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}`
  - Header: `api-key`
- Kept OpenAI-compatible mode on:
  - URL: `{AI_BASE_URL}/chat/completions`
  - Header: `Authorization: Bearer ...`
- Added sanitized provider diagnostics to `/api/ai/status`.
- Added `POST /api/ai/test` for a tiny JSON-only live-provider check that returns provider, model/deployment, endpoint host, success/failure, HTTP status code, and error category without exposing API keys.
- Preserved normal mock fallback for analysis/draft generation while leaving `/api/ai/test` to report direct provider failures.
- Added tests for Azure URL construction, Azure `api-key` header usage, OpenAI bearer header usage, Azure status diagnostics, sanitized test failures, and mock default behavior.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 90 tests.

Out of scope for this partial slice:

- Gmail send/draft/label/archive execution-provider changes.
- Calendar read/write provider changes.
- Microsoft Graph OAuth/client changes.
- Phase 15 provider status/admin page for all external providers.

## Completion notes — 2026-05-18 remaining provider wiring

Status: completed for Phase 15 scope.

Implemented:

- Added a provider matrix at `/providers` and `/api/providers/status`.
- Audited required providers/actions and surfaced classification plus runtime state for:
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
  - Azure OpenAI / OpenAI-compatible AI provider
- Added states for live, mock, disabled, missing configuration, dry-run, and failed.
- Added guarded external execution provider mode behind `EXECUTION_PROVIDER=external`.
- Added `EXTERNAL_WRITE_DRY_RUN=true` default and dry-run results that do not modify external systems.
- Added live Gmail draft/send/label/archive client methods behind explicit Gmail write flags.
- Added Google Calendar free/busy read and event/reminder write client methods behind explicit calendar flags.
- Added Microsoft Graph app-only OAuth/client setup for Outlook mail where tenant app registration and `Mail.Read`-style permissions are available.
- Kept Microsoft Teams and Outlook Calendar read fail-closed and documented as tenant-permission-dependent.
- Added skipped live integration seam coverage plus deterministic provider-status and dry-run tests.
- Updated `.env.example`, README, Help, Deployment, Lessons Learned, and phase/status docs.

Validation:

- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 97 tests.
- Empty SQLite migration to Alembic head `0012_live_ai_provider_diagnostics` — passed.
- Temporary Uvicorn route smoke for `/`, `/providers`, `/review-packages`, `/bulk-triage`, `/executions`, `/admin`, and `/healthz` — passed.
- `POST /api/ai/test` — passed against Azure OpenAI deployment `gpt-4.1-mini` with HTTP 200.

Safeguards:

- Mock providers remain the default.
- All live external write feature flags default to false.
- Dry-run defaults to true.
- Execution still requires prepare, approve, and final confirm.
- Delete/unsubscribe remains not live-wired.
- Provider status fails closed when configuration or flags are missing.
