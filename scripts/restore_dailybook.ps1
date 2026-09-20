param(
    [Parameter(Mandatory=$true)][string]$BackupFile,
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = "Stop"
$python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$tool = Join-Path $ProjectDir "scripts\db_maintenance.py"
if (-not (Test-Path $BackupFile)) { throw "Backup not found: $BackupFile" }
Write-Host "DailyBook must be stopped before restore." -ForegroundColor Yellow
$answer = Read-Host "Is DailyBook stopped? Type YES to continue"
if ($answer -ne "YES") { throw "Restore cancelled." }
& $python $tool restore $BackupFile
if ($LASTEXITCODE -ne 0) { throw "Restore failed." }

