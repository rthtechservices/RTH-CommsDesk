param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$url = "$BaseUrl/api/operational-smoke/run"
$result = Invoke-RestMethod -Method Post -Uri $url
Write-Host "Smoke run #$($result.run_id): $($result.overall_status)"
if ($result.summary) {
    Write-Host "Passed=$($result.summary.passed) Warning=$($result.summary.warning) Failed=$($result.summary.failed) Skipped=$($result.summary.skipped)"
}

$checks = @($result.checks | Where-Object { $_.status -in @("failed", "warning") })
foreach ($check in $checks) {
    Write-Host "[$($check.status)] $($check.label): $($check.next_action)"
}

if ($Open) {
    Start-Process "$BaseUrl/operational-smoke"
}
