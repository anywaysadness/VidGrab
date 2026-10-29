from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from vidgrab.downloader import (
    DownloadCancelled,
    DownloadWorker,
    MetadataWorker,
    describe_error,
)


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (DownloadCancelled(), "cancelled"),
        (DownloadError("ERROR: This video is private"), "unavailable"),
        (DownloadError("ERROR: Video unavailable"), "unavailable"),
        (DownloadError("ERROR: HTTP Error 404: Not Found"), "unavailable"),
        (DownloadError("ERROR: Sign in to confirm your age"), "unavailable"),
        (DownloadError("ERROR: unable to download video data: HTTP Error 403: Forbidden"), "forbidden"),
        (
            DownloadError("ERROR: Sign in to confirm you're not a bot. Use --cookies-from-browser"),
            "bot_check",
        ),
        (
            DownloadError("ERROR: Requested format is not available"),
            "format_unavailable",
        ),
        (
            DownloadError("ERROR: This video is DRM protected and cannot be downloaded"),
            "drm",
        ),
        (
            DownloadError("ERROR: Failed to decrypt with DPAPI (cookie database is locked)"),
            "cookies",
        ),
        (
            DownloadError(
                "ERROR: You have requested merging of multiple formats but ffmpeg is not installed"
            ),
            "ffmpeg",
        ),
        (PermissionError("Permission denied"), "permission"),
        (ConnectionResetError("Connection reset by peer"), "network"),
        (TimeoutError("timed out"), "network"),
        (DownloadError("ERROR: Unable to download webpage: <urlopen error timed out>"), "network"),
        (RuntimeError("совсем другая ошибка"), "generic"),
    ],
)
def test_describe_error(exc, code):
    actual_code, message = describe_error(exc)
    assert actual_code == code
    assert message


def test_describe_error_generic_contains_detail():
    _code, message = describe_error(RuntimeError("boom"))
    assert "boom" in message


class _MetaYDL:
    def __init__(self, opts):
        self.opts = opts
        self.closed = False

    def extract_info(self, url, download=False):
        assert download is False
        return {
            "id": "abc123",
            "title": "Демо-видео",
            "duration": 65,
            "webpage_url": url,
            "formats": [
                {"height": 1080, "vcodec": "avc1", "acodec": "mp4a"},
                {"height": 720, "vcodec": "avc1", "acodec": None},
                {"height": 480, "vcodec": "avc1", "acodec": None},
            ],
        }

    def close(self):
        self.closed = True


def test_metadata_worker_ready():
    worker = MetadataWorker("https://example.com/v", None, ydl_factory=_MetaYDL)
    results = []
    worker.ready.connect(results.append)
    worker.run()
    assert results
    summary = results[0]
    assert summary["title"] == "Демо-видео"
    assert summary["duration"] == 65
    assert summary["qualities"] == ["360p", "480p", "720p", "1080p", "best"]


class _ErrorMetaYDL:
    def __init__(self, opts):
        pass

    def extract_info(self, url, download=False):
        raise DownloadError("ERROR: This video is private")

    def close(self):
        pass


def test_metadata_worker_error():
    worker = MetadataWorker("https://example.com/v", None, ydl_factory=_ErrorMetaYDL)
    failures = []
    worker.failed.connect(lambda code, message: failures.append((code, message)))
    worker.run()
    assert failures and failures[0][0] == "unavailable"


class _DownloadYDL:
    def __init__(self, opts):
        self.opts = opts
        self.closed = False
        self.filepath = Path(opts["paths"]["home"]) / "Демо [abc123].mp4"

    def extract_info(self, url, download=True):
        assert download is True
        hooks = self.opts["progress_hooks"]
        hooks[0](
            {
                "status": "downloading",
                "downloaded_bytes": 40,
                "total_bytes": 100,
                "speed": 1024,
                "eta": 5,
            }
        )
        hooks[0](
            {
                "status": "downloading",
                "downloaded_bytes": 100,
                "total_bytes": 100,
                "speed": 2048,
                "eta": 0,
            }
        )
        hooks[0]({"status": "finished"})
        self.filepath.write_bytes(b"fake video data")
        return {"id": "abc123", "title": "Демо", "filepath": str(self.filepath)}

    def prepare_filename(self, info):
        return info["filepath"]

    def close(self):
        self.closed = True


