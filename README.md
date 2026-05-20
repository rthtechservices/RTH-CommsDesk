# RTH CommsDesk (MVP)

RTH CommsDesk is a privacy-first personal communications triage system.

## Project tracking and LLM handoff

This repository is managed through phased LLM-assisted development.

Before assigning work to Codex, Copilot, or another LLM session, have the session read:

1. `docs/LLM_SESSION_GUIDE.md`
2. `docs/PROJECT_TRACKING.md`
3. `docs/PHASE_PLAN.md`
4. The assigned phase file under `docs/phases/`
5. `docs/IMPLEMENTATION_LOG.md`
6. `docs/LESSONS_LEARNED.md`
7. `docs/HELP.md`
8. `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md` when testing delegated Microsoft Graph locally

Each LLM session should complete one phase only, update documentation, and stop for human review.

## MVP scope
- Gmail-first connector workflow with optional Outlook mail read and notification-summary webhook intake
- Metadata/snippet storage by default
- Deterministic classification and attention scoring
- Local review-only draft suggestions with voice profiles (no auto-send)
- Local SQLite for development

## Known MVP limitations
- Outlook mail read now supports delegated Microsoft Graph OAuth for local smoke testing; Outlook send, Outlook Calendar, and Teams remain disabled/not implemented.
- The dashboard now includes compact operational status, command-center, source/runtime cards, dense attention rows, workflow breadcrumbs, provider blockers, review packages, and execution approvals.
- Provider status is visible at `/providers`; it includes copy/paste configuration guidance but does not edit `.env`. Microsoft Graph Teams, Outlook send, and Outlook Calendar remain disabled/not implemented.
- AI classifier is provider-neutral but runs with deterministic logic/mock fallback by default.
- Gmail sync is read-only and duplicate-safe. Recent sync handles the active inbox window, and manual backfill can page farther through the Gmail backlog.
- Gmail conversation context can be fetched on demand so detail pages show a full thread timeline when full content is available.
- Draft generation and AI analysis use deterministic mock/local providers by default; no paid AI credentials are required for local development. Live AI can be enabled through environment variables with mock fallback.
- Local conversation summaries and proposed action review packages are stored for review only. They do not modify Gmail or calendars.
- Sent-mail learning can infer VIP candidates, salutation/tone guidance, and recurring operator sign-off guidance, with explicit approve/reject/edit controls on the Voice Calibration page.
- Bulk triage mode supports paginated queue processing, local automation candidate generation, and reversible bulk actions.
- Local calendar availability recommendations can prepare reminder/scheduling proposals with conflict reasoning for review packages; date-only meeting requests ask for a time instead of inventing one.
- Approved outbound execution flows now support prepare/approve/confirm lifecycle with audit logs and mock provider execution.
- External Gmail and Google Calendar execution providers are guarded by `EXECUTION_PROVIDER`, per-action feature flags, and `EXTERNAL_WRITE_DRY_RUN=true` by default.
- Authentication defaults are local-development-friendly; production deployments must provide explicit auth and secret settings.

## Safety rules
- Never commit secrets, OAuth tokens, or private message data.
- Full body ingestion is opt-in (`GMAIL_STORE_FULL_BODY=true`) and off by default.
- The app does not auto-send, archive, or delete emails.

## Setup
1. Copy env file:
   ```bash
   cp .env.example .env
   ```
2. Install dependencies:
   ```bash
   pip install -e .[dev,gmail]
   ```
3. Configure Gmail OAuth desktop credentials:
   - Download client credentials JSON from Google Cloud Console.
   - Save it as `client_secret.json` in the repository root (or set `GMAIL_CLIENT_SECRETS_FILE`).
   - Do **not** commit this file.
4. Run migrations:
   ```bash
   alembic upgrade head
   ```
   Startup also runs Alembic migrations, but running this explicitly keeps local setup predictable.
5. Start API and dashboard:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Open dashboard at `http://127.0.0.1:8000/`.

## Gmail OAuth setup
1. Create OAuth desktop credentials in Google Cloud Console.
2. Save the JSON as `client_secret.json` (or set `GMAIL_CLIENT_SECRETS_FILE` to that path).
3. Trigger initial auth by calling `POST /api/sync/gmail`.
4. Gmail read sync uses `https://www.googleapis.com/auth/gmail.readonly`.
5. When any Gmail write flag is enabled, Gmail OAuth requests the combined
   read/write scope set: `gmail.readonly`, `gmail.compose`, `gmail.send`, and
   `gmail.modify`.
