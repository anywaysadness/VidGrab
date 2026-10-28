#!/usr/bin/env bash
# Скачивает Windows-сборку ffmpeg (gyan.dev essentials) в vidgrab/assets/ffmpeg.exe.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$ROOT/vidgrab/assets"
URL="${FFMPEG_URL:-https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip}"

mkdir -p "$ASSETS"
CACHE="$ROOT/tools/ffmpeg-cache"
ZIP="$CACHE/$(basename "$URL")"
mkdir -p "$CACHE"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -f "$ZIP" ] && [ "$(stat -c%s "$ZIP")" -gt 50000000 ]; then
    echo "Использую кэш: $ZIP"
else
    echo "Скачиваю ffmpeg: $URL"
    curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 -o "$ZIP.part" "$URL"
    mv "$ZIP.part" "$ZIP"
fi

mkdir -p "$TMP/extract"
python3 -m zipfile -e "$ZIP" "$TMP/extract"

FFMPEG_SRC="$(find "$TMP/extract" -type f -name 'ffmpeg.exe' -print -quit)"
FFPROBE_SRC="$(find "$TMP/extract" -type f -name 'ffprobe.exe' -print -quit)"
if [ -z "$FFMPEG_SRC" ]; then
    echo "Ошибка: ffmpeg.exe не найден в архиве" >&2
    exit 1
fi

cp "$FFMPEG_SRC" "$ASSETS/ffmpeg.exe"
[ -n "$FFPROBE_SRC" ] && cp "$FFPROBE_SRC" "$ASSETS/ffprobe.exe"

# Проверяем, что это PE-файл (MZ), а не HTML-ошибка сервера.
if [ "$(head -c 2 "$ASSETS/ffmpeg.exe" | xxd -p)" != "4d5a" ]; then
    echo "Ошибка: vidgrab/assets/ffmpeg.exe не является PE-файлом" >&2
    exit 1
fi

ls -lh "$ASSETS/ffmpeg.exe" "$ASSETS/ffprobe.exe"
echo "Готово: $ASSETS/ffmpeg.exe"
