#!/usr/bin/env bash
# Собирает dist/VidGrab/VidGrab.exe в Docker-образе с Wine и Windows Python.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="vidgrab-wine-builder"

if [ ! -f "$ROOT/vidgrab/assets/ffmpeg.exe" ]; then
    echo "Сначала скачайте ffmpeg.exe: bash tools/fetch_ffmpeg.sh" >&2
    exit 1
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Собираю Docker-образ $IMAGE (wine + Windows Python 3.12) ..."
    docker build -t "$IMAGE" -f "$ROOT/tools/Dockerfile.wine" "$ROOT"
fi

echo "Сборка VidGrab.exe под Wine ..."
EXTRA_ARGS=()
if [ -f "$ROOT/vidgrab/assets/ffprobe.exe" ]; then
    EXTRA_ARGS+=(--add-binary 'Z:/src/vidgrab/assets/ffprobe.exe;vidgrab/assets')
fi

docker run --rm -v "$ROOT:/src" -w /src "$IMAGE" \
    wine 'C:\Python311\python.exe' -m PyInstaller \
        --noconfirm --windowed --onedir --name VidGrab \
        --add-binary 'Z:/src/vidgrab/assets/ffmpeg.exe;vidgrab/assets' \
        "${EXTRA_ARGS[@]}" \
        --collect-submodules yt_dlp --collect-data yt_dlp \
        --paths . --distpath dist --workpath build --specpath . \
        main.py

# Файлы созданы root-пользователем контейнера — возвращаем владельца.
docker run --rm -v "$ROOT:/src" "$IMAGE" \
    chown -R "$(id -u):$(id -g)" /src/dist /src/build /src/VidGrab.spec

if [ ! -f "$ROOT/dist/VidGrab/VidGrab.exe" ]; then
    echo "Ошибка: dist/VidGrab/VidGrab.exe не создан" >&2
    exit 1
fi

echo "Готово: $ROOT/dist/VidGrab/VidGrab.exe"
du -sh "$ROOT/dist/VidGrab"
