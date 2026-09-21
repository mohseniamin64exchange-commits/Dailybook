[CmdletBinding()]
param(
    [switch]$Clean,
    [string]$InnoSetup = "",
    [switch]$UseCurrentPython,
    [switch]$SkipTests,
    [ValidateSet("All", "Server", "Launcher", "Service", "Installer")]
    [string]$Stage = "All"
)

$ErrorActionPreference = "Stop"
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $InstallerRoot
$BuildRoot = Join-Path $InstallerRoot "build"
$DistRoot = Join-Path $InstallerRoot "dist"
$ServiceDir = Join-Path $InstallerRoot "service"
$Venv = Join-Path $InstallerRoot ".venv-build"

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    $PreviousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $CommandOutput = @(& $File @Arguments 2>&1)
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorAction
    $CommandOutput | ForEach-Object { Write-Host $_ }
    if ($ExitCode -ne 0) {
        $Details = (($CommandOutput | Select-Object -Last 20) -join ' | ').Replace("`r", ' ').Replace("`n", ' ')
        Write-Host "::error title=Build command failed::$Details"
        throw "Command failed ($ExitCode): $File $($Arguments -join ' ')"
    }
}

if ($Clean) {
    foreach ($Path in @($BuildRoot, $DistRoot, $ServiceDir, (Join-Path $InstallerRoot "output"))) {
        if (Test-Path $Path) { Remove-Item $Path -Recurse -Force }
    }
}

if ($UseCurrentPython) {
    $PythonCommand = Get-Command "python.exe" -ErrorAction Stop
    $Python = $PythonCommand.Source
} elseif (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    # Prefer the regular `python` command so modern installs (for example 3.14)
    # work even when the Python Launcher has no `-3.11` runtime registered.
    $PythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $BasePython = $PythonCommand.Source
        $BaseArgs = @()
    } else {
        $PyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if (-not $PyLauncher) {
            $LauncherCandidates = @(
                "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe",
                "$env:SystemRoot\py.exe"
            ) | Where-Object { Test-Path $_ }
            if (-not $LauncherCandidates) {
                throw "Python 3.11 or newer was not found. Install a current 64-bit Python and run the build again."
            }
            $BasePython = $LauncherCandidates[0]
        } else {
            $BasePython = $PyLauncher.Source
        }
        # No fixed version selector: use the launcher's default installed Python.
        $BaseArgs = @()
    }

    Write-Host "Using Python: $BasePython" -ForegroundColor Cyan
    Invoke-Checked $BasePython ($BaseArgs + @("-m", "venv", $Venv))
}

if (-not $UseCurrentPython) {
    $Python = Join-Path $Venv "Scripts\python.exe"
    Invoke-Checked $Python @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked $Python @("-m", "pip", "install", "-r", (Join-Path $ProjectRoot "windows\requirements-build.txt"))
}
if (-not $SkipTests -and $Stage -eq "All") {
    Invoke-Checked $Python @("-m", "pytest", "-q", $ProjectRoot)
}

$ServerDist = Join-Path $DistRoot "server"
$LauncherDist = Join-Path $DistRoot "launcher"
New-Item -ItemType Directory -Force -Path $BuildRoot, $ServerDist, $LauncherDist | Out-Null

if ($Stage -in @("All", "Server")) {
$ServerArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
    "--name", "DailyBookServer", "--paths", $ProjectRoot,
    "--distpath", $ServerDist, "--workpath", (Join-Path $BuildRoot "server"),
    "--specpath", $BuildRoot,
    "--add-data", "$(Join-Path $ProjectRoot 'app\templates');app\templates",
    "--add-data", "$(Join-Path $ProjectRoot 'app\static');app\static",
    (Join-Path $ProjectRoot "run.py")
)
Invoke-Checked $Python $ServerArgs
}

if ($Stage -in @("All", "Launcher")) {
$LauncherArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "DailyBook", "--distpath", $LauncherDist,
    "--workpath", (Join-Path $BuildRoot "launcher"), "--specpath", $BuildRoot,
    (Join-Path $ProjectRoot "windows\launcher.py")
)
Invoke-Checked $Python $LauncherArgs
}

if ($Stage -in @("All", "Service")) {
New-Item -ItemType Directory -Force -Path $ServiceDir | Out-Null
$WinSw = Join-Path $ServiceDir "DailyBookService.exe"
if (-not (Test-Path $WinSw)) {
    Invoke-WebRequest "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe" -OutFile $WinSw
}

@'
<service>
  <id>DailyBook</id>
  <name>DailyBook Server</name>
  <description>DailyBook local network journal server</description>
  <executable>%BASE%\..\server\DailyBookServer.exe</executable>
  <workingdirectory>%BASE%\..\server</workingdirectory>
  <env name="DAILYBOOK_DATA_DIR" value="C:\ProgramData\DailyBook" />
  <env name="DAILYBOOK_HOST" value="0.0.0.0" />
  <env name="DAILYBOOK_SERVICE_MODE" value="1" />
  <startmode>Automatic</startmode>
  <delayedAutoStart>true</delayedAutoStart>
  <stoptimeout>15sec</stoptimeout>
  <onfailure action="restart" delay="10 sec" />
  <logpath>C:\ProgramData\DailyBook\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>5120</sizeThreshold>
    <keepFiles>5</keepFiles>
  </log>
</service>
'@ | Set-Content -Encoding UTF8 (Join-Path $ServiceDir "DailyBookService.xml")

}
if ($Stage -in @("All", "Installer")) {
$Candidates = @(
    $InnoSetup,
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $Candidates) {
    throw "Inno Setup 6 was not found. Install it or pass -InnoSetup with ISCC.exe path."
}

Invoke-Checked $Candidates[0] @(Join-Path $InstallerRoot "DailyBook.iss")
Write-Host "Setup created in installer\output\DailyBook-Setup-x64.exe" -ForegroundColor Green
}

