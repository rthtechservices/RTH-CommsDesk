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

Retention controls:

```text
RETENTION_MESSAGE_BODY_DAYS=90
RETENTION_SENT_LEARNING_DAYS=180
RETENTION_EXECUTION_AUDIT_DAYS=365
```

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
