#!/usr/bin/env bash
# Скачивает QuickJS-ng qjs.exe (Windows x64) в vidgrab/assets.
#
# qjs нужен yt-dlp для решения JS-задач YouTube (nsig/PO-token). Без него
# публичные видео могут отдавать ссылки, падающие с HTTP 403.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.17.0"
SHA256="2aeabf0092c3262d6b2609824418f7dd7ed1f1df939f73b2b15645230cac0d77"
URL="https://github.com/quickjs-ng/quickjs/releases/download/v${VERSION}/qjs-windows-x86_64.exe"
CACHE_DIR="$ROOT/tools/qjs-cache"
CACHE_FILE="$CACHE_DIR/qjs-windows-x86_64.exe"
ASSET="$ROOT/vidgrab/assets/qjs.exe"

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

if [ -f "$ASSET" ]; then
    echo "qjs.exe уже на месте: $ASSET"
    exit 0
fi

mkdir -p "$CACHE_DIR" "$ROOT/vidgrab/assets"
if [ ! -f "$CACHE_FILE" ] || [ "$(sha256_of "$CACHE_FILE")" != "$SHA256" ]; then
    echo "Скачиваю QuickJS-ng $VERSION ..."
    tmp="$CACHE_FILE.part"
    curl -fsSL --retry 3 --max-time 180 -o "$tmp" "$URL"
    actual="$(sha256_of "$tmp")"
    if [ "$actual" != "$SHA256" ]; then
        rm -f "$tmp"
        echo "Ошибка: SHA-256 qjs.exe не совпал: $actual" >&2
        exit 1
    fi
    mv "$tmp" "$CACHE_FILE"
fi

# Проверка, что это действительно PE-файл Windows, а не HTML-ошибка.
magic="$(head -c 2 "$CACHE_FILE" | od -An -tx1 | tr -d ' \n')"
if [ "$magic" != "4d5a" ]; then
    echo "Ошибка: $CACHE_FILE не является PE-файлом (magic=$magic)" >&2
    exit 1
fi

cp "$CACHE_FILE" "$ASSET"
echo "Готово: $ASSET"
