import json
from datetime import datetime
from pathlib import Path

from vidgrab import APP_NAME, APP_VERSION
from vidgrab.report import build_report, report_path, write_report
from vidgrab.settings import Settings
from vidgrab.utils import app_data_dir, log_path


def _selftest() -> dict:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "ok": True,
        "python": "3.11.9",
        "frozen": True,
        "executable": "C:/Apps/VidGrab/VidGrab.exe",
        "platform": "Windows-11",
        "checks": {
            "yt_dlp": "2026.10.26",
            "pyside6": "6.8.3",
            "ffmpeg_path": "C:/Apps/VidGrab/_internal/vidgrab/assets/ffmpeg.exe",
            "ffmpeg_version": "ffmpeg version 8.0",
            "qjs_path": "C:/Apps/VidGrab/_internal/vidgrab/assets/qjs.exe",
            "qjs_version": "0.17.0",
        },
        "errors": [],
        "warnings": [],
    }


def test_report_contains_diagnostics(appdata, tmp_path):
    log_path().parent.mkdir(parents=True, exist_ok=True)
    log_path().write_text(
        "\n".join(f"строка {i}" for i in range(700)), encoding="utf-8"
    )
    settings = Settings(
        last_folder=str(tmp_path),
        cookies_from_browser="chrome",
        cookies_file="C:/secret/cookies.txt",
        youtube_client="tv",
    )
    text = build_report(settings, _selftest())

    assert APP_NAME in text and APP_VERSION in text
    assert "yt-dlp: 2026.10.26" in text
    assert "qjs версия: 0.17.0" in text
    assert "Cookies из браузера: chrome" in text
    assert "Файл cookies.txt: задан" in text
    assert "C:/secret/cookies.txt" not in text  # путь к cookies не утекает
    assert "строка 699" in text
    assert "строка 0" not in text  # только хвост лога
    assert "Последние 500 строк" in text


def test_report_without_log(appdata):
    text = build_report(Settings(), _selftest())
    assert "лог ещё не создан" in text
    assert "Результат: OK" in text


def test_report_when_selftest_failed(appdata):
    selftest = _selftest()
    selftest["ok"] = False
    selftest["errors"] = ["ffmpeg не найден"]
    text = build_report(Settings(), selftest)
    assert "ЕСТЬ ОШИБКИ" in text
    assert "Ошибка: ffmpeg не найден" in text


def test_write_report_creates_file(appdata):
    now = datetime(2025, 10, 29, 17, 40, 5)
    path = write_report(Settings(), _selftest(), now=now)
    assert path.is_file()
    assert path.parent == app_data_dir() / "reports"
    assert path.name == "report-20251029-174005.txt"
    content = path.read_text(encoding="utf-8")
    assert "## Система" in content
    assert "## Самопроверка" in content
    json.dumps(_selftest())  # selftest остаётся сериализуемым


def test_report_path_format():
    path = report_path(datetime(2026, 1, 2, 3, 4, 5))
    assert path.name == "report-20260102-030405.txt"
    assert str(path).endswith(".txt")
    assert Path(path).parent.name == "reports"
