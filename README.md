# RTH CommsDesk (MVP)

RTH CommsDesk is a privacy-first personal communications triage system.

## MVP scope
- Gmail-only connector (read-only)
- Metadata/snippet storage by default
- Deterministic classification and attention scoring
- Draft-only reply placeholders (no auto-send)
- Local SQLite for development

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
3. Run migrations:
   ```bash
   alembic upgrade head
   ```
4. Start API and dashboard:
   ```bash
   uvicorn app.main:app --reload
   ```
5. Open dashboard at `http://127.0.0.1:8000/`.

## Gmail OAuth setup
1. Create OAuth desktop credentials in Google Cloud Console.
2. Save the JSON as `client_secret.json` (or set `GMAIL_CLIENT_SECRETS_FILE`).
3. Trigger initial auth by calling `POST /api/sync/gmail`.
4. Read-only Gmail scope only is used: `https://www.googleapis.com/auth/gmail.readonly`.

## Running tests
```bash
pytest -q
```

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
