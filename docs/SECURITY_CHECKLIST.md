# Production Security Checklist

Use this checklist before exposing RTH CommsDesk beyond localhost.

## Authentication and access

- [ ] `APP_AUTH_ENABLED=true` in staging/production.
- [ ] `APP_AUTH_USERNAME`, `APP_AUTH_PASSWORD`, and `API_AUTH_TOKEN` are set with strong values.
- [ ] `AUTH_SESSION_SECRET` is long/random and not the local default.
- [ ] Reverse proxy or ingress requires TLS and redirects HTTP to HTTPS.
- [ ] `/api/notifications/webhook` uses `NOTIFICATION_WEBHOOK_SECRET`.

## Secrets handling

- [ ] OAuth client secret JSON and token files are stored outside git.
- [ ] `.env` files containing secrets are excluded from commits.
- [ ] Secrets are injected from secret manager/runtime config, not hardcoded.
- [ ] Logs and error traces are reviewed to ensure tokens/secrets are redacted.

## Data minimization and retention

- [ ] `GMAIL_STORE_FULL_BODY` is enabled only when explicitly required.
- [ ] Retention windows are configured:
  - `RETENTION_MESSAGE_BODY_DAYS`
  - `RETENTION_SENT_LEARNING_DAYS`
  - `RETENTION_EXECUTION_AUDIT_DAYS`
- [ ] Admin retention cleanup is run on a schedule.
- [ ] Admin cache-clear controls are restricted to trusted operators.

## Execution safety

- [ ] External write actions still require prepare -> approve -> confirm workflow.
- [ ] Duplicate-execution safeguards remain enabled.
- [ ] Audit logs are retained per policy and reviewed periodically.

## Operational hardening

- [ ] CI (`ruff` + `pytest`) passes before deployment.
- [ ] Database backups and restore drill are documented and tested.
- [ ] Health check endpoint (`/healthz`) is monitored.
- [ ] Incident escalation contact/process is documented internally.
