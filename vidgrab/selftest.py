"""Самопроверка установки VidGrab: версии, пути, доступность ресурсов."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp

from vidgrab import APP_NAME, APP_VERSION
from vidgrab.settings import Settings, load_settings, save_settings
from vidgrab.utils import (
    app_data_dir,
    ensure_writable_dir,
    find_ffmpeg,
    find_quickjs,
    log_path,
    quickjs_version,
)

log = logging.getLogger(__name__)


def _check_ffmpeg(checks: dict[str, Any], errors: list[str]) -> None:
    ffmpeg_path = find_ffmpeg()
    checks["ffmpeg_path"] = str(ffmpeg_path) if ffmpeg_path else None
    if not ffmpeg_path:
        errors.append("ffmpeg не найден")
        return
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=creationflags,
        )
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        checks["ffmpeg_version"] = output.splitlines()[0] if output else ""
        if proc.returncode != 0:
            errors.append(f"ffmpeg вернул код {proc.returncode}")
    except Exception as exc:  # noqa: BLE001
        checks["ffmpeg_version"] = None
        errors.append(f"ffmpeg не запускается: {exc}")


def _check_quickjs(checks: dict[str, Any], warnings: list[str]) -> None:
    qjs_path = find_quickjs()
    checks["qjs_path"] = str(qjs_path) if qjs_path else None
    checks["qjs_version"] = quickjs_version(qjs_path) if qjs_path else None
    if not qjs_path:
        # Без qjs приложение работает, но YouTube может отдавать битые ссылки (403).
        warnings.append("qjs не найден: YouTube может отклонять загрузку (HTTP 403)")


def collect_selftest(*, with_qt: bool = True) -> dict[str, Any]:
    """Собирает сведения о сборке. Не меняет настройки пользователя."""
    checks: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []
    result: dict[str, Any] = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "ok": False,
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }

    data_dir = app_data_dir()
    writable, reason = ensure_writable_dir(data_dir)
    checks["appdata"] = {"path": str(data_dir), "writable": writable}
    if not writable:
        errors.append(f"каталог данных недоступен для записи: {reason}")

    try:
        with tempfile.TemporaryDirectory(
            prefix="vidgrab-selftest-", dir=str(data_dir) if writable else None
        ) as tmp:
            probe_path = Path(tmp) / "settings.json"
            probe = Settings(last_folder=tmp, last_quality="720p")
            saved = save_settings(probe, probe_path)
            loaded = load_settings(probe_path)
            checks["settings_roundtrip"] = bool(
                saved and loaded.last_folder == tmp and loaded.last_quality == "720p"
            )
            if not checks["settings_roundtrip"]:
                errors.append("настройки не сохраняются/не читаются")
    except Exception as exc:  # noqa: BLE001
        checks["settings_roundtrip"] = False
        errors.append(f"settings: {exc}")

    checks["log_file"] = str(log_path())
    try:
        log.info("selftest: проверка логирования")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"логирование: {exc}")

    checks["yt_dlp"] = getattr(yt_dlp.version, "__version__", "unknown")
    try:
        import certifi as _certifi

        checks["certifi"] = _certifi.where()
        checks["certifi_exists"] = Path(_certifi.where()).is_file()
    except Exception:  # noqa: BLE001
        checks["certifi"] = None
        checks["certifi_exists"] = False
    try:
        import importlib

        importlib.import_module("yt_dlp.extractor")  # ленивые экстракторы должны быть в сборке
        checks["yt_dlp_extractors"] = True
    except Exception as exc:  # noqa: BLE001
        checks["yt_dlp_extractors"] = False
        errors.append(f"yt-dlp extractors: {exc}")

    if with_qt:
        try:
            from PySide6 import __version__ as pyside_version
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
            checks["pyside6"] = pyside_version
            checks["qt_platform"] = app.platformName()
        except Exception as exc:  # noqa: BLE001
            checks["pyside6"] = None
            errors.append(f"Qt: {exc}")

    _check_ffmpeg(checks, errors)
    _check_quickjs(checks, warnings)

    result["ok"] = not errors
    return result


def write_selftest_json(result: dict[str, Any]) -> Path:
    path = app_data_dir() / "selftest.json"
    try:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        log.warning("Не удалось записать отчёт самопроверки", exc_info=True)
    return path
