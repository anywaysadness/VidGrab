"""Точка входа VidGrab: логирование, GUI, CLI-прототип и самопроверка."""

from __future__ import annotations

import argparse
import faulthandler
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TextIO

import yt_dlp

from vidgrab import APP_NAME, APP_ORG, APP_VERSION, QUALITY_CHOICES, strings
from vidgrab.downloader import (
    build_ydl_opts,
    describe_error,
    list_qualities,
    progress_payload,
    remove_partial_files,
    resolve_download_path,
    summarize_info,
)
from vidgrab.settings import Settings, load_settings, save_settings
from vidgrab.utils import (
    app_data_dir,
    crash_log_path,
    default_download_dir,
    ensure_writable_dir,
    find_ffmpeg,
    format_duration,
    is_valid_url,
    log_path,
    normalize_url,
)

log = logging.getLogger("vidgrab")

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INVALID_URL = 2
EXIT_METADATA = 3
EXIT_DOWNLOAD = 4
EXIT_FFMPEG = 5
EXIT_PERMISSION = 6
EXIT_CANCELLED = 130

_CRASH_FILE: TextIO | None = None


# --------------------------------------------------------------------------- #
# Логирование
# --------------------------------------------------------------------------- #

def setup_logging() -> None:
    """Файловый лог в %APPDATA%\\VidGrab\\vidgrab.log + faulthandler в crash-лог."""
    root = logging.getLogger()
    if any(getattr(handler, "_vidgrab_handler", False) for handler in root.handlers):
        return

    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    try:
        target = log_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target, maxBytes=1_048_576, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler._vidgrab_handler = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)
    except OSError as exc:  # лог не должен мешать запуску приложения
        print(f"VidGrab: не удалось открыть файл лога: {exc}", file=sys.stderr)

    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler._vidgrab_handler = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)

    global _CRASH_FILE
    try:
        crash_path = crash_log_path()
        crash_path.parent.mkdir(parents=True, exist_ok=True)
        _CRASH_FILE = open(crash_path, "a", encoding="utf-8")
        faulthandler.enable(file=_CRASH_FILE, all_threads=True)
    except OSError:
        log.debug("faulthandler недоступен", exc_info=True)


# --------------------------------------------------------------------------- #
# Самопроверка (используется для проверки собранного exe)
# --------------------------------------------------------------------------- #

