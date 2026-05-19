# Microsoft Graph Local Delegated Smoke Guide

This guide documents the current local Microsoft Graph delegated configuration for RTH CommsDesk.

## Registered app

Entra application display name: `RTH-CommsDesk`

Local delegated smoke values:

```env
MICROSOFT_TENANT_ID=1ce279ff-f48b-4959-86d5-e9f16a768e6a
MICROSOFT_CLIENT_ID=31f0d287-5142-49b9-a3eb-3d06b50506d9
MICROSOFT_CLIENT_SECRET=
MICROSOFT_ACCOUNT=me
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_AUTH_MODE=delegated
MICROSOFT_GRAPH_SCOPES=User.Read Mail.Read offline_access
MICROSOFT_GRAPH_TOKEN_FILE=./microsoft_graph_token.json
MICROSOFT_GRAPH_OUTLOOK_MAIL_ENABLED=true
MICROSOFT_GRAPH_TEAMS_ENABLED=false
MICROSOFT_GRAPH_OUTLOOK_CALENDAR_READ_ENABLED=false
MICROSOFT_GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

## Client secret or certificate

For the current local delegated/device-code path, no Microsoft client secret or client certificate is required.

Leave this blank:

```env
MICROSOFT_CLIENT_SECRET=
```

Only configure a client secret or certificate if switching to `MICROSOFT_GRAPH_AUTH_MODE=app_only`. App-only mode is not the current local smoke-test path.

## Configured permissions

Phase 17 Outlook read needs only:

- `User.Read`
- `Mail.Read`
- `offline_access`

The current app registration has additional delegated permissions granted, including mail send/read-write, calendar, and chat/channel permissions. CommsDesk still keeps Outlook send, Outlook calendar, and Teams disabled by feature flags and implementation boundaries. Extra Entra permissions do not enable those features unless code and local feature flags also allow them.

## Public client/device-code note

The local delegated flow uses device-code authorization. If `POST /api/graph/test` fails with a public-client or device-code client error, check the app registration under Authentication and enable the public client/native client flow setting for local testing.

## Token file

The delegated token is stored locally at:

```text
./microsoft_graph_token.json
```

Do not commit this file. Delete it only when intentionally forcing Microsoft Graph reauthorization:

```powershell
Remove-Item ".\microsoft_graph_token.json" -Force -ErrorAction SilentlyContinue
```

## Smoke test commands

From the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In a second PowerShell window:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/graph/test" | ConvertTo-Json -Depth 8
```

Expected first-run behavior:

- If no token exists, the response should be sanitized and indicate authorization is required.
- Complete the Microsoft device-code login using the displayed instructions.
- Retry the same command.

Expected successful behavior:

- `success` is `true`.
- `auth_mode` is `delegated`.
- `account` is `me`.
- No access token, refresh token, authorization header, or secret is returned.

Then test Outlook sync:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/sync/outlook" | ConvertTo-Json -Depth 8
```

Then open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/providers
```

Confirm Outlook messages appear with source `outlook` and that provider status shows Microsoft Graph delegated auth and Outlook mail read as configured/live.

## Current boundary

This local Graph setup is for Outlook mail read only.

Still disabled/not implemented:

- Outlook mail send.
- Outlook calendar read/write.
- Teams live sync/write.

Those should remain parked until the Gmail/Google Calendar operational test workflow is proven in later phases.
