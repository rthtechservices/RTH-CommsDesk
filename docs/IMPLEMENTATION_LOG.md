# Implementation Log

Record completed work here at the end of every phase. Newest entries should be added at the top.

## 2026-05-19 — Live Microsoft Graph Delegated Outlook Smoke

### Summary
- Completed live local delegated Microsoft Graph authorization after enabling public client flows on the `RTH-CommsDesk` Entra app registration.
- Confirmed `POST /api/graph/test` succeeds with sanitized output: delegated auth mode, account `me`, configured tenant/client, no client secret, HTTP 200, and no token/secret leakage.
- Confirmed `POST /api/sync/outlook` performs live Outlook mail read through Graph and normalizes records into the existing local message/thread model.

### Smoke results
- `POST /api/graph/test` — success `true`, HTTP 200.
- `POST /api/sync/outlook` — fetched 100, inserted 100, skipped duplicates 0, updated threads 79, errors empty.

### Lessons
- Delegated device-code Graph auth requires the Entra app registration to allow public client/native client flows. Without that setting, token polling can fail with `AADSTS7000218` asking for a client assertion or client secret.
- `MICROSOFT_CLIENT_SECRET` should remain blank for the delegated local smoke path.
- Outlook send, Outlook calendar, and Teams remain disabled/not implemented.

## 2026-05-19 — Phase 17: Microsoft Graph Delegated OAuth and Outlook Mail Smoke

### Summary
- Added delegated Microsoft Graph OAuth support for local development with `MICROSOFT_GRAPH_AUTH_MODE=delegated`, configurable scopes, and a local `MICROSOFT_GRAPH_TOKEN_FILE`.
- Preserved the existing app-only Microsoft Graph client-credentials seam.
- Added sanitized `POST /api/graph/test` diagnostics for auth mode, account, configured booleans, success/failure, HTTP status, and sanitized error category/message.
- Implemented read-only Outlook mail sync through Graph `/me/messages` or `/users/{MICROSOFT_ACCOUNT}/messages`, using `$select` and safe paging.
- Updated provider status rows so Microsoft Graph delegated auth and Outlook mail read are visible while Outlook send, Outlook Calendar, and Teams remain disabled/not implemented.

### Files changed
- `app/core/config.py`
- `app/services/microsoft_graph_client.py`
- `app/services/provider_status_service.py`
- `app/api/routes.py`
- `.env.example`
- `.gitignore`
- `tests/test_microsoft_graph_client.py`
- `tests/test_provider_status.py`
- `README.md`
- `docs/HELP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_17_MICROSOFT_GRAPH_DELEGATED_OAUTH_OUTLOOK_MAIL.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed.
- `python -m pytest tests/test_microsoft_graph_client.py tests/test_provider_status.py tests/test_external_connectors.py -q` — passed, 14 tests.

### Smoke tests
- Automated validation used mocked Graph HTTP tests for delegated `/me/messages` paging, app-only `/users/{account}/messages`, device-code startup, sanitized test output, and the `/api/graph/test` route.
- Follow-up live local smoke succeeded after Phase 17: `POST /api/graph/test` returned HTTP 200 success, and `POST /api/sync/outlook` fetched 100 Outlook messages, inserted 100, skipped 0 duplicates, and updated 79 threads.

### Documentation updated
- `.env.example`
- `README.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/PHASE_PLAN.md`
- `docs/PHASE_STATUS.md`
- `docs/phases/PHASE_17_MICROSOFT_GRAPH_DELEGATED_OAUTH_OUTLOOK_MAIL.md`

### Known issues
- Outlook send, Outlook Calendar, and Teams remain disabled/not implemented by design.

### Recommended next actions
- Proceed to Phase 18: Operational Inbox Workflow Smoke and Fast-Path UX.

## 2026-05-19 — Live External Gmail/Calendar Execution Fixes

### Summary
- Replaced one-record-per-source execution behavior with immutable attempt records, including attempt numbers and prepare-new/rerun/clone controls.
- Added send-ready draft fields and execution payload sanitization so review notes stay in CommsDesk and external Gmail drafts receive only the clean subject/body.
- Fixed live Google Calendar execution payloads so reminder and scheduled-event writes include `timeZone` on both `start` and `end`, defaulting to `America/Vancouver`.
- Added configurable `GOOGLE_CALENDAR_TIME_ZONE` and documented it in setup/deployment help.
- Improved live Gmail insufficient-scope handling so execution failures record a clear `gmail_token.json` reauthorization instruction instead of a generic provider error.
- Preserved mock execution and external dry-run behavior, and made tests force mock execution defaults so local `.env` live-provider settings do not leak into the test suite.

### Files changed
- `app/core/config.py`
- `app/services/external_provider_clients.py`
- `app/services/draft_service.py`
- `app/models/entities.py`
- `app/web/routes.py`
- `app/web/templates/execution_detail.html`
- `app/web/templates/executions.html`
- `app/web/templates/draft_review.html`
- `app/api/routes.py`
- `alembic/versions/0013_execution_attempts_send_ready_drafts.py`
- `.env.example`
- `tests/conftest.py`
- `tests/test_external_provider_clients.py`
- `tests/test_execution_service.py`
- `README.md`
- `docs/DEPLOYMENT.md`
- `docs/HELP.md`
- `docs/LESSONS_LEARNED.md`
- `docs/IMPLEMENTATION_LOG.md`

### Tests run
- `python -m ruff check .` — passed.
- `python -m pytest -q` — passed, 113 tests.
- `python -m pytest tests/test_execution_service.py tests/test_external_provider_clients.py tests/test_draft_generation.py -q` — passed, 20 tests.

### Smoke tests
- Not run against live external writes after the fix; no real email or calendar write was executed during this patch.

### Known issues
- Existing live Gmail tokens created with read-only scopes must be deleted and reauthorized before live compose/send/modify actions can succeed.

## Entry template

```markdown
## YYYY-MM-DD — Phase XX: <title>

### Summary
- 

### Files changed
- 

### Tests run
- `pytest -q` — pass/fail

### Smoke tests
- App startup:
- Dashboard:
- Key workflow:

### Documentation updated
- 

### Known issues
- 

### Recommended next actions
- 
```