def run_selftest() -> int:
    checks: dict[str, Any] = {}
    errors: list[str] = []
    result: dict[str, Any] = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "ok": False,
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "platform": platform.platform(),
        "checks": checks,
        "errors": errors,
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

    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        checks["pyside6"] = pyside_version
        checks["qt_platform"] = app.platformName()
    except Exception as exc:  # noqa: BLE001
        checks["pyside6"] = None
        errors.append(f"Qt: {exc}")

    ffmpeg_path = find_ffmpeg()
    checks["ffmpeg_path"] = str(ffmpeg_path) if ffmpeg_path else None
    if not ffmpeg_path:
        errors.append("ffmpeg не найден")
    else:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            proc = subprocess.run(
                [str(ffmpeg_path), "-version"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=creationflags,
            )
            first_line = ""
            output = (proc.stdout or "") + (proc.stderr or "")
            if output.strip():
                first_line = output.strip().splitlines()[0]
            checks["ffmpeg_version"] = first_line
            if proc.returncode != 0:
                errors.append(f"ffmpeg вернул код {proc.returncode}")
        except Exception as exc:  # noqa: BLE001
            checks["ffmpeg_version"] = None
            errors.append(f"ffmpeg не запускается: {exc}")

    result["ok"] = not errors
    report_path = data_dir / "selftest.json"
    try:
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        log.warning("Не удалось записать отчёт самопроверки", exc_info=True)

    log.info("Самопроверка: %s (ошибок: %d)", "OK" if result["ok"] else "FAIL", len(errors))
    try:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception:  # noqa: BLE001 - в windowed-сборке stdout может отсутствовать
        pass
    return EXIT_OK if result["ok"] else EXIT_FAILURE


# --------------------------------------------------------------------------- #
# CLI-прототип
# --------------------------------------------------------------------------- #

def _extract_metadata(url: str, ffmpeg_path: Path | None) -> dict[str, Any]:
    opts = build_ydl_opts(Path.cwd(), "best", ffmpeg_path, [], skip_download=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        raise RuntimeError("загрузчик не вернул данные о видео")
    return summarize_info(info)


def _download_sync(
    url: str,
    quality: str,
    outdir: Path,
    ffmpeg_path: Path | None,
    on_progress: Callable[[int, str, str], None] | None = None,
) -> Path:
    started_at = time.time()

    def hook(hook_data: dict[str, Any]) -> None:
        status = hook_data.get("status")
        if status == "downloading" and on_progress is not None:
            percent, speed, eta = progress_payload(hook_data)
            on_progress(percent, speed, eta)
        elif status == "finished" and on_progress is not None:
            on_progress(100, "—", "—")

    opts = build_ydl_opts(outdir, quality, ffmpeg_path, [hook])
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("загрузчик не вернул данные о файле")
            return resolve_download_path(outdir, ydl, info, started_at)
    except KeyboardInterrupt:
        remove_partial_files(outdir, started_at)
        raise


def _json_out(payload: dict[str, Any]) -> None:
    # ensure_ascii=True: JSON остаётся валидным при любой кодировке консоли
    # (в именах файлов бывают символы вроде «｜», которых нет в cp1251).
    print(json.dumps(payload, ensure_ascii=True, indent=2), flush=True)


def _error_exit_code(code: str, *, stage: str) -> int:
    if code == "cancelled":
        return EXIT_CANCELLED
    if code == "invalid_url":
        return EXIT_INVALID_URL
    if code == "ffmpeg":
        return EXIT_FFMPEG
    if code == "permission":
        return EXIT_PERMISSION
    return EXIT_METADATA if stage == "metadata" else EXIT_DOWNLOAD


def _cmd_cli(args: argparse.Namespace) -> int:
    url = normalize_url(args.url)
    machine = bool(args.json)

    if not is_valid_url(url):
        message = strings.ERRORS["invalid_url"]
        if machine:
            _json_out({"ok": False, "code": "invalid_url", "error": message})
        else:
            print(f"Ошибка: {message}", file=sys.stderr)
        return EXIT_INVALID_URL

    outdir = Path(args.out).expanduser() if args.out else default_download_dir()
    writable, reason = ensure_writable_dir(outdir)
    if not writable:
        message = f"{strings.ERRORS['permission']} ({reason})"
        if machine:
            _json_out({"ok": False, "code": "permission", "error": message})
        else:
            print(f"Ошибка: {message}", file=sys.stderr)
        return EXIT_PERMISSION

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        if machine:
            _json_out({"ok": False, "code": "ffmpeg", "error": strings.ERRORS["ffmpeg"]})
        else:
            print(f"Ошибка: {strings.ERRORS['ffmpeg']}", file=sys.stderr)
        return EXIT_FFMPEG

    try:
        summary = _extract_metadata(url, ffmpeg_path)
    except Exception as exc:  # noqa: BLE001
        code, message = describe_error(exc)
        log.exception("CLI: не удалось получить метаданные")
        if machine:
            _json_out({"ok": False, "code": code, "error": message})
        else:
            print(f"Ошибка: {message}", file=sys.stderr)
        return _error_exit_code(code, stage="metadata")

    qualities = summary.get("qualities") or list_qualities({})
    if not machine:
        print(f"Название: {summary.get('title')}")
        print(f"Длительность: {format_duration(summary.get('duration'))}")
        print(f"Доступные качества: {', '.join(qualities)}")
        print(f"Папка сохранения: {outdir}")
        print(f"FFmpeg: {ffmpeg_path}")

    if args.quality not in qualities:
        message = (
            f"Качество {args.quality} недоступно для этого видео. "
            f"Доступно: {', '.join(qualities)}."
        )
        if machine:
            _json_out(
                {
                    "ok": False,
                    "code": "unavailable",
                    "error": message,
                    "qualities": qualities,
                    "title": summary.get("title"),
                    "duration": summary.get("duration"),
                }
            )
        else:
            print(f"Ошибка: {message}", file=sys.stderr)
        return EXIT_DOWNLOAD

    def on_progress(percent: int, speed: str, eta: str) -> None:
        if machine:
            return
        sys.stderr.write(f"\r{percent:3d}% | скорость {speed} | осталось {eta}   ")
        sys.stderr.flush()

    try:
        path = _download_sync(url, args.quality, outdir, ffmpeg_path, on_progress)
    except KeyboardInterrupt:
        if not machine:
            sys.stderr.write("\nЗагрузка отменена пользователем.\n")
        return EXIT_CANCELLED
    except Exception as exc:  # noqa: BLE001
        code, message = describe_error(exc)
        log.exception("CLI: ошибка загрузки")
        if machine:
            _json_out({"ok": False, "code": code, "error": message})
        else:
            sys.stderr.write("\n")
            print(f"Ошибка: {message}", file=sys.stderr)
        return _error_exit_code(code, stage="download")

    if not machine:
        sys.stderr.write("\n")
        print(f"Готово: {path}")
    if machine:
        _json_out(
            {
                "ok": True,
                "title": summary.get("title"),
                "duration": summary.get("duration"),
                "qualities": qualities,
                "quality": args.quality,
                "path": str(path),
            }
        )
    return EXIT_OK


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #

def _install_excepthook() -> None:
    def hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        log.critical("Необработанное исключение", exc_info=(exc_type, exc, tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    strings.DIALOG_ERROR_TITLE,
                    f"Непредвиденная ошибка:\n{exc}",
                )
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = hook


def _run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from vidgrab.ui import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    _install_excepthook()

    settings = load_settings()
    window = MainWindow(settings)
    window.show()
    log.info("GUI запущен")
    return app.exec()


# --------------------------------------------------------------------------- #
# Разбор аргументов
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="VidGrab",
        description="Скачивание видео по ссылке (PySide6 + yt-dlp + ffmpeg).",
    )
    parser.add_argument("url", nargs="?", help="ссылка на видео (для --cli)")
    parser.add_argument("--cli", action="store_true", help="скачать видео из командной строки")
    parser.add_argument(
        "--quality",
        default="best",
        choices=list(QUALITY_CHOICES),
        help="качество загрузки (по умолчанию best)",
    )
    parser.add_argument(
        "-o", "--out", default=None, help="папка сохранения (по умолчанию Downloads/VidGrab)"
    )
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод (для --cli)")
    parser.add_argument("--selftest", action="store_true", help="проверить установку и выйти")
    parser.add_argument("--version", action="store_true", help="показать версию и выйти")
    return parser


def _configure_stdio() -> None:
    """Не падать при печати символов, которых нет в кодировке консоли."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)

    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return EXIT_OK

    setup_logging()

    if args.selftest:
        return run_selftest()

    log.info("=" * 60)
    log.info(
        "%s %s: старт (frozen=%s, python=%s, argv=%s)",
        APP_NAME,
        APP_VERSION,
        bool(getattr(sys, "frozen", False)),
        sys.version.split()[0],
        sys.argv[1:],
    )

    if args.cli:
        if not args.url:
            message = "Для --cli нужна ссылка: VidGrab.exe --cli URL"
            if args.json:
                _json_out({"ok": False, "code": "invalid_url", "error": message})
            else:
                print(message, file=sys.stderr)
            return EXIT_INVALID_URL
        return _cmd_cli(args)

    try:
        return _run_gui()
    except Exception as exc:  # noqa: BLE001
        log.exception("Не удалось запустить GUI")
        print(f"VidGrab: не удалось запустить интерфейс: {exc}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
