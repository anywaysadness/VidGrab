from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

from vidgrab import strings
from vidgrab.settings import Settings
from vidgrab.ui import MainWindow

SUMMARY = {
    "id": "abc123",
    "title": "Демо-видео для теста",
    "duration": 125,
    "qualities": ["360p", "480p", "720p", "best"],
}


class FakeMetadataWorker(QObject):
    ready = Signal(dict)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, summary=None, error=None):
        super().__init__()
        self._summary = summary
        self._error = error

    def start(self):
        if self._summary is not None:
            self.ready.emit(self._summary)
        if self._error is not None:
            self.failed.emit(*self._error)
        self.finished.emit()

    def deleteLater(self):
        pass


class FakeDownloadWorker(QObject):
    progress = Signal(int, str, str)
    stage_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str, str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, path=None, error=None, auto=True):
        super().__init__()
        self._path = path
        self._error = error
        self._auto = auto
        self.cancel_requested = False

    def start(self):
        if not self._auto:
            return
        self.progress.emit(42, "1.2 МБ/с", "00:12")
        if self._error is not None:
            self.failed.emit(*self._error)
        elif self._path is not None:
            self.completed.emit(str(self._path))
        self.finished.emit()

    def request_cancel(self):
        self.cancel_requested = True
        self.cancelled.emit()
        self.finished.emit()

    def isRunning(self):
        return False

    def wait(self, _timeout=0):
        return True

    def deleteLater(self):
        pass


@pytest.fixture()
def message_boxes(monkeypatch):
    calls = {"warning": [], "critical": [], "question": []}
    monkeypatch.setattr(
        "vidgrab.ui.QMessageBox.warning",
        staticmethod(lambda *a, **k: calls["warning"].append(a[2] if len(a) > 2 else "")),
    )
    monkeypatch.setattr(
        "vidgrab.ui.QMessageBox.critical",
        staticmethod(lambda *a, **k: calls["critical"].append(a[2] if len(a) > 2 else "")),
    )
    return calls


def make_window(
    tmp_path, summary=SUMMARY, metadata_error=None, download=None, download_error=None
):
    settings = Settings(last_folder=str(tmp_path), last_quality="720p")
    created = {}

    def metadata_factory(url, ffmpeg, config):
        created["metadata_config"] = config
        worker = FakeMetadataWorker(summary if metadata_error is None else None, metadata_error)
        created["metadata"] = worker
        return worker

    def download_factory(url, quality, outdir, ffmpeg, config):
        created["download_args"] = (url, quality, str(outdir), ffmpeg)
        created["download_config"] = config
        worker = FakeDownloadWorker(
            path=download or (Path(outdir) / "video.mp4"),
            error=download_error,
            auto=True,
        )
        created["download"] = worker
        return worker

    window = MainWindow(
        settings,
        metadata_factory=metadata_factory,
        download_factory=download_factory,
    )
    return window, created


def test_window_initial_state(qapp, tmp_path):
    from PySide6.QtWidgets import QLabel

    window, _ = make_window(tmp_path)
    assert any(label.text() == strings.DISCLAIMER for label in window.findChildren(QLabel))
    assert not window.download_btn.isEnabled()
    assert not window.quality_combo.isEnabled()
    assert window.status_label.text() == strings.STATUS_IDLE
    window.close()


def test_paste_from_clipboard(qapp, tmp_path):
    from PySide6.QtGui import QGuiApplication

    window, _ = make_window(tmp_path)
    QGuiApplication.clipboard().setText("  https://example.com/video  ")
    window._on_paste()
    assert window.url_edit.text() == "https://example.com/video"
    window.close()


def test_invalid_url_warning(qapp, tmp_path, message_boxes):
    window, created = make_window(tmp_path)
    window.url_edit.setText("не ссылка")
    window._on_check()
    assert message_boxes["warning"]
    assert "metadata" not in created
    window.close()


