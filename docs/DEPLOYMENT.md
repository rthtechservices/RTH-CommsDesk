# Deployment Guide

This guide describes a repeatable deployment path for RTH CommsDesk beyond local development.

## Target deployment posture

- **Runtime**: FastAPI served by Uvicorn (or Gunicorn+Uvicorn workers).
- **Database**: managed SQL database via `DATABASE_URL` (recommended: Azure Database for PostgreSQL Flexible Server).
- **Auth**: app auth enabled (`APP_AUTH_ENABLED=true`) with required web credentials and API token.
- **Logging**: structured JSON logs (`LOG_FORMAT=json`) with redaction enabled by default.

## Required environment configuration

Minimum required settings for non-local environments:

```text
ENV=staging
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<db_name>
APP_BASE_URL=https://commsdesk.example.com
LOG_LEVEL=INFO
LOG_FORMAT=json

APP_AUTH_ENABLED=true
APP_AUTH_USERNAME=<secure-username>
APP_AUTH_PASSWORD=<secure-password>
API_AUTH_TOKEN=<long-random-token>
AUTH_SESSION_SECRET=<long-random-secret>
AUTH_SESSION_TTL_HOURS=12

GMAIL_CLIENT_SECRETS_FILE=/run/secrets/gmail_client_secret.json
GMAIL_TOKEN_FILE=/var/lib/commsdesk/gmail_token.json
NOTIFICATION_WEBHOOK_SECRET=<long-random-webhook-secret>
```

Provider status and dry-run controls:

```text
EXECUTION_PROVIDER=mock
EXTERNAL_WRITE_DRY_RUN=true
GMAIL_WRITE_ENABLED=false
GMAIL_DRAFT_CREATE_ENABLED=false
GMAIL_SEND_ENABLED=false
GMAIL_LABEL_ARCHIVE_ENABLED=false
GOOGLE_CALENDAR_WRITE_ENABLED=false
```

Keep these disabled for first deployment. Use `/providers` and `GET /api/providers/status` to confirm live/mock/disabled/missing/dry-run states before enabling any external write path.

Retention controls:

```text
RETENTION_MESSAGE_BODY_DAYS=90
RETENTION_SENT_LEARNING_DAYS=180
RETENTION_EXECUTION_AUDIT_DAYS=365
```

## External provider prerequisites

### Gmail write actions

Live Gmail draft/send/label/archive actions require:

- Google OAuth client configuration available through `GMAIL_CLIENT_SECRETS_FILE`.
- OAuth token authorization for the required Gmail scope: compose, send, or modify.
- `EXECUTION_PROVIDER=external`.
- The matching feature flag enabled, such as `GMAIL_DRAFT_CREATE_ENABLED=true`.
- Approval and final confirmation in the execution workflow.
- `EXTERNAL_WRITE_DRY_RUN=false` only after a manual dry-run review.

### Google Calendar

Google Calendar read/write actions require:

- Google OAuth client configuration available through `GMAIL_CLIENT_SECRETS_FILE`.
- `GOOGLE_CALENDAR_TOKEN_FILE` stored outside committed source.
- `GOOGLE_CALENDAR_ID` set to the intended calendar, usually `primary`.
- `GOOGLE_CALENDAR_READ_ENABLED=true` for free/busy checks.
- `GOOGLE_CALENDAR_WRITE_ENABLED=true` plus external execution flow for event/reminder creation.

### Microsoft Graph

Outlook mail live ingestion requires tenant-specific Microsoft Graph setup:

- Azure app registration.
- Application permissions and admin consent for the mailbox read scope required by the deployment.
- `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, and `MICROSOFT_ACCOUNT`.
- `MICROSOFT_GRAPH_ENABLED=true` and `MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true`.

Teams and Outlook Calendar are intentionally fail-closed until the exact tenant permissions and endpoint strategy are confirmed.

## Deployment steps

1. Build and install dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install -e ".[dev,gmail]"
   ```

2. Apply migrations:

   ```bash
   python -m alembic upgrade head
   ```

3. Start service:

   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. Validate health endpoint:

   ```bash
   curl -fsS http://127.0.0.1:8000/healthz
   ```

5. Verify auth:
   - `GET /` should redirect to `/login` when not authenticated.
   - API calls require `X-API-Key` or `Authorization: Bearer <API_AUTH_TOKEN>`.

## CI and release gate

- CI workflow is defined at `.github/workflows/ci.yml`.
- Required checks: `ruff` and `pytest -q`.
- Do not promote deployments when CI is red.

## Backup and restore guidance

### Database backups

- Use managed database automated backups and point-in-time restore.
- Record backup retention settings in your infrastructure configuration.
- Before major schema changes, take an on-demand backup/snapshot.

### Restore drill

1. Restore a database snapshot into an isolated environment.
2. Update `DATABASE_URL` for that environment.
3. Run `python -m alembic upgrade head`.
4. Validate app startup and `/healthz`.
5. Verify admin retention and dashboard behavior.

### Local file-backed secrets

- `gmail_token.json` and OAuth secret JSON files are sensitive.
- Store these outside the repo in secret volumes or secret managers.
- Never commit token/secret files.
