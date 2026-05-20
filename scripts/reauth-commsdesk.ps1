param(
    [switch]$Gmail,
    [switch]$GoogleCalendar,
    [switch]$MicrosoftGraph,
    [switch]$All
)

$ErrorActionPreference = "Stop"

if (-not ($Gmail -or $GoogleCalendar -or $MicrosoftGraph -or $All)) {
    Write-Host "Specify one or more switches: -Gmail, -GoogleCalendar, -MicrosoftGraph, or -All."
    exit 1
}

function Remove-TokenIfRequested {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
        Write-Host "Deleted token file: $Path"
    } else {
        Write-Host "Token file not present: $Path"
    }
}

if ($All -or $Gmail) {
    Remove-TokenIfRequested ".\gmail_token.json"
    Write-Host "Gmail scopes:"
    Write-Host "  https://www.googleapis.com/auth/gmail.readonly"
    Write-Host "  https://www.googleapis.com/auth/gmail.compose"
    Write-Host "  https://www.googleapis.com/auth/gmail.send"
    Write-Host "  https://www.googleapis.com/auth/gmail.modify"
    Write-Host "Next: start the app, then run POST /api/sync/gmail or use the dashboard Sync Gmail button."
}

if ($All -or $GoogleCalendar) {
    Remove-TokenIfRequested ".\google_calendar_token.json"
    Write-Host "Google Calendar scopes:"
    Write-Host "  https://www.googleapis.com/auth/calendar.freebusy"
    Write-Host "  https://www.googleapis.com/auth/calendar.events"
    Write-Host "Next: run .\scripts\smoke-commsdesk.ps1 and review Google Calendar readiness."
}

if ($All -or $MicrosoftGraph) {
    Remove-TokenIfRequested ".\microsoft_graph_token.json"
    Write-Host "Microsoft Graph scopes:"
    Write-Host "  User.Read Mail.Read offline_access"
    Write-Host "Next: run POST /api/graph/test. Complete the device-code login if prompted, then retry."
}

Write-Host "Client secrets and .env were not deleted."
