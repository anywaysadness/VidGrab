import pytest

from vidgrab.downloader import (
    build_format_selector,
    build_ydl_opts,
    list_qualities,
    progress_payload,
)


def _video(height, vcodec="avc1", acodec=None):
    return {"height": height, "vcodec": vcodec, "acodec": acodec}


@pytest.mark.parametrize(
    ("formats", "expected"),
    [
        ([_video(1080), _video(720), _video(480), _video(360)], ["360p", "480p", "720p", "1080p", "best"]),
        ([_video(2160)], ["best"]),
        ([_video(360), _video(720)], ["360p", "720p", "best"]),
        (
            [
                {"resolution": "640x360", "vcodec": None, "height": None},
                {"resolution": "1280x720", "vcodec": "unknown", "height": None},
            ],
            ["360p", "720p", "best"],
        ),
        ([_video(720), _video(480)], ["360p", "480p", "720p", "best"]),
        ([_video(480, vcodec="none")], ["best"]),
        ([_video(240)], ["best"]),
        ([], ["best"]),
    ],
)
def test_list_qualities(formats, expected):
    assert list_qualities({"formats": formats}) == expected


def test_list_qualities_uses_top_level_height():
    assert list_qualities({"height": 720}) == ["720p", "best"]


@pytest.mark.parametrize(
    ("quality", "expected"),
    [
        ("720p", "bestvideo[height<=720]+bestaudio/best[height<=720]/best"),
        ("1080p", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"),
        ("best", "bestvideo+bestaudio/best"),
        ("unknown", "bestvideo+bestaudio/best"),
    ],
)
def test_build_format_selector(quality, expected):
    assert build_format_selector(quality) == expected


def test_build_ydl_opts_uses_ffmpeg_and_hooks(tmp_path):
    hook = lambda data: None  # noqa: E731
    opts = build_ydl_opts(tmp_path, "720p", "/ffmpeg/ffmpeg.exe", [hook])
    assert opts["format"] == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    assert opts["paths"]["home"] == str(tmp_path)
    assert opts["ffmpeg_location"] == "/ffmpeg/ffmpeg.exe"
    assert opts["progress_hooks"] == [hook]
    assert opts["noplaylist"] is True
    assert opts["merge_output_format"] == "mp4"


def test_progress_payload():
    percent, speed, eta = progress_payload(
        {
            "status": "downloading",
            "downloaded_bytes": 512,
            "total_bytes": 1024,
            "speed": 2048,
            "eta": 65,
        }
    )
    assert percent == 50
    assert speed == "2.0 КБ/с"
    assert eta == "01:05"


def test_progress_payload_estimates():
    percent, _speed, _eta = progress_payload(
        {"status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 200}
    )
    assert percent == 25
