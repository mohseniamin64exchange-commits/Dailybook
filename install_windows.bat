@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py"
) else (
    set "PY=python"
)

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing/updating Python dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist "instance" mkdir instance
if not exist "backups" mkdir backups

echo Installation completed.
echo Run start_dailybook.bat to start DailyBook.
endlocal