6. If credentials are missing, `/api/sync/gmail` returns a clear configuration error.

## Live AI provider setup

Mock AI remains the default. To use OpenAI-compatible Chat Completions, set:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=...
AI_MODEL=...
AI_BASE_URL=https://api.openai.com/v1
```

To use Azure OpenAI / Azure AI Foundry deployments, set:

```env
AI_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_VERSION=2025-04-01-preview
```

Do not put an Azure `/openai/responses?...` or `/chat/completions?...` URL in `AI_BASE_URL`. Azure mode builds the deployment URL from `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, and `AZURE_OPENAI_API_VERSION`.

Use `GET /api/ai/status` for sanitized configuration status and `POST /api/ai/test` for a tiny JSON-only provider test. The test endpoint returns provider, model/deployment, endpoint host, success/failure, HTTP status code, and error category without returning API keys.

## Provider status and external-write dry-run

Open `http://127.0.0.1:8000/providers` or call `GET /api/providers/status` to see each provider/action classified as live-ready, mock-only, adapter-shape-only, partially wired, or not implemented, with runtime state such as live, mock, disabled, missing configuration, dry-run, or failed. The page includes configuration snippets and restart guidance; it does not live-edit `.env`.

Open `http://127.0.0.1:8000/operational-smoke` for the daily readiness panel. It shows Gmail read config, Outlook delegated Graph status, Outlook sync readiness, Azure/OpenAI test links, execution provider mode, dry-run state, Gmail write flags, Google Calendar write status, Microsoft write boundaries, source counts, and pending workflow queues.
Smoke runs can now be persisted from the page or with `POST /api/operational-smoke/run`; recent sanitized smoke history is visible on `/operational-smoke`.

External writes are disabled by default:

```env
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
OPERATIONAL_TEST_MODE=false
EXECUTION_TEST_EMAIL_ALLOWLIST=
GMAIL_WRITE_ENABLED=false
GMAIL_DRAFT_CREATE_ENABLED=false
GMAIL_SEND_ENABLED=false
GMAIL_LABEL_ARCHIVE_ENABLED=false
GOOGLE_CALENDAR_WRITE_ENABLED=false
```

Phase 19 test execution also requires `OPERATIONAL_TEST_MODE=true` and a comma-separated `EXECUTION_TEST_EMAIL_ALLOWLIST`. The allowlist supports exact addresses such as `test@example.com` and explicit domains such as `@example.com`. Empty allowlists and non-allowlisted recipients block streamlined Gmail draft/send execution before any real provider write is attempted.

To test guarded Gmail draft or Google Calendar dry-run execution without modifying Gmail or calendars, set `EXECUTION_PROVIDER=external`, `OPERATIONAL_TEST_MODE=true`, keep `EXTERNAL_WRITE_DRY_RUN=true`, configure the allowlist, and enable only the specific action flag being tested. Execution still requires prepare, approve, and final confirm.

Do not set `EXTERNAL_WRITE_DRY_RUN=false` unless OAuth scopes, feature flags, provider status, allowlist, and the execution payload have been manually reviewed. Gmail send test execution is blocked while dry-run remains enabled.

## Google Calendar setup

Google Calendar read/write uses the same local OAuth client secret file plus a separate token file:

```env
CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_TOKEN_FILE=./google_calendar_token.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIME_ZONE=America/Vancouver
GOOGLE_CALENDAR_READ_ENABLED=true
GOOGLE_CALENDAR_WRITE_ENABLED=false
```

Calendar write remains disabled unless `GOOGLE_CALENDAR_WRITE_ENABLED=true`, `EXECUTION_PROVIDER=external`, approval/confirmation are completed, and dry-run is deliberately disabled.

Calendar execution payloads include `timeZone` on both start and end. `GOOGLE_CALENDAR_TIME_ZONE` defaults to `America/Vancouver`.

## Gmail write-scope reauthorization

If live Gmail draft/send/label execution needs write access, enable the intended Gmail write flags before the next OAuth flow. A token created for read-only sync cannot perform compose, send, or modify actions. Delete the local `gmail_token.json` and re-authorize after enabling the write flags so Google can prompt for `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.compose`, `https://www.googleapis.com/auth/gmail.send`, and `https://www.googleapis.com/auth/gmail.modify`.

