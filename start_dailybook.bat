@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run install_windows.bat first.
    exit /b 1
)

if not exist "instance" mkdir instance
if not exist "backups" mkdir backups

set "DAILYBOOK_HOST=0.0.0.0"

echo DailyBook is starting. Default port: 4000
echo The saved Admin setting is applied after each restart.
.venv\Scripts\python.exe run.py
endlocal