def test_check_fills_metadata(qapp, tmp_path):
    window, created = make_window(tmp_path)
    window.url_edit.setText("https://example.com/video")
    window._on_check()

    assert "metadata" in created
    assert window.title_value.text() == SUMMARY["title"]
    assert window.duration_value.text() == "02:05"
    assert [window.quality_combo.itemData(i) for i in range(window.quality_combo.count())] == SUMMARY["qualities"]
    assert window.quality_combo.currentData() == "720p"
    assert window.download_btn.isEnabled()
    assert window.status_label.text() == strings.STATUS_READY

    window.show()
    qapp.processEvents()
    window.grab().save(str(tmp_path / "gui_ready.png"))
    window.close()


def test_check_error_shows_message(qapp, tmp_path, message_boxes):
    window, _ = make_window(tmp_path, metadata_error=("network", "Нет подключения к интернету."))
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    assert message_boxes["critical"]
    assert not window.download_btn.isEnabled()
    window.close()


def test_download_flow(qapp, tmp_path, monkeypatch):
    output = tmp_path / "out"
    output.mkdir()
    target = output / "Демо-видео.mp4"
    target.write_bytes(b"video")

    window, created = make_window(tmp_path, download=target)
    monkeypatch.setattr("vidgrab.ui.find_ffmpeg", lambda: Path("/fake/ffmpeg.exe"))
    opened = []
    monkeypatch.setattr("vidgrab.ui.open_folder", lambda path: opened.append(Path(path)) or Path(path))

    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.folder_edit.setText(str(output))
    window.show()
    qapp.processEvents()
    window._on_download()

    _url, quality, outdir, ffmpeg = created["download_args"]
    assert quality == "720p"
    assert outdir == str(output)
    assert ffmpeg == Path("/fake/ffmpeg.exe")
    assert created["download_config"] is not None
    assert window.progress_bar.value() == 100
    assert window.open_folder_btn.isVisible()
    assert window.open_folder_btn.isEnabled()
    assert window.result_frame.isVisible()
    assert target.name in window.result_label.text()
    assert window._last_path == target
    assert "Готово" in window.status_label.text()
    assert window.settings.last_folder == str(output)

    window.grab().save(str(tmp_path / "gui_done.png"))

    # Кнопка «Открыть папку» ведёт в папку из поля, а не к файлу.
    window._on_open_folder()
    assert opened[-1] == output

    # Клик по ссылке результата тоже открывает папку.
    window._on_result_link()
    assert opened[-1] == output
    window.close()


def test_download_requires_check(qapp, tmp_path, message_boxes):
    window, created = make_window(tmp_path)
    window.url_edit.setText("https://example.com/video")
    window._on_download()
    assert message_boxes["warning"]
    assert "download" not in created
    window.close()


def test_cancel_flow(qapp, tmp_path, monkeypatch):
    window, created = make_window(tmp_path)
    monkeypatch.setattr("vidgrab.ui.find_ffmpeg", lambda: Path("/fake/ffmpeg.exe"))

    def download_factory(url, quality, outdir, ffmpeg, config):
        worker = FakeDownloadWorker(auto=False)
        created["download"] = worker
        return worker

    window._download_factory = download_factory
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.folder_edit.setText(str(tmp_path))
    window._on_download()
    assert window.cancel_btn.isEnabled()

    window._on_cancel()
    assert created["download"].cancel_requested
    assert window.status_label.text() == strings.STATUS_CANCELLED
    assert window.cancel_btn.isEnabled() is False
    assert window.download_btn.isEnabled()
    # После отмены прогресс сброшен, ссылка результата скрыта.
    assert window.progress_bar.value() == 0
    assert window.percent_label.text() == "0%"
    assert window.speed_label.text() == strings.PLACEHOLDER_SPEED
    assert window.eta_label.text() == strings.PLACEHOLDER_ETA
    assert not window.result_frame.isVisible()
    assert window._last_path is None

    window.show()
    qapp.processEvents()
    window.grab().save(str(tmp_path / "gui_cancelled.png"))
    window.close()


def test_error_resets_progress_and_hides_result(qapp, tmp_path, message_boxes):
    window, created = make_window(tmp_path, download_error=("forbidden", "HTTP 403"))
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window._on_download()

    assert message_boxes["critical"]
    assert window.progress_bar.value() == 0
    assert window.percent_label.text() == "0%"
    assert window.speed_label.text() == strings.PLACEHOLDER_SPEED
    assert window.eta_label.text() == strings.PLACEHOLDER_ETA
    assert not window.result_frame.isVisible()
    assert window._last_path is None
    assert window.status_label.text() == strings.STATUS_ERROR
    assert window.download_btn.isEnabled()
    window.close()


