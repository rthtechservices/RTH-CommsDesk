param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$RunMigrations,
    [switch]$RunSyncIfNeeded,
    [switch]$RunBackfillPage,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

function Resolve-CommsDeskRoot {
    $computer = $env:COMPUTERNAME
    $known = @{
        "RTH-PREDATOR" = "D:\OneDrive - RTH Tech Services Inc\CODE\RTH-CommsDesk\RTH-CommsDesk"
        "RTH-SURFACE" = "C:\Users\RohanHare\OneDrive - RTH Tech Services Inc\CODE\RTH-CommsDesk\RTH-CommsDesk"
    }
    if ($known.ContainsKey($computer) -and (Test-Path -LiteralPath $known[$computer])) {
        return (Resolve-Path -LiteralPath $known[$computer]).Path
    }
    if (Test-Path -LiteralPath (Join-Path (Get-Location) "pyproject.toml")) {
        return (Get-Location).Path
    }
    $entered = Read-Host "Enter RTH-CommsDesk repository path"
    if (-not (Test-Path -LiteralPath $entered)) {
        throw "Repository path not found: $entered"
    }
    return (Resolve-Path -LiteralPath $entered).Path
}

$root = Resolve-CommsDeskRoot
Set-Location -LiteralPath $root

$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $venvActivate) {
    if (-not $env:VIRTUAL_ENV -or -not $env:VIRTUAL_ENV.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        . $venvActivate
    }
}

if ($RunMigrations) {
    Write-Host "Running Alembic migrations (upgrade head)..."
    python -m alembic upgrade head
}

try {
    $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/healthz"
    Write-Host "Health check OK: $($health.status)"
} catch {
    throw "CommsDesk is not reachable at $BaseUrl. Start the app first (for example: .\scripts\start-commsdesk.ps1)."
}

$syncStatus = $null
try {
    $syncStatus = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/sync/gmail/status"
} catch {
    Write-Host "Warning: Unable to read Gmail sync status from /api/sync/gmail/status."
}

if ($syncStatus) {
    $lastSync = $syncStatus.last_successful_sync_at
    if (-not $lastSync) {
        Write-Host "Gmail sync/backfill status: no successful Gmail sync recorded yet."
        if ($RunSyncIfNeeded) {
            Write-Host "Running Gmail sync now (read-only)..."
            $syncResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/sync/gmail"
            Write-Host "Sync completed: fetched=$($syncResult.fetched_count) inserted=$($syncResult.inserted_count)"
        } else {
            Write-Host "Guide: run POST $BaseUrl/api/sync/gmail (or click Sync Gmail on dashboard) before relying on cleanup candidates."
            Write-Host "Guide: optionally run POST $BaseUrl/api/sync/gmail/backfill for older inbox pages."
        }
    } else {
        Write-Host "Gmail sync/backfill status: last successful sync at $lastSync"
    }
}

if ($RunBackfillPage) {
    Write-Host "Running one Gmail backfill page (read-only)..."
    $backfillResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/sync/gmail/backfill"
    Write-Host "Backfill completed: fetched=$($backfillResult.fetched_count) inserted=$($backfillResult.inserted_count)"
}

Write-Host "Refreshing mailbox cleanup candidates..."
$refreshResult = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/mailbox-cleanup/refresh"
$summary = $refreshResult.summary
$posture = $refreshResult.execution_posture

try {
    $summaryResult = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/mailbox-cleanup/summary"
    if ($summaryResult -and $summaryResult.summary) {
        $summary = $summaryResult.summary
    }
    if ($summaryResult -and $summaryResult.execution_posture) {
        $posture = $summaryResult.execution_posture
    }
} catch {
    Write-Host "Warning: /api/mailbox-cleanup/summary unavailable, using refresh payload summary."
}

Write-Host ""
Write-Host "Mailbox cleanup smoke summary (local, non-destructive):"
Write-Host "  total cleanup candidates       : $($summary.total_cleanup_candidates)"
Write-Host "  high-confidence candidates     : $($summary.high_confidence_candidates)"
Write-Host "  protected candidates           : $($summary.protected_candidates)"
Write-Host "  Gmail label-capable candidates : $($summary.gmail_label_capable_candidates)"
Write-Host "  Gmail archive-capable candidates: $($summary.gmail_archive_capable_candidates)"
Write-Host "  delete candidates              : $($summary.delete_candidates)"
Write-Host "  blocked candidates             : $($summary.blocked_candidates)"
Write-Host ""
Write-Host "Cleanup execution posture: $($posture.label)"
Write-Host "  $($posture.detail)"
Write-Host ""
Write-Host "Mailbox cleanup UI: $BaseUrl/bulk-triage/mailbox-cleanup"
Write-Host "Safety: this script does not perform external Gmail cleanup writes."

if ($Open) {
    Start-Process "$BaseUrl/bulk-triage/mailbox-cleanup"
}
