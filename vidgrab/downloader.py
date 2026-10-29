"""Загрузчик на yt-dlp: рабочие потоки QThread, выбор качества, ошибки."""

from __future__ import annotations

import logging
import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import URLError

import yt_dlp
from PySide6.QtCore import QThread, Signal

from vidgrab import QUALITY_CHOICES, strings
from vidgrab.utils import format_eta, human_speed, truncate

log = logging.getLogger(__name__)

OUTTMPL = "%(title).150B [%(id)s].%(ext)s"
PART_SUFFIXES = (".part", ".ytdl")


@dataclass(frozen=True)
class YdlConfig:
    """Необязательные параметры yt-dlp: JS-рантайм и авторизация."""

    js_runtime: Path | None = None
    cookies_from_browser: str = ""
    cookies_file: str = ""
    youtube_client: str = ""

    def is_empty(self) -> bool:
        return not (
            self.js_runtime
            or self.cookies_from_browser
            or self.cookies_file
            or self.youtube_client
        )


# Ключевые слова в сообщениях yt-dlp, по которым выбираем понятный текст.
# Порядок проверок важен: bot-check и cookies — до общих сетевых/недоступных.
_BOT_MARKERS = (
    "sign in to confirm you're not a bot",
    "sign in to confirm you are not a bot",
    "not a bot",
    "confirm you're not a bot",
    "confirm you are not a bot",
    "botcheck",
    "bot check",
)
_COOKIE_MARKERS = (
    "cookie database",
    "cookiesfrombrowser",
    "cookies from browser",
    "failed to decrypt",
    "could not copy chrome cookie",
    "unable to open cookie",
    "cookie file",
    "cookies.txt",
)
_DRM_MARKERS = (
    "widevine",
    "playready",
    "drm protected",
    "drm-protected",
    "protected by drm",
    "this video is drm",
)
_FORMAT_MARKERS = (
    "requested format is not available",
    "no video formats found",
    "requested format not available",
    "no formats found",
)
_PERMISSION_MARKERS = (
    "permission denied",
    "access is denied",
    "errno 13",
    "no space left on device",
    "not writable",
    "read-only file system",
)
_FFMPEG_MARKERS = (
    "ffmpeg is not installed",
    "ffprobe is not installed",
    "ffmpeg not found",
    "ffprobe not found",
    "ffmpeg exited with code",
    "postprocessing: ffmpeg",
    "you have requested merging of multiple formats",
)
_UNAVAILABLE_MARKERS = (
    "private video",
    "video is private",
    "video unavailable",
    "this video is unavailable",
    "has been removed",
    "removed by the uploader",
    "members-only",
    "join this channel",
    "not available in your country",
    "account has been terminated",
    "age-restricted",
    "confirm your age",
    "http error 404",
    "http error 410",
)
_NETWORK_MARKERS = (
    "urlopen error",
    "timed out",
    "timeout",
    "getaddrinfo",
    "name or service not known",
    "temporary failure in name resolution",
    "network is unreachable",
    "connection refused",
    "connection reset",
    "connection aborted",
    "failed to resolve",
    "certificate verify failed",
    "ssl:",
    "unable to download webpage",
)


class DownloadCancelled(Exception):
    """Пользователь отменил загрузку (поднимается из progress_hook)."""


def _format_height(fmt: dict[str, Any]) -> int | None:
    """Высота потока: поле height или строка resolution вида "1280x720"."""
    height = fmt.get("height")
    if height:
        try:
            return int(height)
        except (TypeError, ValueError):
            return None
    resolution = fmt.get("resolution")
    if isinstance(resolution, str):
        match = re.search(r"x(\d+)$", resolution.strip())
        if match:
            return int(match.group(1))
    return None


def _video_heights(info: dict[str, Any]) -> set[int]:
    heights: set[int] = set()
    for fmt in info.get("formats") or []:
        vcodec = fmt.get("vcodec")
        height = _format_height(fmt)
        if height and vcodec != "none":
            heights.add(int(height))
    if not heights and info.get("height"):
        try:
            heights.add(int(info["height"]))
        except (TypeError, ValueError):
            pass
    return heights