def test_open_folder_button_works_without_download(qapp, tmp_path, monkeypatch):
    window, _ = make_window(tmp_path)
    chosen = tmp_path / "выбранная папка"
    window.folder_edit.setText(str(chosen))
    opened = []
    monkeypatch.setattr("vidgrab.ui.open_folder", lambda path: opened.append(Path(path)) or Path(path))

    window.show()
    qapp.processEvents()
    assert window.open_folder_btn.isVisible()
    assert window.open_folder_btn.isEnabled()

    window._on_open_folder()
    assert opened == [chosen]
    window.close()


def test_result_link_falls_back_when_file_deleted(qapp, tmp_path, monkeypatch):
    output = tmp_path / "out"
    output.mkdir()
    target = output / "video.mp4"
    target.write_bytes(b"video")

    window, _ = make_window(tmp_path, download=target)
    monkeypatch.setattr("vidgrab.ui.find_ffmpeg", lambda: Path("/fake/ffmpeg.exe"))
    opened = []
    monkeypatch.setattr("vidgrab.ui.open_folder", lambda path: opened.append(Path(path)) or Path(path))

    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.folder_edit.setText(str(output))
    window.show()
    qapp.processEvents()
    window._on_download()
    assert window.result_frame.isVisible()

    target.unlink()
    window._on_result_link()
    assert opened[-1] == output  # удалённый файл не мешает открыть папку
    window.close()


def test_result_hidden_on_new_check(qapp, tmp_path, monkeypatch):
    output = tmp_path / "out"
    output.mkdir()
    target = output / "video.mp4"
    target.write_bytes(b"video")

    window, _ = make_window(tmp_path, download=target)
    monkeypatch.setattr("vidgrab.ui.find_ffmpeg", lambda: Path("/fake/ffmpeg.exe"))
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.folder_edit.setText(str(output))
    window.show()
    qapp.processEvents()
    window._on_download()
    assert window.result_frame.isVisible()

    # Новая ссылка и повторная проверка убирают прошлый результат.
    window.url_edit.setText("https://example.com/other")
    window._on_check()
    assert not window.result_frame.isVisible()
    assert window._last_path is None
    window.close()


def test_report_button_creates_file(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("VIDGRAB_APPDATA", str(tmp_path / "appdata"))
    window, _ = make_window(tmp_path)
    monkeypatch.setattr(
        "vidgrab.ui.write_report",
        lambda settings: _fake_report(tmp_path),
    )
    monkeypatch.setattr("vidgrab.ui.QMessageBox.exec", lambda self: 0)
    window._on_report()
    assert (tmp_path / "report.txt").is_file()
    assert strings.STATUS_REPORT_DONE.format(path=tmp_path / "report.txt") in window.status_label.text()
    window.close()


def _fake_report(tmp_path):
    path = tmp_path / "report.txt"
    path.write_text("report", encoding="utf-8")
    return path


def test_quality_change_persists_in_settings(qapp, tmp_path):
    window, _ = make_window(tmp_path)
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.quality_combo.setCurrentIndex(1)  # 480p
    assert window.settings.last_quality == "480p"
    window.close()


def test_close_saves_settings(qapp, tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("VIDGRAB_APPDATA", str(tmp_path / "appdata"))
    window, _ = make_window(tmp_path)
    window.url_edit.setText("https://example.com/video")
    window._on_check()
    window.folder_edit.setText(str(tmp_path / "chosen"))
    window._save_settings()
    window.close()

    saved = tmp_path / "appdata" / "settings.json"
    assert saved.is_file()
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["last_folder"] == str(tmp_path / "chosen")
    assert data["language"] == "ru"


def test_theme_and_icons(qapp, tmp_path):
    window, _ = make_window(tmp_path)
    assert qapp.styleSheet()
    assert not window.download_btn.icon().isNull()
    assert not window.open_folder_btn.icon().isNull()
    assert window.minimumWidth() >= 900
    window.close()
