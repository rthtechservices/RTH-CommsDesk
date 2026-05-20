#Requires -Version 5.1
<#
.SYNOPSIS
    Phase 25 operator guide: controlled Gmail cleanup execution.
    Shows current environment posture and guides the operator through the
    dry-run → live confirmation workflow. Does NOT perform any Gmail writes.

.DESCRIPTION
    Use this script before executing any Gmail cleanup action to verify:
    - Which feature flags are currently set
    - Whether the system is in dry-run or live mode
    - That the required flag sequence is understood before confirming

    SAFE TO RUN AT ANY TIME. This script is read-only and informational.
    It never modifies Gmail, the database, or any external system.

.EXAMPLE
    .\scripts\test-gmail-cleanup-execution.ps1
    .\scripts\test-gmail-cleanup-execution.ps1 -ShowSmoke
#>

param(
    [switch]$ShowSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent

# ─── Activate virtual environment ────────────────────────────────────────────
$VenvActivate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    . $VenvActivate
    Write-Host "[venv] Activated: $VenvActivate" -ForegroundColor DarkGray
} else {
    Write-Warning "[venv] No .venv found at $VenvActivate — using system Python."
}

# ─── Load .env if present ─────────────────────────────────────────────────────
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)$') {
            $key   = $Matches[1]
            $value = $Matches[2].Trim('"').Trim("'")
            if (-not [System.Environment]::GetEnvironmentVariable($key)) {
                [System.Environment]::SetEnvironmentVariable($key, $value)
            }
        }
    }
    Write-Host "[env] Loaded .env from: $EnvFile" -ForegroundColor DarkGray
} else {
    Write-Host "[env] No .env file found. Using environment variables only." -ForegroundColor DarkYellow
}

