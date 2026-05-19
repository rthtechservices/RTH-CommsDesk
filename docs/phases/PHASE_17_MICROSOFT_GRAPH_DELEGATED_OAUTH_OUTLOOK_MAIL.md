# Phase 17 — Microsoft Graph Delegated OAuth and Outlook Mail Smoke

## Objective

Add delegated Microsoft Graph OAuth support and prove Outlook mail read ingestion works before adding send, calendar, or Teams write actions.

## Scope

- Delegated Microsoft Graph OAuth for local development.
- Configurable local token file at `MICROSOFT_GRAPH_TOKEN_FILE`.
- Configurable auth mode: `delegated` or `app_only`.
- Configurable delegated scopes: `User.Read Mail.Read offline_access`.
- Preserve the existing app-only client seam.
- Add sanitized `POST /api/graph/test`.
- Implement read-only Outlook mail sync through Graph.
- Normalize Outlook mail into the existing message/thread model.
- Add provider status rows for delegated auth, Outlook mail read, Outlook mail send, Outlook calendar, and Teams.

## Out of scope

- Outlook mail send.
- Outlook calendar read/write.
- Teams sync or Teams writes.
- Any Microsoft Graph write action.
- Scraping Microsoft/Teams surfaces outside supported Graph APIs.

## Implementation notes

- `MICROSOFT_GRAPH_AUTH_MODE=delegated` uses a local device-code flow and stores token material in `MICROSOFT_GRAPH_TOKEN_FILE`.
- `MICROSOFT_GRAPH_AUTH_MODE=app_only` still uses the existing client-credentials seam with `MICROSOFT_CLIENT_SECRET`.
- `POST /api/graph/test` returns only sanitized diagnostics: auth mode, account, configured booleans, success/failure, HTTP status, and sanitized error category/message.
- Delegated Outlook read uses `/me/messages` when `MICROSOFT_ACCOUNT=me`.
- App-only or explicit-account reads use `/users/{MICROSOFT_ACCOUNT}/messages`.
- Outlook mail read uses `$select` for only required fields and follows Graph paging up to the requested limit.
- Teams, Outlook send, and Outlook Calendar provider rows remain disabled/not implemented.

## Configuration

```env
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true
MICROSOFT_GRAPH_AUTH_MODE=delegated
MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read offline_access
MICROSOFT_GRAPH_TOKEN_FILE=./microsoft_graph_token.json
MICROSOFT_TENANT_ID=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_ACCOUNT=me
```

For app-only tenants:

```env
MICROSOFT_GRAPH_AUTH_MODE=app_only
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_ACCOUNT=user@example.com
```

## Acceptance criteria

- [x] `python -m ruff check .` passes.
- [x] `python -m pytest -q` passes.
- [x] `POST /api/graph/test` works with sanitized output.
- [x] Outlook mail read sync works with delegated auth when configured.
- [x] No Outlook send/calendar/Teams writes are enabled.
- [x] Existing Gmail, Google Calendar, Azure OpenAI, mock execution tests still pass.

## Completion notes

Status: completed on 2026-05-19.

Implemented:

- Added delegated/app-only auth mode configuration.
- Added local delegated token-file support and device-code startup.
- Added sanitized Graph test endpoint.
- Added paged read-only Outlook mail Graph fetch.
- Preserved Outlook normalization through the existing connector and sync pipeline.
- Added provider status rows for delegated auth and disabled Microsoft write/unimplemented surfaces.
- Added mocked HTTP tests for delegated read paging, app-only read, device-code startup, sanitized status, and the API route.

Validation:

- `python -m ruff check .` passed.
- `python -m pytest -q` passed.
