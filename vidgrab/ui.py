"""Главное окно VidGrab: всё взаимодействие пользователя с загрузчиком."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vidgrab import APP_NAME, APP_VERSION, strings
from vidgrab.downloader import DownloadWorker, MetadataWorker
from vidgrab.settings import Settings, save_settings
from vidgrab.theme import (
    ERROR,
    NORMAL,
    SUCCESS,
    VidGrabComboBox,
    apply_theme,
    enable_dark_title_bar,
    make_app_icon,
    make_icon,
)
from vidgrab.utils import (
    ensure_writable_dir,
    find_ffmpeg,
    format_duration,
    format_quality_label,
    normalize_url,
    is_valid_url,
    open_in_explorer,
)

log = logging.getLogger(__name__)

MetadataFactory = Callable[[str, Path | None], Any]
DownloadFactory = Callable[[str, str, Path, Path | None], Any]


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings | None = None,
        metadata_factory: MetadataFactory | None = None,
        download_factory: DownloadFactory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings or Settings()
        self._metadata_factory: MetadataFactory = metadata_factory or (
            lambda url, ffmpeg: MetadataWorker(url, ffmpeg)
        )
        self._download_factory: DownloadFactory = download_factory or (
            lambda url, quality, outdir, ffmpeg: DownloadWorker(url, quality, outdir, ffmpeg)
        )
        self._titlebar_styled = False
        self._metadata_worker: Any = None
        self._download_worker: Any = None
        self._metadata: dict[str, Any] | None = None
        self._qualities: list[str] = []
        self._last_path: Path | None = None
        self._busy: str | None = None

        apply_theme()
        self.setWindowTitle(strings.WINDOW_TITLE)
        self.setWindowIcon(make_app_icon())
        self.setMinimumSize(900, 620)
        self.resize(1040, 720)
        self._build_ui()
        self._restore_window_geometry()
        self._apply_settings()
        self._set_busy(None)
        self._set_status(strings.STATUS_IDLE)
        log.info("Окно VidGrab создано, папка по умолчанию: %s", self.settings.last_folder)

    # ---------- построение интерфейса ----------

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(18)

        # Ссылка.
        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        url_label = QLabel(strings.LABEL_URL)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(strings.PLACEHOLDER_URL)
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.setMinimumHeight(44)
        self.paste_btn = QPushButton(strings.BTN_PASTE)
        self.paste_btn.setMinimumHeight(44)
        self.check_btn = QPushButton(strings.BTN_CHECK)
        self.check_btn.setObjectName("accentButton")
        self.check_btn.setMinimumHeight(44)
        self.check_btn.setDefault(True)
        url_row.addWidget(url_label)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.paste_btn)
        url_row.addWidget(self.check_btn)
        layout.addLayout(url_row)

        # Метаданные.
        info_frame = QFrame()
        info_frame.setObjectName("infoPanel")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(20, 16, 20, 16)
        info_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_caption = QLabel(strings.LABEL_TITLE)
        title_caption.setObjectName("captionLabel")
        title_row.addWidget(title_caption)
        self.title_value = QLabel(strings.PLACEHOLDER_TITLE)
        self.title_value.setObjectName("titleValue")
        self.title_value.setWordWrap(True)
        self.title_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(self.title_value, 1)
        info_layout.addLayout(title_row)

        duration_row = QHBoxLayout()
        duration_caption = QLabel(strings.LABEL_DURATION)
        duration_caption.setObjectName("captionLabel")
        duration_row.addWidget(duration_caption)
        self.duration_value = QLabel(strings.PLACEHOLDER_DURATION)
        duration_row.addWidget(self.duration_value, 1)
        info_layout.addLayout(duration_row)
        layout.addWidget(info_frame)

        # Качество.
        quality_row = QHBoxLayout()
        quality_row.setSpacing(12)
        quality_row.addWidget(QLabel(strings.LABEL_QUALITY))
        self.quality_combo = VidGrabComboBox()
        self.quality_combo.setMinimumSize(QSize(320, 42))
        self.quality_combo.setMaximumWidth(520)
        quality_row.addWidget(self.quality_combo)
        quality_row.addStretch(1)
        layout.addLayout(quality_row)

        # Папка.
        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        folder_row.addWidget(QLabel(strings.LABEL_FOLDER))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText(str(Path.home() / "Downloads" / APP_NAME))
        self.folder_edit.setMinimumHeight(42)
        self.browse_btn = QPushButton(strings.BTN_BROWSE)
        self.browse_btn.setMinimumHeight(42)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_btn)
        layout.addLayout(folder_row)

        # Кнопки действий.
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)
        self.download_btn = QPushButton(strings.BTN_DOWNLOAD)
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.setIcon(make_icon("download", "#ffffff"))
        self.download_btn.setIconSize(QSize(18, 18))
        self.download_btn.setMinimumSize(QSize(160, 46))
        self.cancel_btn = QPushButton(strings.BTN_CANCEL)
        self.cancel_btn.setMinimumSize(QSize(130, 46))
        self.open_folder_btn = QPushButton(strings.BTN_OPEN_FOLDER)
        self.open_folder_btn.setIcon(make_icon("folder", "#e8ebf3"))
        self.open_folder_btn.setIconSize(QSize(18, 18))
        self.open_folder_btn.setMinimumSize(QSize(190, 46))
        self.open_folder_btn.setVisible(False)
        actions_row.addWidget(self.download_btn)
        actions_row.addWidget(self.cancel_btn)
        actions_row.addWidget(self.open_folder_btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        # Прогресс.
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percentLabel")
        self.percent_label.setMinimumWidth(40)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.percent_label)
        layout.addLayout(progress_row)

        details_row = QHBoxLayout()
        details_row.setSpacing(28)
        self.speed_label = QLabel(strings.PLACEHOLDER_SPEED)
        self.speed_label.setObjectName("mutedLabel")
        self.eta_label = QLabel(strings.PLACEHOLDER_ETA)
        self.eta_label.setObjectName("mutedLabel")
        details_row.addWidget(self.speed_label)
        details_row.addWidget(self.eta_label)
        details_row.addStretch(1)
        layout.addLayout(details_row)

        self.status_label = QLabel(strings.STATUS_IDLE)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)

        layout.addStretch(1)

        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

        disclaimer = QLabel(strings.DISCLAIMER)
        disclaimer.setObjectName("disclaimerLabel")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        # Сигналы.
        self.paste_btn.clicked.connect(self._on_paste)
        self.check_btn.clicked.connect(self._on_check)
        self.browse_btn.clicked.connect(self._on_browse)
        self.download_btn.clicked.connect(self._on_download)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        self.url_edit.textEdited.connect(self._on_url_edited)
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if not self._titlebar_styled:
            enable_dark_title_bar(self)
            self._titlebar_styled = True

    # ---------- настройки и состояние ----------

    def _apply_settings(self) -> None:
        self.folder_edit.setText(self.settings.last_folder)
        if self.settings.last_quality:
            self.quality_combo.addItem(
                format_quality_label(self.settings.last_quality), self.settings.last_quality
            )
            self.quality_combo.setEnabled(False)

    def _restore_window_geometry(self) -> None:
        if not self.settings.window_geometry:
            return
        try:
            data = QByteArray.fromBase64(self.settings.window_geometry.encode("ascii"))
            self.restoreGeometry(data)
        except (ValueError, TypeError):
            log.warning("Не удалось восстановить геометрию окна", exc_info=True)

    def _save_window_geometry(self) -> None:
        try:
            self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        except Exception:  # noqa: BLE001 - не критично для работы
            log.warning("Не удалось сохранить геометрию окна", exc_info=True)

    def _save_settings(self) -> None:
        self._save_window_geometry()
        self.settings.last_folder = self.folder_edit.text().strip() or self.settings.last_folder
        current = self.quality_combo.currentData()
        if isinstance(current, str) and current:
            self.settings.last_quality = current
        save_settings(self.settings)

    def _set_status(self, text: str, *, error: bool = False, ok: bool = False) -> None:
        color = ERROR if error else (SUCCESS if ok else NORMAL)
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(text)

    def _set_busy(self, busy: str | None) -> None:
        self._busy = busy
        idle = busy is None
        has_qualities = bool(self._qualities)
        self.url_edit.setEnabled(idle)
        self.paste_btn.setEnabled(idle)
        self.check_btn.setEnabled(idle)
        self.folder_edit.setEnabled(idle)
        self.browse_btn.setEnabled(idle)
        self.quality_combo.setEnabled(idle and has_qualities)
        self.download_btn.setEnabled(idle and has_qualities and self._metadata is not None)
        self.cancel_btn.setEnabled(busy == "download")

    def _reset_metadata(self) -> None:
        self._metadata = None
        self._qualities = []
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        self.quality_combo.blockSignals(False)
        self.title_value.setText(strings.PLACEHOLDER_TITLE)
        self.duration_value.setText(strings.PLACEHOLDER_DURATION)
        self.open_folder_btn.setVisible(False)
        self._last_path = None

    def _reset_progress(self) -> None:
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.speed_label.setText(strings.PLACEHOLDER_SPEED)
        self.eta_label.setText(strings.PLACEHOLDER_ETA)

    # ---------- действия ----------

    def _current_url(self) -> str:
        url = normalize_url(self.url_edit.text())
        return url if is_valid_url(url) else ""

    def _warn(self, message: str) -> None:
        log.warning("Предупреждение пользователю: %s", message)
        QMessageBox.warning(self, strings.DIALOG_WARNING_TITLE, message)

    def _error(self, message: str) -> None:
        log.error("Ошибка пользователю: %s", message)
        QMessageBox.critical(self, strings.DIALOG_ERROR_TITLE, message)

    def _on_paste(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            self._set_status(strings.STATUS_CLIPBOARD_EMPTY)
            return
        self.url_edit.setText(text)
        self._on_url_edited(text)
        self.url_edit.setFocus()

    def _on_url_edited(self, _text: str) -> None:
        if self._metadata is not None:
            self._reset_metadata()
            self._set_status(strings.STATUS_IDLE)
            self._set_busy(None)

    def _on_quality_changed(self, _text: str) -> None:
        value = self.quality_combo.currentData()
        if isinstance(value, str) and value:
            self.settings.last_quality = value

    def _on_check(self) -> None:
        if self._busy is not None:
            return
        url = self._current_url()
        if not url:
            self._warn(strings.MSG_INVALID_URL)
            self._set_status(strings.STATUS_IDLE)
            return
        self.url_edit.setText(url)
        self._reset_metadata()
        self._reset_progress()
        self._set_status(strings.STATUS_CHECKING)
        self._set_busy("metadata")
        self.progress_bar.setRange(0, 0)

        worker = self._metadata_factory(url, find_ffmpeg())
        worker.ready.connect(self._on_metadata_ready)
        worker.failed.connect(self._on_metadata_failed)
        worker.finished.connect(self._on_metadata_finished)
        self._metadata_worker = worker
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("Не удалось запустить проверку ссылки")
            self._metadata_worker = None
            self.progress_bar.setRange(0, 100)
            self._set_busy(None)
            self._error(strings.ERRORS["generic"].format(detail=str(exc)))

    def _on_metadata_ready(self, summary: dict[str, Any]) -> None:
        log.info("Интерфейс получил метаданные: %s", summary.get("title"))
        self._metadata = summary
        self.title_value.setText(str(summary.get("title") or strings.PLACEHOLDER_TITLE))
        self.duration_value.setText(format_duration(summary.get("duration")))
        self._qualities = list(summary.get("qualities") or [])
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        for quality in self._qualities:
            self.quality_combo.addItem(format_quality_label(quality), quality)
        preferred = self.settings.last_quality
        if preferred in self._qualities:
            self.quality_combo.setCurrentIndex(self._qualities.index(preferred))
        else:
            self.quality_combo.setCurrentIndex(self._qualities.index("best"))
        self.quality_combo.blockSignals(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(None)
        self._set_status(strings.STATUS_READY, ok=True)

    def _on_metadata_failed(self, code: str, message: str) -> None:
        log.warning("Проверка ссылки не удалась: code=%s", code)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(None)
        self._set_status(strings.STATUS_ERROR, error=True)
        self._error(message)

    def _on_metadata_finished(self) -> None:
        worker = self._metadata_worker
        self._metadata_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_browse(self) -> None:
        start = self.folder_edit.text().strip() or self.settings.last_folder
        chosen = QFileDialog.getExistingDirectory(self, strings.LABEL_FOLDER, start)
        if chosen:
            self.folder_edit.setText(chosen)
            self.settings.last_folder = chosen
            save_settings(self.settings)
            log.info("Выбрана папка сохранения: %s", chosen)

    def _on_download(self) -> None:
        if self._busy is not None:
            return
        url = self._current_url()
        if not url:
            self._warn(strings.MSG_INVALID_URL)
            return
        if self._metadata is None:
            self._warn(strings.MSG_NEED_CHECK)
            return
        quality = self.quality_combo.currentData()
        if not isinstance(quality, str) or not quality:
            self._warn(strings.MSG_NO_QUALITY)
            return

        folder_text = self.folder_edit.text().strip() or self.settings.last_folder
        folder = Path(folder_text).expanduser()
        writable, reason = ensure_writable_dir(folder)
        if not writable:
            log.error("Папка недоступна для записи: %s (%s)", folder, reason)
            self._error(f"{strings.ERRORS['permission']}\n\n{folder}\n{reason}")
            return

        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            log.error("ffmpeg не найден, загрузка невозможна")
            self._error(strings.ERRORS["ffmpeg"])
            return

        self.folder_edit.setText(str(folder))
        self._reset_progress()
        self.open_folder_btn.setVisible(False)
        self._last_path = None
        self.progress_bar.setRange(0, 100)
        self._set_status(strings.STATUS_DOWNLOADING)
        self._set_busy("download")

        worker = self._download_factory(url, quality, folder, ffmpeg_path)
        worker.progress.connect(self._on_progress)
        worker.stage_changed.connect(self._on_stage_changed)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_download_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_download_finished)
        self._download_worker = worker

        self.settings.last_folder = str(folder)
        self.settings.last_quality = quality
        save_settings(self.settings)

        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            log.exception("Не удалось запустить загрузку")
            self._download_worker = None
            self._set_busy(None)
            self._error(strings.ERRORS["generic"].format(detail=str(exc)))

    def _on_progress(self, percent: int, speed: str, eta: str) -> None:
        self.progress_bar.setValue(max(0, min(100, percent)))
        self.percent_label.setText(f"{percent}%")
        self.speed_label.setText(f"Скорость: {speed}")
        self.eta_label.setText(f"Осталось: {eta}")
        self._set_status(strings.STATUS_DOWNLOADING)

    def _on_stage_changed(self, text: str) -> None:
        self._set_status(text)

    def _on_completed(self, path: str) -> None:
        self._last_path = Path(path)
        self.progress_bar.setValue(100)
        self.percent_label.setText("100%")
        self.speed_label.setText(strings.PLACEHOLDER_SPEED)
        self.eta_label.setText(strings.PLACEHOLDER_ETA)
        self._set_busy(None)
        self.open_folder_btn.setVisible(True)
        self._set_status(strings.STATUS_DONE.format(path=path), ok=True)
        self._save_settings()
        log.info("Интерфейс: загрузка завершена, файл %s", path)

    def _on_download_failed(self, code: str, message: str) -> None:
        self._set_busy(None)
        self._set_status(strings.STATUS_ERROR, error=True)
        self._error(message)

    def _on_cancelled(self) -> None:
        self._set_busy(None)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.speed_label.setText(strings.PLACEHOLDER_SPEED)
        self.eta_label.setText(strings.PLACEHOLDER_ETA)
        self.open_folder_btn.setVisible(False)
        self._set_status(strings.STATUS_CANCELLED, error=True)

    def _on_download_finished(self) -> None:
        worker = self._download_worker
        self._download_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_cancel(self) -> None:
        worker = self._download_worker
        if worker is None:
            return
        self.cancel_btn.setEnabled(False)
        self._set_status(strings.STATUS_CANCELLING)
        try:
            worker.request_cancel()
        except Exception:  # noqa: BLE001
            log.exception("Не удалось запросить отмену")

    def _on_open_folder(self) -> None:
        target = self._last_path or Path(self.folder_edit.text().strip() or ".")
        try:
            open_in_explorer(target)
        except Exception as exc:  # noqa: BLE001
            log.exception("Не удалось открыть папку %s", target)
            self._error(f"Не удалось открыть папку: {exc}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        worker = self._download_worker
        if worker is not None and getattr(worker, "isRunning", lambda: False)():
            answer = QMessageBox.question(
                self,
                strings.DIALOG_WARNING_TITLE,
                strings.MSG_CLOSE_WHILE_DOWNLOADING,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._on_cancel()
            if not worker.wait(10000):
                log.warning("Поток загрузки не завершился за 10 секунд")
                self._error(strings.MSG_CLOSE_WAIT)
                event.ignore()
                return
        self._save_settings()
        log.info("Окно закрывается")
        event.accept()
