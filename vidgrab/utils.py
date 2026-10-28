"""Вспомогательные функции: пути, URL, форматирование, ffmpeg, проводник."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from vidgrab import APP_NAME

_DOMAIN_RE = re.compile(r"^[\w.-]+\.[a-zA-Z]{2,}(?:[/:?#]|$)")


def app_data_dir() -> Path:
    """Каталог данных приложения: %APPDATA%\\VidGrab (или override для тестов)."""
    override = os.environ.get("VIDGRAB_APPDATA")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    # Linux/macOS — только для разработки и тестов.
    return Path.home() / ".config" / APP_NAME


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def log_path() -> Path:
    return app_data_dir() / "vidgrab.log"


def crash_log_path() -> Path:
    return app_data_dir() / "vidgrab-crash.log"


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / APP_NAME


def normalize_url(text: str | None) -> str:
    """Убирает пробелы и добавляет https://, если схема не указана."""
    value = (text or "").strip()
    if not value:
        return ""
    if "://" not in value and _DOMAIN_RE.match(value):
        value = "https://" + value
    return value


def is_valid_url(text: str | None) -> bool:
    value = normalize_url(text)
    if not value or any(ch.isspace() for ch in value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https"):
        return False
    if not parts.netloc:
        return False
    try:
        host = parts.hostname
    except ValueError:
        return False
    if not host:
        return False
    if host in ("localhost", "::1") or host.startswith("127."):
        return True
    return "." in host


def human_size(num: float | int | None) -> str:
    if not num:
        return "0 Б"
    value = float(num)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} ТБ"


def human_speed(bytes_per_second: float | int | None) -> str:
    if not bytes_per_second:
        return "—"
    return f"{human_size(bytes_per_second)}/с"


def format_eta(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if total < 0:
        return "—"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: float | int | None) -> str:
    if not seconds:
        return "—"
    return format_eta(seconds)


def truncate(text: str, limit: int = 300) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def find_ffmpeg() -> Path | None:
    """Ищет ffmpeg: env override → рядом с exe/_MEIPASS → assets пакета → PATH."""
    candidates: list[Path] = []
    env_value = os.environ.get("VIDGRAB_FFMPEG")
    if env_value:
        candidates.append(Path(env_value).expanduser())

    windows = os.name == "nt"
    binary_name = "ffmpeg.exe" if windows else "ffmpeg"

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / binary_name)
        candidates.append(exe_dir / "vidgrab" / "assets" / binary_name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / binary_name)
            candidates.append(Path(meipass) / "vidgrab" / "assets" / binary_name)

    assets_dir = Path(__file__).resolve().parent / "assets"
    candidates.append(assets_dir / binary_name)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def ensure_writable_dir(path: str | Path) -> tuple[bool, str]:
    """Создаёт папку (если нужно) и проверяет реальную запись в неё."""
    target = Path(path).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, str(exc)
    if not target.is_dir():
        return False, "путь существует, но это не папка"
    try:
        fd, probe = tempfile.mkstemp(prefix=".vidgrab-probe-", dir=str(target))
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        return False, str(exc)
    return True, ""


def open_in_explorer(path: str | Path) -> None:
    """Открывает проводник с выделением файла (Windows) или папку."""
    target = Path(path).expanduser().resolve()
    folder = target.parent if target.is_file() else target
    if sys.platform == "win32":
        if target.is_file():
            subprocess.Popen(["explorer", f"/select,{target}"])
        else:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(folder)])


def format_quality_label(quality: str) -> str:
    return quality