def list_qualities(info: dict[str, Any]) -> list[str]:
    """Доступные качества из фиксированного списка (+ always best).

    Качество Np показывается, только если у видео есть поток, реально близкий
    к этой высоте: 0.9*N <= height <= 1.35*N. Так мы не показываем «480p» для
    видео с вариантами только 360p и 720p.
    """
    heights = _video_heights(info)
    qualities = [
        f"{bucket}p"
        for bucket in (360, 480, 720, 1080)
        if any(0.9 * bucket <= height <= 1.35 * bucket for height in heights)
    ]
    qualities.append("best")
    return qualities


def build_format_selector(quality: str) -> str:
    if quality == "best" or quality not in QUALITY_CHOICES:
        return "bestvideo+bestaudio/best"
    height = int(quality[:-1])
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"


def build_ydl_opts(
    outdir: str | Path,
    quality: str,
    ffmpeg_path: str | Path | None,
    progress_hooks: Iterable[Callable[[dict[str, Any]], None]] = (),
    logger: logging.Logger | None = None,
    *,
    skip_download: bool = False,
    config: YdlConfig | None = None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "format": build_format_selector(quality),
        "paths": {"home": str(outdir)},
        "outtmpl": {"default": OUTTMPL},
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": False,
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "windowsfilenames": True,
        "progress_hooks": list(progress_hooks),
        "logger": _YdlLogger(logger or log),
    }
    if ffmpeg_path:
        opts["ffmpeg_location"] = str(ffmpeg_path)
    if skip_download:
        opts["skip_download"] = True
    if config is not None:
        if config.js_runtime:
            # Только quickjs: без него yt-dlp ищет deno и на публичных видео
            # YouTube отдаёт ссылки, падающие с HTTP 403.
            opts["js_runtimes"] = {"quickjs": {"path": str(config.js_runtime)}}
        if config.cookies_file:
            opts["cookiefile"] = str(Path(config.cookies_file).expanduser())
        elif config.cookies_from_browser:
            opts["cookiesfrombrowser"] = (config.cookies_from_browser,)
        if config.youtube_client:
            opts["extractor_args"] = {"youtube": {"player_client": [config.youtube_client]}}
    return opts


class _YdlLogger:
    """Адаптер логгера yt-dlp в стандартный logging."""

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            self._log.debug(msg)
        else:
            self._log.info(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)


def summarize_info(info: dict[str, Any]) -> dict[str, Any]:
    duration = info.get("duration")
    return {
        "id": info.get("id"),
        "title": info.get("title") or info.get("id") or "Без названия",
        "duration": duration if isinstance(duration, (int, float)) else None,
        "uploader": info.get("uploader"),
        "webpage_url": info.get("webpage_url") or info.get("original_url"),
        "qualities": list_qualities(info),
    }


def describe_error(exc: BaseException) -> tuple[str, str]:
    """Превращает исключение в (код, понятный пользователю текст).

    Коды: bot_check, cookies, drm, forbidden, format_unavailable, unavailable,
    permission, ffmpeg, network, generic, cancelled.
    """
    if isinstance(exc, DownloadCancelled):
        return "cancelled", strings.ERRORS["cancelled"]

    detail = truncate(str(exc) or exc.__class__.__name__, 300)
    low = detail.lower()

    def has(markers: Iterable[str]) -> bool:
        return any(marker in low for marker in markers)

    if isinstance(exc, PermissionError) or has(_PERMISSION_MARKERS):
        return "permission", strings.ERRORS["permission"]
    if has(_FFMPEG_MARKERS):
        return "ffmpeg", strings.ERRORS["ffmpeg"]
    if has(_BOT_MARKERS):
        return "bot_check", strings.ERRORS["bot_check"]
    if has(_COOKIE_MARKERS):
        return "cookies", strings.ERRORS["cookies"]
    if has(_DRM_MARKERS):
        return "drm", strings.ERRORS["drm"]
    if has(_FORMAT_MARKERS):
        return "format_unavailable", strings.ERRORS["format_unavailable"]
    if "http error 403" in low or "403: forbidden" in low:
        return "forbidden", strings.ERRORS["forbidden"]
    if has(_UNAVAILABLE_MARKERS):
        return "unavailable", strings.ERRORS["unavailable"]
    if isinstance(exc, (URLError, socket.timeout, TimeoutError, ConnectionError)) or has(
        _NETWORK_MARKERS
    ):
        return "network", strings.ERRORS["network"]
    return "generic", strings.ERRORS["generic"].format(detail=detail)


