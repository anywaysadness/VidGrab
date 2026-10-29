"""Диалог настроек: cookies браузера и клиент YouTube (авторизация, не обход DRM)."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vidgrab import strings
from vidgrab.settings import Settings
from vidgrab.theme import VidGrabComboBox

log = logging.getLogger(__name__)

BROWSERS = (
    ("", strings.SETTINGS_COOKIES_NONE),
    ("chrome", "Chrome"),
    ("edge", "Edge"),
    ("firefox", "Firefox"),
    ("file", strings.SETTINGS_COOKIES_FILE),
)
CLIENTS = (
    ("", strings.SETTINGS_CLIENT_AUTO),
    ("web", "web"),
    ("tv", "tv"),
)


class SettingsDialog(QDialog):
    """Небольшой диалог: источник cookies и клиент YouTube."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(strings.SETTINGS_TITLE)
        self.setModal(True)
        self.setMinimumWidth(560)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.cookies_combo = VidGrabComboBox()
        self.cookies_combo.setMinimumHeight(38)
        for value, label in BROWSERS:
            self.cookies_combo.addItem(label, value)
        form.addRow(QLabel(strings.SETTINGS_COOKIES), self.cookies_combo)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        self.file_edit = QLineEdit()
        self.file_edit.setMinimumHeight(38)
        self.file_edit.setPlaceholderText("C:\\Users\\…\\cookies.txt")
        self.browse_btn = QPushButton(strings.BTN_BROWSE)
        self.browse_btn.setMinimumHeight(38)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(self.browse_btn)
        file_widget = QWidget()
        file_widget.setLayout(file_row)
        form.addRow(QLabel(strings.SETTINGS_COOKIES_FILE_LABEL), file_widget)

        self.client_combo = VidGrabComboBox()
        self.client_combo.setMinimumHeight(38)
        for value, label in CLIENTS:
            self.client_combo.addItem(label, value)
        form.addRow(QLabel(strings.SETTINGS_CLIENT), self.client_combo)

        layout.addLayout(form)

        hint = QLabel(strings.SETTINGS_COOKIES_HINT)
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(strings.BTN_DIALOG_CANCEL)
        self.save_btn = QPushButton(strings.BTN_SAVE)
        self.save_btn.setObjectName("accentButton")
        self.save_btn.setDefault(True)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

        self.browse_btn.clicked.connect(self._on_browse)
        self.cookies_combo.currentIndexChanged.connect(self._sync_file_enabled)
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load(self) -> None:
        source = self._settings.cookies_from_browser
        if not source and self._settings.cookies_file.strip():
            source = "file"
        index = self.cookies_combo.findData(source)
        self.cookies_combo.setCurrentIndex(max(0, index))
        self.file_edit.setText(self._settings.cookies_file)
        client_index = self.client_combo.findData(self._settings.youtube_client)
        self.client_combo.setCurrentIndex(max(0, client_index))
        self._sync_file_enabled()

    def _sync_file_enabled(self) -> None:
        is_file = self.cookies_combo.currentData() == "file"
        self.file_edit.setEnabled(is_file)
        self.browse_btn.setEnabled(is_file)

    def _on_browse(self) -> None:
        start = self.file_edit.text().strip() or str(Path.home())
        chosen, _filter = QFileDialog.getOpenFileName(
            self, strings.SETTINGS_COOKIES_FILE_LABEL, start, "Cookies (*.txt);;Все файлы (*)"
        )
        if chosen:
            self.file_edit.setText(chosen)

    def _on_save(self) -> None:
        source = self.cookies_combo.currentData()
        if source == "file":
            path_text = self.file_edit.text().strip()
            if not path_text:
                QMessageBox.warning(self, strings.DIALOG_WARNING_TITLE, strings.SETTINGS_COOKIES_FILE_EMPTY)
                return
            path = Path(path_text).expanduser()
            if not path.is_file():
                QMessageBox.warning(
                    self,
                    strings.DIALOG_WARNING_TITLE,
                    strings.SETTINGS_COOKIES_FILE_MISSING.format(path=path),
                )
                return
            self._settings.cookies_from_browser = ""
            self._settings.cookies_file = str(path)
        elif source:
            self._settings.cookies_from_browser = str(source)
            self._settings.cookies_file = ""
        else:
            self._settings.cookies_from_browser = ""
            self._settings.cookies_file = ""
        self._settings.youtube_client = str(self.client_combo.currentData() or "")
        log.info(
            "Настройки сохранены: cookies=%s, клиент YouTube=%s",
            self._settings.cookies_from_browser or ("файл" if self._settings.cookies_file else "нет"),
            self._settings.youtube_client or "авто",
        )
        self.accept()
