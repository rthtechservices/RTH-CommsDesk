# RTH CommsDesk (MVP)

RTH CommsDesk is a privacy-first personal communications triage system.

## MVP scope
- Gmail-only connector (read-only)
- Metadata/snippet storage by default
- Deterministic classification and attention scoring
- Draft-only reply placeholders (no auto-send)
- Local SQLite for development

## Known MVP limitations
- Incremental `since` sync is supported in service calls but is not yet persisted as a cross-run watermark.
- Outlook/Teams/SMS/WhatsApp/Messenger connectors are stubbed only.
- AI classifier is provider-neutral but runs with deterministic logic/mock fallback by default.

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

## Running tests
```bash
pytest -q
```

## Privacy defaults
- Store message metadata and snippets by default.
- Full body storage is disabled unless `GMAIL_STORE_FULL_BODY=true`.
- OAuth token file (`gmail_token.json`) and client secrets are local-only and gitignored.

## Safety confirmation
- No send/reply automation exists.
- No archive/delete actions exist.
- No scraping/bypass behavior is implemented.

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
```

## Phase 2 TODO
- Outlook/Microsoft Graph connector
- Teams connector
- Android notification bridge for SMS/WhatsApp/Messenger
- Vector store for approved reply examples
- AI-generated draft replies
- Azure SQL deployment
- Dashboard authentication
