# Скачивает QuickJS-ng qjs.exe (Windows x64) в vidgrab\assets.
#
# qjs нужен yt-dlp для решения JS-задач YouTube (nsig/PO-token). Без него
# публичные видео могут отдавать ссылки, падающие с HTTP 403.
$ErrorActionPreference = "Stop"

$Version = "0.17.0"
$Sha256 = "2aeabf0092c3262d6b2609824418f7dd7ed1f1df939f73b2b15645230cac0d77"
$Url = "https://github.com/quickjs-ng/quickjs/releases/download/v$Version/qjs-windows-x86_64.exe"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CacheDir = Join-Path $Root "tools\qjs-cache"
$CacheFile = Join-Path $CacheDir "qjs-windows-x86_64.exe"
$Asset = Join-Path $Root "vidgrab\assets\qjs.exe"

if (Test-Path $Asset) {
    Write-Host "qjs.exe уже на месте: $Asset"
    exit 0
}

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Asset) | Out-Null

$needDownload = $true
if (Test-Path $CacheFile) {
    $hash = (Get-FileHash -Algorithm SHA256 $CacheFile).Hash.ToLower()
    if ($hash -eq $Sha256) { $needDownload = $false }
}

if ($needDownload) {
    Write-Host "Скачиваю QuickJS-ng $Version ..."
    $tmp = "$CacheFile.part"
    Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
    $hash = (Get-FileHash -Algorithm SHA256 $tmp).Hash.ToLower()
    if ($hash -ne $Sha256) {
        Remove-Item -Force $tmp
        throw "SHA-256 qjs.exe не совпал: $hash"
    }
    Move-Item -Force $tmp $CacheFile
}

$bytes = [System.IO.File]::ReadAllBytes($CacheFile)
if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
    throw "$CacheFile не является PE-файлом Windows"
}

Copy-Item -Force $CacheFile $Asset
Write-Host "Готово: $Asset"
