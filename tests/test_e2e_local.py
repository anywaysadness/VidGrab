"""Интеграционные тесты: реальный yt-dlp + локальный HTTP-сервер + ffmpeg.

YouTube и другие сайты здесь не используются специально: тесты не должны зависеть
от доступности интернета и региональных блокировок.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from vidgrab.downloader import DownloadWorker, MetadataWorker
from vidgrab.main import _download_sync, _extract_metadata

ROOT = Path(__file__).resolve().parents[1]


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    assert path, "для интеграционных тестов нужен ffmpeg в PATH"
    return path


def _make_sample(path: Path) -> None:
    ffmpeg = _ffmpeg()
    for codec in ("libx264", "mpeg4"):
        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            codec,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
        result = subprocess.run(command, capture_output=True, timeout=120)
        if result.returncode == 0 and path.is_file():
            return
    pytest.fail(f"не удалось создать тестовое видео: {result.stderr[-800:]}")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs):  # noqa: D401 - подавляем шум
        pass


@pytest.fixture()
def local_video(tmp_path):
    sample = tmp_path / "sample.mp4"
    _make_sample(sample)
    handler = functools.partial(_QuietHandler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/sample.mp4"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.integration
def test_sync_extract_and_download(local_video, tmp_path):
    ffmpeg = Path(_ffmpeg())
    summary = _extract_metadata(local_video, ffmpeg)
    assert summary["title"]
    assert "best" in summary["qualities"]

    outdir = tmp_path / "out"
    path = _download_sync(local_video, "best", outdir, ffmpeg)
    assert path.is_file()
    assert path.stat().st_size > 1000


@pytest.mark.integration
def test_qthread_workers_real_download(qapp, local_video, tmp_path):
    ffmpeg = Path(_ffmpeg())
    metadata_worker = MetadataWorker(local_video, ffmpeg)
    summaries: list[dict] = []
    failures: list[tuple[str, str]] = []
    metadata_worker.ready.connect(summaries.append)
    metadata_worker.failed.connect(lambda code, message: failures.append((code, message)))
    metadata_worker.start()
    assert metadata_worker.wait(120_000), "проверка ссылки не завершилась"
    qapp.processEvents()
    assert not failures
    assert summaries and "best" in summaries[0]["qualities"]

    outdir = tmp_path / "qthread-out"
    download_worker = DownloadWorker(local_video, "best", outdir, ffmpeg)
    completed: list[str] = []
    progress: list[int] = []
    download_worker.completed.connect(completed.append)
    download_worker.progress.connect(lambda percent, *_rest: progress.append(percent))
    download_worker.start()
    assert download_worker.wait(180_000), "загрузка не завершилась"
    qapp.processEvents()
    assert completed, "нет сигнала completed"
    assert Path(completed[0]).is_file()
    assert progress, "не было событий прогресса"


@pytest.mark.integration
def test_cli_json_mode(local_video, tmp_path):
    env = dict(os.environ)
    env["VIDGRAB_APPDATA"] = str(tmp_path / "appdata")
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--cli",
            local_video,
            "--quality",
            "best",
            "--json",
            "-o",
            str(tmp_path / "cli-out"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert Path(payload["path"]).is_file()


@pytest.mark.integration
def test_cli_invalid_url(tmp_path):
    env = dict(os.environ)
    env["VIDGRAB_APPDATA"] = str(tmp_path / "appdata")
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--cli", "не ссылка", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "invalid_url"