CommsDesk checks the scopes stored in `gmail_token.json` before reusing it. If the token is missing a required Gmail scope, live execution forces reauthorization or reports exactly which scopes are missing.

## Microsoft Graph setup

Outlook mail read supports delegated Microsoft Graph OAuth for local development while preserving the existing app-only client seam.

For local delegated Outlook mail read smoke testing, configure:

```env
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true
MICROSOFT_GRAPH_AUTH_MODE=delegated
MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read offline_access
MICROSOFT_GRAPH_TOKEN_FILE=./microsoft_graph_token.json
MICROSOFT_TENANT_ID=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=
MICROSOFT_ACCOUNT=me
```

No Microsoft client secret or certificate is required for the delegated device-code path. A secret/certificate is only required for `MICROSOFT_GRAPH_AUTH_MODE=app_only`.

Run `POST /api/graph/test` to verify delegated configuration. If no delegated token exists, CommsDesk starts a local device-code authorization flow and returns a sanitized `authorization_required` result. Complete the Microsoft device login, then retry `POST /api/graph/test`. The delegated token is stored only in `MICROSOFT_GRAPH_TOKEN_FILE`; do not commit it.

Outlook read sync uses `GET /me/messages` for delegated `MICROSOFT_ACCOUNT=me`, or `/users/{MICROSOFT_ACCOUNT}/messages` when a specific account is configured. It requests only the selected fields needed for local triage and follows Graph paging up to the requested sync limit.

For app-only Graph tenants, set:

```env
MICROSOFT_GRAPH_AUTH_MODE=app_only
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_ACCOUNT=user@example.com
```

Detailed local instructions are in `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md`.

Teams, Outlook send, and Outlook Calendar remain disabled/not implemented. The current Microsoft Graph boundary is Outlook mail read only.

## Running tests
```bash
pytest -q
```

## Windows daily scripts

From the repository root:

```powershell
.\scripts\start-commsdesk.ps1
.\scripts\smoke-commsdesk.ps1
.\scripts\smoke-mailbox-cleanup.ps1
.\scripts\backup-commsdesk.ps1
.\scripts\reauth-commsdesk.ps1 -Gmail
.\scripts\reauth-commsdesk.ps1 -GoogleCalendar
.\scripts\reauth-commsdesk.ps1 -MicrosoftGraph
```

The backup script excludes `.env`, OAuth token files, and `client_secret.json` by default.

## Local database lifecycle

Local development uses SQLite at `commsdesk.db` by default. The app no longer creates tables directly with SQLAlchemy `create_all()` during startup. Startup runs Alembic migrations to the current head, and `alembic upgrade head` is the explicit setup command.

To reset disposable local data safely:

```powershell
# Stop the local uvicorn server first.
Remove-Item .\commsdesk.db -ErrorAction SilentlyContinue
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Do not delete or commit `client_secret.json`, `gmail_token.json`, `.env`, or any exported/private message data as part of a database reset.

## Privacy defaults
- Store message metadata and snippets by default.
- Full body storage is disabled unless `GMAIL_STORE_FULL_BODY=true`.
- OAuth token files (`gmail_token.json`, `google_calendar_token.json`, `microsoft_graph_token.json`) and client secrets are local-only and gitignored.
- Structured logging redacts token/secret/password/authorization values.
- Retention windows can scrub stored message bodies, sent-learning excerpts, and aged execution audit rows.

## Safety confirmation
- No unsupervised send/archive/delete automation exists.
- No scraping/bypass behavior is implemented.

## Deployment and hardening docs

- Deployment/runbook: `docs/DEPLOYMENT.md`
- Production checklist: `docs/SECURITY_CHECKLIST.md`
- User/admin operations: `docs/HELP.md`
- Microsoft Graph local smoke guide: `docs/MICROSOFT_GRAPH_LOCAL_SMOKE.md`

## Project structure
```
/app
  /api
  /connectors
    /gmail
    /outlook
    /teams
    /notifications
  /core
  /models
  /services
  /triage
  /voice
  /web
/alembic
/tests
/docs
  /phases
```

## Current phase status

Phases 01 through 22 are implemented. Phase 22 is ready for human review after validation.
