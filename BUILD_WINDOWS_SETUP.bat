@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator access...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

where winget >nul 2>&1
if errorlevel 1 (
  echo Windows Package Manager ^(winget^) is required to prepare the build computer.
  echo Install App Installer from Microsoft Store, then run this file again.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Installing current Python for the build computer...
    winget install --id Python.Python.3.14 --exact --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :failed
  )
)

if not exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" if not exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
  echo Installing Inno Setup 6 for the build computer...
  winget install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :failed
)

echo Building and testing DailyBook...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\build_installer.ps1" -Clean
if errorlevel 1 goto :failed

echo.
echo Setup is ready:
echo %~dp0installer\output\DailyBook-Setup-x64.exe
explorer.exe /select,"%~dp0installer\output\DailyBook-Setup-x64.exe"
pause
exit /b 0

:failed
echo.
echo Setup build failed. Review the message above.
pause
exit /b 1
