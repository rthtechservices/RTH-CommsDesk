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

Each LLM session should complete one phase only, update the documentation, and stop for human review.

## MVP scope
- Gmail-first connector workflow with optional Outlook/Teams ingestion and notification-summary webhook intake
- Metadata/snippet storage by default
- Deterministic classification and attention scoring
- Local review-only draft suggestions with voice profiles (no auto-send)
- Local SQLite for development

## Known MVP limitations
- Outlook/Teams connectors are implemented as mocked Graph-shape adapters; live Microsoft auth/client wiring is environment-specific.
- AI classifier is provider-neutral but runs with deterministic logic/mock fallback by default.
- Gmail sync is read-only and duplicate-safe. Recent sync handles the active inbox window, and manual backfill can page farther through the Gmail backlog.
- Gmail conversation context can be fetched on demand so detail pages show a full thread timeline when full content is available.
- Draft generation and AI analysis use deterministic mock/local providers by default; no paid AI credentials are required for local development. Live AI can be enabled through environment variables with mock fallback.
- Local conversation summaries and proposed action review packages are stored for review only. They do not modify Gmail or calendars.
- Sent-mail learning can infer VIP candidates and salutation/tone guidance, with explicit approve/reject/edit controls on the Voice Calibration page.
- Bulk triage mode supports paginated queue processing, local automation candidate generation, and reversible bulk actions.
- Local calendar availability recommendations can prepare reminder/scheduling proposals with conflict reasoning for review packages.
- Approved outbound execution flows now support prepare/approve/confirm lifecycle with audit logs and mock provider execution.
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
4. Read-only Gmail scope only is used: `https://www.googleapis.com/auth/gmail.readonly`.
5. If credentials are missing, `/api/sync/gmail` returns a clear configuration error.

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

## Running tests
```bash
pytest -q
```

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
- OAuth token file (`gmail_token.json`) and client secrets are local-only and gitignored.
- Structured logging redacts token/secret/password/authorization values.
- Retention windows can scrub stored message bodies, sent-learning excerpts, and aged execution audit rows.

## Safety confirmation
- No unsupervised send/archive/delete automation exists.
- No scraping/bypass behavior is implemented.

## Deployment and hardening docs

- Deployment/runbook: `docs/DEPLOYMENT.md`
- Production checklist: `docs/SECURITY_CHECKLIST.md`
- User/admin operations: `docs/HELP.md`

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

Phases 01 through 14 are now implemented in this repository roadmap.
