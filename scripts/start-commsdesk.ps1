param(
    [switch]$NoBackup
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
if (-not (Test-Path -LiteralPath $venvActivate)) {
    throw "Virtual environment not found at $venvActivate"
}
. $venvActivate

python -m alembic upgrade head

$dbPath = Join-Path $root "commsdesk.db"
if (-not $NoBackup -and (Test-Path -LiteralPath $dbPath)) {
    & (Join-Path $root "scripts\backup-commsdesk.ps1")
}

Write-Host ""
Write-Host "RTH CommsDesk local URLs:"
Write-Host "  http://127.0.0.1:8000/"
Write-Host "  http://127.0.0.1:8000/operational-smoke"
Write-Host "  http://127.0.0.1:8000/providers"
Write-Host ""
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