def progress_payload(hook_data: dict[str, Any]) -> tuple[int, str, str]:
    """Из словаря progress_hook делает (процент, скорость, ETA) для GUI."""
    downloaded = hook_data.get("downloaded_bytes") or 0
    total = hook_data.get("total_bytes") or hook_data.get("total_bytes_estimate") or 0
    if total:
        percent = max(0, min(100, int(downloaded * 100 / total)))
    else:
        percent = 0
    speed = hook_data.get("speed")
    eta = hook_data.get("eta")
    return percent, human_speed(speed), format_eta(eta)


def resolve_download_path(
    outdir: Path, ydl: Any, info: dict[str, Any], started_at: float = 0.0
) -> Path:
    """Находит итоговый файл после загрузки (с учётом склейки в mp4)."""
    candidates: list[Path] = []
    for item in info.get("requested_downloads") or []:
        if isinstance(item, dict) and item.get("filepath"):
            candidates.append(Path(item["filepath"]))
    if info.get("filepath"):
        candidates.append(Path(info["filepath"]))
    prepare = getattr(ydl, "prepare_filename", None)
    if callable(prepare):
        try:
            candidates.append(Path(prepare(info)))
        except Exception:  # noqa: BLE001
            log.debug("prepare_filename не сработал", exc_info=True)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    for candidate in candidates:
        for ext in (".mp4", ".mkv", ".webm", ".m4a", ".mp3"):
            alt = candidate.with_suffix(ext)
            if alt.is_file():
                return alt

    recent = [
        p
        for p in outdir.iterdir()
        if p.is_file()
        and not p.name.endswith(PART_SUFFIXES)
        and p.stat().st_mtime >= started_at - 5
    ]
    if recent:
        return max(recent, key=lambda p: p.stat().st_mtime)
    raise RuntimeError("файл не найден после загрузки")


def remove_partial_files(outdir: Path, started_at: float) -> None:
    """Удаляет *.part/*.ytdl, созданные текущей загрузкой."""
    try:
        for item in outdir.iterdir():
            if not item.is_file() or not item.name.endswith(PART_SUFFIXES):
                continue
            try:
                if item.stat().st_mtime < started_at - 5:
                    continue
                item.unlink()
                log.info("Удалён недокачанный файл: %s", item.name)
            except OSError:
                log.warning("Не удалось удалить %s", item, exc_info=True)
    except OSError:
        log.warning("Не удалось осмотреть папку %s", outdir, exc_info=True)


