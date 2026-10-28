"""Настройки приложения: JSON в %APPDATA%\\VidGrab\\settings.json."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vidgrab import QUALITY_CHOICES
from vidgrab.utils import default_download_dir, settings_path

log = logging.getLogger(__name__)

DEFAULT_QUALITY = "best"
DEFAULT_LANGUAGE = "ru"


@dataclass
class Settings:
    last_folder: str = field(default_factory=lambda: str(default_download_dir()))
    last_quality: str = DEFAULT_QUALITY
    language: str = DEFAULT_LANGUAGE
    window_geometry: str = ""


def _coerce(data: dict[str, Any]) -> Settings:
    defaults = Settings()
    folder = data.get("last_folder")
    if not isinstance(folder, str) or not folder.strip():
        folder = defaults.last_folder
    quality = data.get("last_quality")
    if quality not in QUALITY_CHOICES:
        quality = DEFAULT_QUALITY
    language = data.get("language")
    if not isinstance(language, str) or not language:
        language = DEFAULT_LANGUAGE
    geometry = data.get("window_geometry")
    if not isinstance(geometry, str):
        geometry = ""
    return Settings(
        last_folder=folder,
        last_quality=quality,
        language=language,
        window_geometry=geometry,
    )


def load_settings(path: str | Path | None = None) -> Settings:
    target = Path(path) if path is not None else settings_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings()
    except OSError as exc:
        log.warning("Не удалось прочитать настройки %s: %s", target, exc)
        return Settings()

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Файл настроек повреждён (%s), использую значения по умолчанию", exc)
        return Settings()

    if not isinstance(data, dict):
        log.warning("Файл настроек содержит не объект, использую значения по умолчанию")
        return Settings()
    return _coerce(data)


def save_settings(settings: Settings, path: str | Path | None = None) -> bool:
    target = Path(path) if path is not None else settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(settings), ensure_ascii=False, indent=2)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)
        return True
    except OSError as exc:
        log.error("Не удалось сохранить настройки %s: %s", target, exc)
        return False