def test_download_worker_success(tmp_path):
    worker = DownloadWorker(
        "https://example.com/v", "720p", tmp_path, None, ydl_factory=_DownloadYDL
    )
    progress = []
    stages = []
    completed = []
    worker.progress.connect(lambda p, s, e: progress.append((p, s, e)))
    worker.stage_changed.connect(stages.append)
    worker.completed.connect(completed.append)
    worker.run()

    assert [p[0] for p in progress] == [40, 100, 100]
    assert progress[0][1] == "1.0 КБ/с"
    assert progress[0][2] == "00:05"
    assert stages == ["Обработка (склейка/конвертация)…"]
    assert completed and Path(completed[0]).is_file()


class _CancelYDL:
    def __init__(self, opts):
        self.opts = opts
        self.part = Path(opts["paths"]["home"]) / "video.mp4.part"

    def extract_info(self, url, download=True):
        self.part.write_bytes(b"incomplete")
        self.opts["progress_hooks"][0](
            {"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100}
        )
        raise AssertionError("hook должен был прервать загрузку")

    def close(self):
        pass


def test_download_worker_cancel_cleans_part(tmp_path):
    worker = DownloadWorker(
        "https://example.com/v", "best", tmp_path, None, ydl_factory=_CancelYDL
    )
    cancelled = []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.request_cancel()
    worker.run()

    assert cancelled
    assert not list(tmp_path.glob("*.part"))
    assert not list(tmp_path.glob("*.ytdl"))


class _FailYDL:
    def __init__(self, opts):
        pass

    def extract_info(self, url, download=True):
        raise PermissionError("Permission denied: 'C:/video.mp4.part'")

    def close(self):
        pass


def test_download_worker_permission_error(tmp_path):
    worker = DownloadWorker(
        "https://example.com/v", "best", tmp_path, None, ydl_factory=_FailYDL
    )
    failures = []
    worker.failed.connect(lambda code, message: failures.append((code, message)))
    worker.run()
    assert failures and failures[0][0] == "permission"


def test_public_video_errors_do_not_mention_drm():
    """403 и bot-check на публичном видео не должны выглядеть как DRM."""
    for exc in (
        DownloadError("ERROR: unable to download video data: HTTP Error 403: Forbidden"),
        DownloadError("ERROR: Sign in to confirm you're not a bot"),
        DownloadError("ERROR: This video is private"),
        DownloadError("ERROR: Requested format is not available"),
    ):
        _code, message = describe_error(exc)
        assert "DRM" not in message
        assert "не обходит" not in message
        assert "приложение не" not in message.lower()


def test_build_ydl_opts_uses_quickjs_and_cookies(tmp_path):
    from vidgrab.downloader import YdlConfig, build_ydl_opts

    qjs = tmp_path / "qjs.exe"
    cookies = tmp_path / "cookies.txt"
    config = YdlConfig(
        js_runtime=qjs,
        cookies_from_browser="chrome",
        youtube_client="web",
    )
    opts = build_ydl_opts(tmp_path, "720p", None, config=config)
    assert opts["js_runtimes"] == {"quickjs": {"path": str(qjs)}}
    assert opts["cookiesfrombrowser"] == ("chrome",)
    assert "cookiefile" not in opts
    assert opts["extractor_args"] == {"youtube": {"player_client": ["web"]}}

    config = YdlConfig(cookies_file=str(cookies))
    opts = build_ydl_opts(tmp_path, "best", None, config=config)
    assert opts["cookiefile"] == str(cookies)
    assert "cookiesfrombrowser" not in opts
    assert "js_runtimes" not in opts  # без qjs остаётся поведение yt-dlp по умолчанию


def test_workers_pass_config_to_ydl(tmp_path):
    from vidgrab.downloader import YdlConfig

    seen = {}

    class _CaptureYDL:
        def __init__(self, opts):
            seen["opts"] = opts

        def extract_info(self, url, download=False):
            return {
                "id": "x",
                "title": "t",
                "formats": [{"height": 720, "vcodec": "avc1"}],
            }

        def close(self):
            pass

    config = YdlConfig(js_runtime=tmp_path / "qjs.exe")
    worker = MetadataWorker(
        "https://example.com/v", None, ydl_factory=_CaptureYDL, config=config
    )
    worker.run()
    assert seen["opts"]["js_runtimes"]["quickjs"]["path"] == str(tmp_path / "qjs.exe")
