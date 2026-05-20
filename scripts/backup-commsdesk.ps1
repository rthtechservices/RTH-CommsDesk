param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}
$Root = (Resolve-Path -LiteralPath $Root).Path
$backups = Join-Path $Root "_backups"
New-Item -ItemType Directory -Force -Path $backups | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$zipPath = Join-Path $backups "commsdesk-backup-$stamp.zip"
$temp = Join-Path $backups "backup-staging-$stamp"
New-Item -ItemType Directory -Force -Path $temp | Out-Null

$sensitive = @(
    ".env",
    "gmail_token.json",
    "google_calendar_token.json",
    "microsoft_graph_token.json",
    "client_secret.json"
)

$include = @(
    "commsdesk.db",
    ".env.example",
    "README.md",
    "docs\HELP.md",
    "docs\PHASE_STATUS.md",
    "docs\IMPLEMENTATION_LOG.md",
    "docs\LESSONS_LEARNED.md"
)

foreach ($rel in $include) {
    $src = Join-Path $Root $rel
    if (Test-Path -LiteralPath $src) {
        $dest = Join-Path $temp $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $src -Destination $dest -Force
    }
}

Compress-Archive -LiteralPath (Join-Path $temp "*") -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $temp -Recurse -Force

Write-Host "Backup created: $zipPath"
Write-Host "Sensitive files excluded:"
foreach ($name in $sensitive) {
    Write-Host "  $name"
}