class MetadataWorker(QThread):
    """Проверка ссылки: метаданные и доступные качества без скачивания."""

    ready = Signal(dict)
    failed = Signal(str, str)

    def __init__(
        self,
        url: str,
        ffmpeg_path: str | Path | None = None,
        ydl_factory: Callable[[dict[str, Any]], Any] | None = None,
        parent: Any = None,
        *,
        config: YdlConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._ffmpeg_path = ffmpeg_path
        self._ydl_factory = ydl_factory or yt_dlp.YoutubeDL
        self._config = config or YdlConfig()
        log.debug("MetadataWorker создан для %s", url)

    def run(self) -> None:  # noqa: D401 - QThread API
        log.info("Проверка ссылки: %s", self._url)
        ydl = None
        try:
            opts = build_ydl_opts(
                Path.cwd(),
                "best",
                self._ffmpeg_path,
                [],
                skip_download=True,
                config=self._config,
            )
            ydl = self._ydl_factory(opts)
            info = ydl.extract_info(self._url, download=False)
            if not info:
                raise RuntimeError("пустой ответ от загрузчика")
            summary = summarize_info(info)
            log.info(
                "Метаданные: id=%s, качеств=%s (%s)",
                summary.get("id"),
                len(summary.get("qualities") or []),
                ", ".join(summary.get("qualities") or []),
            )
            self.ready.emit(summary)
        except Exception as exc:  # noqa: BLE001 - все ошибки показываем пользователю
            code, message = describe_error(exc)
            log.exception("Ошибка проверки ссылки: %s", exc)
            self.failed.emit(code, message)
        finally:
            close = getattr(ydl, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    log.debug("Не удалось закрыть YoutubeDL", exc_info=True)


class DownloadWorker(QThread):
    """Скачивание видео в отдельном потоке с прогрессом и отменой."""

    progress = Signal(int, str, str)  # процент, скорость, ETA
    stage_changed = Signal(str)
    completed = Signal(str)  # итоговый путь
    failed = Signal(str, str)  # код, текст
    cancelled = Signal()

    def __init__(
        self,
        url: str,
        quality: str,
        outdir: str | Path,
        ffmpeg_path: str | Path | None = None,
        ydl_factory: Callable[[dict[str, Any]], Any] | None = None,
        parent: Any = None,
        *,
        config: YdlConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._quality = quality
        self._outdir = Path(outdir)
        self._ffmpeg_path = ffmpeg_path
        self._ydl_factory = ydl_factory or yt_dlp.YoutubeDL
        self._config = config or YdlConfig()
        self._cancel_requested = False
        self._started_at = 0.0
        self._last_percent_logged = -10

    def request_cancel(self) -> None:
        self._cancel_requested = True
        log.info("Запрошена отмена загрузки")

    def _hook(self, hook_data: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise DownloadCancelled("cancelled by user")
        status = hook_data.get("status")
        if status == "downloading":
            percent, speed, eta = progress_payload(hook_data)
            if percent >= self._last_percent_logged + 10:
                self._last_percent_logged = percent - (percent % 10)
                log.info("Прогресс: %d%%, скорость %s, осталось %s", percent, speed, eta)
            self.progress.emit(percent, speed, eta)
        elif status == "finished":
            log.info("Поток загружен, начинается обработка (ffmpeg)")
            self.stage_changed.emit(strings.STATUS_PROCESSING)
            self.progress.emit(100, "—", "—")
        elif status == "error":
            raise RuntimeError("ошибка загрузки одного из потоков")

    def run(self) -> None:  # noqa: D401 - QThread API
        self._started_at = time.time()
        self._outdir.mkdir(parents=True, exist_ok=True)
        log.info(
            "Старт загрузки: url=%s, качество=%s, папка=%s, ffmpeg=%s, qjs=%s, cookies=%s",
            self._url,
            self._quality,
            self._outdir,
            self._ffmpeg_path or "не найден",
            self._config.js_runtime or "не найден",
            self._config.cookies_file or self._config.cookies_from_browser or "нет",
        )
        ydl = None
        try:
            opts = build_ydl_opts(
                self._outdir,
                self._quality,
                self._ffmpeg_path,
                [self._hook],
                config=self._config,
            )
            ydl = self._ydl_factory(opts)
            info = ydl.extract_info(self._url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("загрузчик не вернул данные о файле")
            path = self._resolve_path(ydl, info)
            log.info("Загрузка завершена: %s", path)
            self.completed.emit(str(path))
        except DownloadCancelled:
            log.info("Загрузка отменена пользователем")
            self._cleanup_parts()
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            if self._cancel_requested:
                log.info("Загрузка прервана после запроса отмены: %s", exc)
                self._cleanup_parts()
                self.cancelled.emit()
                return
            code, message = describe_error(exc)
            log.exception("Ошибка загрузки: %s", exc)
            self._cleanup_parts()
            self.failed.emit(code, message)
        finally:
            close = getattr(ydl, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    log.debug("Не удалось закрыть YoutubeDL", exc_info=True)

    def _resolve_path(self, ydl: Any, info: dict[str, Any]) -> Path:
        return resolve_download_path(self._outdir, ydl, info, self._started_at)

    def _cleanup_parts(self) -> None:
        remove_partial_files(self._outdir, self._started_at)
