import json

from vidgrab.settings import Settings, load_settings, save_settings
from vidgrab.utils import settings_path


def test_defaults_when_missing(appdata):
    settings = load_settings()
    assert settings.last_quality == "best"
    assert settings.language == "ru"
    assert settings.last_folder
    assert not settings_path().exists()


def test_roundtrip(appdata, tmp_path):
    original = Settings(last_folder=str(tmp_path), last_quality="720p", window_geometry="abc")
    assert save_settings(original)
    assert load_settings() == original
    assert json.loads(settings_path().read_text(encoding="utf-8"))["last_quality"] == "720p"


def test_corrupt_json_falls_back(appdata):
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text("{not json", encoding="utf-8")
    settings = load_settings()
    assert settings.last_quality == "best"
    assert settings.language == "ru"


def test_invalid_values_are_sanitized(appdata):
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps({"last_folder": "", "last_quality": "4k", "language": 5, "window_geometry": 1}),
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.last_quality == "best"
    assert settings.language == "ru"
    assert settings.last_folder
    assert settings.window_geometry == ""


def test_explicit_path(tmp_path):
    target = tmp_path / "custom" / "settings.json"
    assert save_settings(Settings(last_folder="/tmp/x", last_quality="480p"), target)
    loaded = load_settings(target)
    assert loaded.last_folder == "/tmp/x"
    assert loaded.last_quality == "480p"


def test_cookies_settings_roundtrip(appdata, tmp_path):
    original = Settings(
        last_folder=str(tmp_path),
        cookies_from_browser="chrome",
        cookies_file="",
        youtube_client="web",
    )
    assert save_settings(original)
    loaded = load_settings()
    assert loaded.cookies_from_browser == "chrome"
    assert loaded.cookies_file == ""
    assert loaded.youtube_client == "web"


def test_old_settings_are_migrated(appdata):
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps({"last_folder": "/tmp/v", "last_quality": "720p"}),
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.last_folder == "/tmp/v"
    assert settings.cookies_from_browser == ""
    assert settings.cookies_file == ""
    assert settings.youtube_client == ""


def test_invalid_cookies_values_are_sanitized(appdata):
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps(
            {
                "cookies_from_browser": "opera",
                "cookies_file": 5,
                "youtube_client": "android_vr",
            }
        ),
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.cookies_from_browser == ""
    assert settings.cookies_file == ""
    assert settings.youtube_client == ""
