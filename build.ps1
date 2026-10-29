# VidGrab build script: creates dist\VidGrab\VidGrab.exe with PyInstaller.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build.ps1
#   powershell -ExecutionPolicy Bypass -File build.ps1 -SkipInstall
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Clean
#
# Requirements: Windows 10/11 x64, Python 3.11+ (py launcher or python in PATH).
param(
    [string]$Python = "",
    [switch]$SkipInstall,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Внешние команды (python/pip/PyInstaller) пишут прогресс в stderr. При
# ErrorActionPreference=Stop PowerShell считает stderr ошибкой, поэтому
# запускаем их с локально отключённым Stop и проверяем код возврата сами.
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$Quiet
    )
    $ErrorActionPreference = "Continue"
    if ($Quiet) {
        & $FilePath @Arguments *> $null
    }
    else {
        & $FilePath @Arguments
    }
    return $LASTEXITCODE
}

function Assert-Success {
    param([int]$Code, [string]$Message)
    if ($Code -ne 0) {
        throw "$Message (exit code $Code)"
    }
}

function Test-PythonVersion {
    param([string]$Executable, [string[]]$Prefix)
    $code = Invoke-Native $Executable (@($Prefix) + @(
        "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
    )) -Quiet
    return ($code -eq 0)
}

function Get-PythonLauncher {
    param([string]$Requested)

    if ($Requested) {
        return @{ Exe = $Requested; Prefix = @() }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonVersion "py" @("-3.12")) { return @{ Exe = "py"; Prefix = @("-3.12") } }
        if (Test-PythonVersion "py" @("-3.11")) { return @{ Exe = "py"; Prefix = @("-3.11") } }
        if (Test-PythonVersion "py" @("-3")) { return @{ Exe = "py"; Prefix = @("-3") } }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonVersion "python" @()) {
            return @{ Exe = "python"; Prefix = @() }
        }
    }
    throw "Python 3.11+ not found. Install it from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
}

$python = Get-PythonLauncher -Requested $Python
$venv = Join-Path $root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creating virtual environment in $venv ..."
    $code = Invoke-Native $python.Exe (@($python.Prefix) + @("-m", "venv", $venv))
    Assert-Success $code "Failed to create virtual environment"
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies ..."
    $code = Invoke-Native $venvPy @("-m", "pip", "install", "--upgrade", "pip")
    Assert-Success $code "pip upgrade failed"
    $code = Invoke-Native $venvPy @("-m", "pip", "install", "-r", "requirements.txt")
    Assert-Success $code "pip install failed"
}

$ffmpeg = Join-Path $root "vidgrab\assets\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) {
    Write-Host "ffmpeg.exe not found, downloading it ..."
    $code = Invoke-Native "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $root "tools\fetch_ffmpeg.ps1")
    )
    Assert-Success $code "Failed to download ffmpeg"
    if (-not (Test-Path $ffmpeg)) { throw "ffmpeg.exe is missing" }
}

$qjs = Join-Path $root "vidgrab\assets\qjs.exe"
if (-not (Test-Path $qjs)) {
    Write-Host "qjs.exe not found, downloading QuickJS-ng ..."
    $code = Invoke-Native "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $root "tools\fetch_qjs.ps1")
    )
    Assert-Success $code "Failed to download qjs"
    if (-not (Test-Path $qjs)) { throw "qjs.exe is missing" }
}

if ($Clean) {
    Write-Host "Cleaning build/ and dist/ ..."
    Remove-Item -Recurse -Force (Join-Path $root "build"), (Join-Path $root "dist") -ErrorAction SilentlyContinue
}

$argumentList = @(
    "--noconfirm",
    "--windowed",
    "--onedir",
    "--name", "VidGrab",
    "--add-binary", "$ffmpeg;vidgrab/assets",
    "--add-binary", "$qjs;vidgrab/assets",
    "--collect-submodules", "yt_dlp",
    "--collect-data", "yt_dlp",
    "--paths", ".",
    "--distpath", "dist",
    "--workpath", "build",
    "--specpath", ".",
    "main.py"
)

$ffprobe = Join-Path $root "vidgrab\assets\ffprobe.exe"
if (Test-Path $ffprobe) {
    $argumentList = @("--add-binary", "$ffprobe;vidgrab/assets") + $argumentList
}

$icon = Join-Path $root "vidgrab\assets\vidgrab.ico"
if (Test-Path $icon) {
    $argumentList = @("--icon", "vidgrab/assets/vidgrab.ico") + $argumentList
}

Write-Host "Running PyInstaller ..."
$code = Invoke-Native $venvPy (@("-m", "PyInstaller") + $argumentList)
Assert-Success $code "PyInstaller failed"

$exe = Join-Path $root "dist\VidGrab\VidGrab.exe"
if (-not (Test-Path $exe)) { throw "Build finished but $exe was not found" }

$size = [math]::Round((Get-ChildItem (Join-Path $root "dist\VidGrab") -Recurse -File |
    Measure-Object -Property Length -Sum).Sum / 1MB, 1)

Write-Host ""
Write-Host "Build OK: $exe"
Write-Host "Total size: $size MB"
Write-Host "Smoke test: & `"$exe`" --selftest"
