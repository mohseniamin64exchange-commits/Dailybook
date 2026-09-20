param(
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot),
    [string]$Destination = ""
)
$ErrorActionPreference = "Stop"
$python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$tool = Join-Path $ProjectDir "scripts\db_maintenance.py"
if (-not (Test-Path $python)) { throw "Python environment not found. Run install_windows.bat first." }
$target = if ($Destination) { $Destination } else { Join-Path $ProjectDir "backups" }
& $python $tool backup --destination $target
if ($LASTEXITCODE -ne 0) { throw "Backup failed." }