function Get-EnvBool([string]$Name) {
    $v = [System.Environment]::GetEnvironmentVariable($Name)
    return $v -in @("true","1","yes","True")
}
function Get-EnvStr([string]$Name, [string]$Default = "(not set)") {
    $v = [System.Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
    return $v
}

# ─── Read current posture ─────────────────────────────────────────────────────
$GmailWrite          = Get-EnvBool "GMAIL_WRITE_ENABLED"
$LabelArchive        = Get-EnvBool "GMAIL_LABEL_ARCHIVE_ENABLED"
$DryRun              = Get-EnvBool "EXTERNAL_WRITE_DRY_RUN"
$OperationalTest     = Get-EnvBool "OPERATIONAL_TEST_MODE"
$Provider            = Get-EnvStr  "EXECUTION_PROVIDER" "mock"
$GmailToken          = Get-EnvStr  "GMAIL_TOKEN_FILE" "gmail_token.json"

Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  RTH CommsDesk — Phase 25 Cleanup Execution Posture  " -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── Flag matrix ─────────────────────────────────────────────────────────────
$rows = @(
    @{ Flag = "EXECUTION_PROVIDER";          Value = $Provider;          RequiredFor = "live cleanup" }
    @{ Flag = "GMAIL_WRITE_ENABLED";          Value = $GmailWrite;        RequiredFor = "any Gmail write" }
    @{ Flag = "GMAIL_LABEL_ARCHIVE_ENABLED";  Value = $LabelArchive;      RequiredFor = "label/archive cleanup" }
    @{ Flag = "EXTERNAL_WRITE_DRY_RUN";       Value = $DryRun;            RequiredFor = "safe dry-run check" }
    @{ Flag = "OPERATIONAL_TEST_MODE";        Value = $OperationalTest;   RequiredFor = "test execution gate" }
    @{ Flag = "GMAIL_TOKEN_FILE";             Value = $GmailToken;        RequiredFor = "OAuth token path" }
)

foreach ($row in $rows) {
    $val = $row.Value
    $flagColor = if ($val -is [bool]) {
        if ($val) { "Green" } else { "DarkGray" }
    } else { "Yellow" }
    $display = if ($val -is [bool]) { if ($val) { "true" } else { "false" } } else { $val }
    Write-Host ("  {0,-40} = " -f $row.Flag) -NoNewline
    Write-Host ("{0,-12}" -f $display) -ForegroundColor $flagColor -NoNewline
    Write-Host ("  [{0}]" -f $row.RequiredFor) -ForegroundColor DarkGray
}

Write-Host ""

# ─── Determine cleanup posture ────────────────────────────────────────────────
Write-Host "  Current cleanup posture:" -NoNewline
if ($Provider -notin @("external","live","google")) {
    Write-Host " MOCK (no Gmail write, safe to test flow)" -ForegroundColor Yellow
} elseif (-not $GmailWrite -or -not $LabelArchive) {
    Write-Host " BLOCKED (required write flags are off)" -ForegroundColor Red
} elseif ($DryRun) {
    Write-Host " DRY-RUN (provider is external but EXTERNAL_WRITE_DRY_RUN=true)" -ForegroundColor Yellow
} else {
    Write-Host " LIVE (provider is external, flags enabled, dry-run is OFF)" -ForegroundColor Red
    Write-Host "  *** Live mode: Gmail WILL be modified after approve+confirm ***" -ForegroundColor Red
}

Write-Host ""

# ─── Required flags for live cleanup ─────────────────────────────────────────
Write-Host "  Required .env for live Gmail cleanup execution:" -ForegroundColor Cyan
Write-Host ""
Write-Host "    EXECUTION_PROVIDER=external" -ForegroundColor Gray
Write-Host "    GMAIL_WRITE_ENABLED=true" -ForegroundColor Gray
Write-Host "    GMAIL_LABEL_ARCHIVE_ENABLED=true" -ForegroundColor Gray
Write-Host "    OPERATIONAL_TEST_MODE=true   (required by execution_test_policy)" -ForegroundColor Gray
Write-Host "    EXTERNAL_WRITE_DRY_RUN=false (only after dry-run confirmed safe)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Always run a dry-run first before enabling EXTERNAL_WRITE_DRY_RUN=false." -ForegroundColor Yellow
Write-Host ""

# ─── Cleanup workflow reminder ────────────────────────────────────────────────
Write-Host "  Phase 25 Gmail cleanup operator workflow:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Run this script to verify posture." -ForegroundColor Gray
Write-Host "  2. Open /bulk-triage/mailbox-cleanup to review cleanup candidates." -ForegroundColor Gray
Write-Host "  3. Mark sender noise if not already done." -ForegroundColor Gray
Write-Host "  4. Click 'Prepare label', 'Prepare archive', or 'Prepare label + archive'." -ForegroundColor Gray
Write-Host "     This creates an execution record. No Gmail write occurs yet." -ForegroundColor Gray
Write-Host "  5. Open /executions and find the new execution record." -ForegroundColor Gray
Write-Host "  6. Review the Gmail Cleanup Confirmation section on the detail page." -ForegroundColor Gray
Write-Host "     Check: sender, message count, mode, label, archive flag, posture." -ForegroundColor Gray
Write-Host "  7. Review recovery guidance before approving." -ForegroundColor Gray
Write-Host "  8. If posture is dry-run: click Approve → Confirm. Result recorded, no Gmail write." -ForegroundColor Gray
Write-Host "  9. If posture is live: verify you have reviewed all details and understand recovery." -ForegroundColor Gray
Write-Host "     Click Approve → Confirm. Gmail is modified." -ForegroundColor Gray
Write-Host " 10. Check the audit trail on the execution detail page." -ForegroundColor Gray
Write-Host ""

# ─── Optional smoke ───────────────────────────────────────────────────────────
if ($ShowSmoke) {
    Write-Host "  Fetching operational smoke from /api/smoke/status ..." -ForegroundColor Cyan
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/smoke/status" -UseBasicParsing -TimeoutSec 5
        Write-Host ($resp.Content | ConvertFrom-Json | ConvertTo-Json -Depth 3) -ForegroundColor DarkGray
    } catch {
        Write-Host "  Could not reach app on localhost:8000. Start the app first." -ForegroundColor DarkYellow
    }
    Write-Host ""
}

Write-Host "  Dashboard : http://localhost:8000/" -ForegroundColor Green
Write-Host "  Cleanup   : http://localhost:8000/bulk-triage/mailbox-cleanup" -ForegroundColor Green
Write-Host "  Executions: http://localhost:8000/executions" -ForegroundColor Green
Write-Host "  Providers : http://localhost:8000/providers" -ForegroundColor Green
Write-Host "  Smoke     : http://localhost:8000/operational-smoke" -ForegroundColor Green
Write-Host ""
