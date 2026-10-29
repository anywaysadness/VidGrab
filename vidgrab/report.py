"""Текстовый отчёт для диагностики: версии, настройки, хвост лога, selftest."""

from __future__ import annotations

import getpass
import json
import logging
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from vidgrab import APP_NAME, APP_VERSION
from vidgrab.settings import Settings, load_settings
from vidgrab.utils import (
    find_ffmpeg,
    find_quickjs,
    log_path,
    quickjs_version,
    reports_dir,
)

log = logging.getLogger(__name__)

LOG_TAIL_LINES = 500


def _tail(path: Path, limit: int = LOG_TAIL_LINES) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "(лог ещё не создан)"
    except OSError as exc:
        return f"(не удалось прочитать лог: {exc})"
    lines = text.splitlines()
    if len(lines) > limit:
        lines = ["… (показаны последние строки) …", *lines[-limit:]]
    return "\n".join(lines) if lines else "(лог пуст)"


def _settings_block(settings: Settings) -> str:
    cookies_source = settings.cookies_from_browser or "нет"
    cookies_file = "задан" if settings.cookies_file.strip() else "нет"
    return "\n".join(
        [
            f"Папка сохранения: {settings.last_folder}",
            f"Качество: {settings.last_quality}",
            f"Cookies из браузера: {cookies_source}",
            f"Файл cookies.txt: {cookies_file}",  # путь не печатаем: он личный
            f"Клиент YouTube: {settings.youtube_client or 'авто'}",
        ]
    )


def build_report(
    settings: Settings | None = None,
    selftest: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> str:
    """Собирает текст отчёта. Cookies и их содержимое не попадают в отчёт."""
    settings = settings or load_settings()
    if selftest is None:
        try:
            from vidgrab.selftest import collect_selftest

            selftest = collect_selftest()
        except Exception as exc:  # noqa: BLE001 - отчёт должен создаваться всегда
            selftest = {"ok": False, "errors": [f"selftest не выполнен: {exc}"]}

    created = (now or datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M:%S %z")
    ffmpeg = find_ffmpeg()
    qjs = find_quickjs()
    checks = selftest.get("checks") or {}
    errors = selftest.get("errors") or []
    warnings = selftest.get("warnings") or []

    lines = [
        f"{APP_NAME} {APP_VERSION} — отчёт для диагностики",
        f"Создан: {created}",
        "",
        "## Система",
        f"ОС: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"Сборка: {'exe (PyInstaller)' if getattr(sys, 'frozen', False) else 'из исходников'}",
        f"Исполняемый файл: {sys.executable}",
        f"Пользователь: {getpass.getuser()}",
        "",
        "## Компоненты",
        f"yt-dlp: {checks.get('yt_dlp') or '—'}",
        f"Qt/PySide6: {checks.get('pyside6') or '—'}",
        f"ffmpeg: {ffmpeg or 'не найден'}",
        f"ffmpeg версия: {checks.get('ffmpeg_version') or '—'}",
        f"qjs: {qjs or 'не найден'}",
        f"qjs версия: {checks.get('qjs_version') or quickjs_version(qjs) or '—'}",
        "",
        "## Настройки (без cookies)",
        _settings_block(settings),
        "",
        "## Самопроверка",
        f"Результат: {'OK' if selftest.get('ok') else 'ЕСТЬ ОШИБКИ'}",
    ]
    lines += [f"Ошибка: {item}" for item in errors]
    lines += [f"Предупреждение: {item}" for item in warnings]
    if not errors and not warnings:
        lines.append("Ошибок и предупреждений нет.")
    lines += [
        "",
        "Подробно (selftest.json):",
        json.dumps(selftest, ensure_ascii=False, indent=2),
        "",
        f"## Последние {LOG_TAIL_LINES} строк лога",
        f"Файл: {log_path()}",
        _tail(log_path()),
        "",
        "## Примечание",
        "В отчёте есть ссылки, пути и имена файлов из лога. Cookies и пароли не включаются.",
        "Перед отправкой проверьте текст на личные данные.",
        "",
    ]
    return "\n".join(lines)


def report_path(now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return reports_dir() / f"report-{stamp}.txt"


def write_report(
    settings: Settings | None = None,
    selftest: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> Path:
    """Создаёт файл отчёта и возвращает его путь."""
    target = report_path(now)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():  # две загрузки в одну секунду
        target = target.with_name(f"{target.stem}-{datetime.now().microsecond}.txt")
    target.write_text(build_report(settings, selftest, now=now), encoding="utf-8")
    log.info("Отчёт создан: %s", target)
    return target
