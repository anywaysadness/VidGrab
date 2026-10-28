# Скачивает Windows-сборку ffmpeg (gyan.dev essentials) в vidgrab\assets\ffmpeg.exe.
param(
    [string]$Url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$root = Split-Path -Parent $PSScriptRoot
$assets = Join-Path $root "vidgrab\assets"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("vidgrab-ffmpeg-" + [Guid]::NewGuid().ToString("N"))
$zip = Join-Path $tmp "ffmpeg.zip"
$extract = Join-Path $tmp "extract"

New-Item -ItemType Directory -Force -Path $assets, $tmp, $extract | Out-Null

try {
    Write-Host "Скачиваю ffmpeg: $Url"
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        $ErrorActionPreference = "Continue"
        & curl.exe -fL --retry 3 --retry-delay 2 --connect-timeout 20 -o $zip $Url
        $curlExit = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($curlExit -ne 0) { throw "curl.exe завершился с кодом $curlExit" }
    }
    else {
        Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
    }

    Expand-Archive -Path $zip -DestinationPath $extract -Force

    $ffmpeg = Get-ChildItem -Path $extract -Recurse -Filter "ffmpeg.exe" -File | Select-Object -First 1
    if (-not $ffmpeg) { throw "ffmpeg.exe не найден в архиве" }
    Copy-Item $ffmpeg.FullName (Join-Path $assets "ffmpeg.exe") -Force

    $ffprobe = Get-ChildItem -Path $extract -Recurse -Filter "ffprobe.exe" -File | Select-Object -First 1
    if ($ffprobe) { Copy-Item $ffprobe.FullName (Join-Path $assets "ffprobe.exe") -Force }

    $target = Join-Path $assets "ffmpeg.exe"
    Write-Host "Готово: $target ($([math]::Round((Get-Item $target).Length / 1MB, 1)) МБ)"
    $ErrorActionPreference = "Continue"
    & $target -version | Select-Object -First 1
    $ErrorActionPreference = "Stop"
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
