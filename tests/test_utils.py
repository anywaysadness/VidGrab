from pathlib import Path
import sys

import pytest

from vidgrab.utils import (
    ensure_writable_dir,
    find_ffmpeg,
    format_duration,
    format_eta,
    format_quality_label,
    human_size,
    human_speed,
    is_valid_url,
    normalize_url,
    truncate,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://youtube.com/watch?v=1", True),
        ("http://example.com/video", True),
        ("https://localhost:8080/video.mp4", True),
        ("http://127.0.0.1:8000/sample.mp4", True),
        ("youtube.com/watch?v=1", True),  # схема добавляется автоматически
        ("", False),
        ("   ", False),
        ("qwerty", False),
        ("ftp://example.com/video", False),
        ("https://", False),
        ("https://exa mple.com", False),
        ("https://example", False),
    ],
)
def test_is_valid_url(raw, expected):
    assert is_valid_url(raw) is expected


def test_normalize_url():
    assert normalize_url("  youtube.com/watch?v=1  ") == "https://youtube.com/watch?v=1"
    assert normalize_url("https://a.b/c") == "https://a.b/c"
    assert normalize_url(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 Б"),
        (512, "512 Б"),
        (1024, "1.0 КБ"),
        (1536, "1.5 КБ"),
        (1024 * 1024, "1.0 МБ"),
    ],
)
def test_human_size(value, expected):
    assert human_size(value) == expected


def test_human_speed_and_eta():
    assert human_speed(None) == "—"
    assert human_speed(1024) == "1.0 КБ/с"
    assert format_eta(None) == "—"
    assert format_eta(5) == "00:05"
    assert format_eta(65) == "01:05"
    assert format_eta(3725) == "1:02:05"


def test_format_duration():
    assert format_duration(None) == "—"
    assert format_duration(0) == "—"
    assert format_duration(125) == "02:05"


def test_truncate():
    assert truncate("a b   c") == "a b c"
    assert len(truncate("x" * 500, 10)) == 10
    assert truncate("x" * 500, 10).endswith("…")


def test_format_quality_label():
    assert format_quality_label("best").startswith("best")
    assert format_quality_label("720p") == "720p"


def test_ensure_writable_dir(tmp_path):
    target = tmp_path / "a" / "b"
    ok, reason = ensure_writable_dir(target)
    assert ok and target.is_dir() and reason == ""


def test_ensure_writable_dir_file_instead_of_folder(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")
    ok, _reason = ensure_writable_dir(file_path)
    assert not ok


@pytest.mark.skipif(not hasattr(Path, "chmod"), reason="chmod недоступен")
def test_ensure_writable_dir_readonly(tmp_path):
    target = tmp_path / "readonly"
    target.mkdir()
    target.chmod(0o555)
    try:
        ok, _reason = ensure_writable_dir(target)
        assert not ok
    finally:
        target.chmod(0o755)


def test_find_ffmpeg_ignores_windows_binary_on_posix(monkeypatch):
    if sys.platform == "win32":
        pytest.skip("поведение только для POSIX")
    monkeypatch.delenv("VIDGRAB_FFMPEG", raising=False)
    found = find_ffmpeg()
    assert found is None or found.suffix.lower() != ".exe"


def test_find_ffmpeg_env_override(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("VIDGRAB_FFMPEG", str(fake))
    assert find_ffmpeg() == fake
