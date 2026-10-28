"""Оформление VidGrab: тёмная тема, палитра, стили и векторные иконки."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QComboBox

ACCENT = "#3b82f6"
TEXT = "#e8ebf3"
MUTED = "#98a0b3"
SUCCESS = "#4ade80"
ERROR = "#f87171"
NORMAL = "#c6ccda"

STYLE = """
QMainWindow, QDialog {
    background-color: #1b1d24;
}
QWidget#centralWidget {
    background-color: #1b1d24;
}
QLabel {
    background: transparent;
    color: #c6ccda;
    font-size: 10pt;
}
QLabel#captionLabel {
    color: #98a0b3;
    min-width: 112px;
}
QLabel#titleValue {
    color: #e8ebf3;
    font-size: 11pt;
    font-weight: 600;
}
QLabel#percentLabel {
    color: #e8ebf3;
    font-size: 10pt;
}
QLabel#mutedLabel {
    color: #98a0b3;
}
QLabel#statusLabel {
    color: #c6ccda;
    font-size: 10pt;
}
QLabel#disclaimerLabel {
    color: #7f8798;
    font-size: 9pt;
}
QLineEdit, QComboBox {
    background-color: #15171d;
    border: 1px solid #303544;
    border-radius: 9px;
    padding: 8px 12px;
    color: #e8ebf3;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    min-height: 22px;
}
QLineEdit:hover, QComboBox:hover {
    border-color: #3a4152;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #6b7280;
    background-color: #1a1c23;
    border-color: #272b36;
}
QComboBox {
    padding-right: 36px;
}
QComboBox::drop-down {
    border: none;
    width: 0px;
}
QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QComboBox QAbstractItemView {
    background-color: #20232c;
    border: 1px solid #303544;
    border-radius: 8px;
    color: #e8ebf3;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}
QPushButton {
    background-color: #242833;
    border: 1px solid #303544;
    border-radius: 9px;
    padding: 9px 18px;
    color: #e8ebf3;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #2c3140;
    border-color: #3a4152;
}
QPushButton:pressed {
    background-color: #1f232e;
}
QPushButton:disabled {
    background-color: #1e212a;
    border-color: #272b36;
    color: #636b7c;
}
QPushButton#primaryButton {
    background-color: #3b82f6;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: 600;
    padding: 9px 22px;
}
QPushButton#primaryButton:hover {
    background-color: #4f8ff7;
    border-color: #4f8ff7;
}
QPushButton#primaryButton:pressed {
    background-color: #2f6fd0;
    border-color: #2f6fd0;
}
QPushButton#primaryButton:disabled {
    background-color: #2a3342;
    border-color: #2a3342;
    color: #7b8496;
}
QPushButton#accentButton {
    background-color: transparent;
    border: 1px solid #3b82f6;
    color: #8bb8ff;
}
QPushButton#accentButton:hover {
    background-color: rgba(59, 130, 246, 0.14);
}
QPushButton#accentButton:pressed {
    background-color: rgba(59, 130, 246, 0.22);
}
QFrame#infoPanel {
    background-color: #20232b;
    border: 1px solid #2b2f3a;
    border-radius: 12px;
}
QFrame#infoPanel QLabel {
    color: #e8ebf3;
}
QFrame#infoPanel QLabel#captionLabel {
    color: #98a0b3;
}
QFrame#separator {
    background-color: #2a2e39;
    border: none;
    max-height: 1px;
    min-height: 1px;
}
QProgressBar {
    background-color: #242833;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
QToolTip {
    background-color: #20232c;
    color: #e8ebf3;
    border: 1px solid #303544;
    padding: 6px;
}
"""


def dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1b1d24"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor("#15171d"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#20232b"))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor("#242833"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#20232c"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#8bb8ff"))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#636b7c"))
    return palette


def _draw_download(painter: QPainter, size: int, color: str) -> None:
    width = max(1.6, size / 10)
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    center = size / 2
    painter.drawLine(QPointF(center, size * 0.18), QPointF(center, size * 0.68))
    painter.drawLine(
        QPointF(center - size * 0.22, size * 0.47),
        QPointF(center, size * 0.68),
    )
    painter.drawLine(
        QPointF(center + size * 0.22, size * 0.47),
        QPointF(center, size * 0.68),
    )
    painter.drawLine(QPointF(size * 0.22, size * 0.86), QPointF(size * 0.78, size * 0.86))


def _draw_folder(painter: QPainter, size: int, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.5, size / 11))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(
        [
            QPointF(size * 0.12, size * 0.80),
            QPointF(size * 0.12, size * 0.28),
            QPointF(size * 0.42, size * 0.28),
            QPointF(size * 0.52, size * 0.40),
            QPointF(size * 0.88, size * 0.40),
            QPointF(size * 0.88, size * 0.80),
            QPointF(size * 0.12, size * 0.80),
        ]
    )


def make_icon(name: str, color: str = TEXT, size: int = 20) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        if name == "download":
            _draw_download(painter, size, color)
        elif name == "folder":
            _draw_folder(painter, size, color)
    finally:
        painter.end()
    return QIcon(pixmap)


class VidGrabComboBox(QComboBox):
    """QComboBox с тонкой стрелкой в стиле тёмной темы."""

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(MUTED))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        center_x = self.width() - 20
        center_y = self.height() / 2 - 2
        painter.drawLine(QPointF(center_x - 4, center_y), QPointF(center_x, center_y + 4))
        painter.drawLine(QPointF(center_x, center_y + 4), QPointF(center_x + 4, center_y))
        painter.end()


def make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setBrush(QColor("#ffffff"))
    painter.drawPolygon(
        [QPointF(26, 20), QPointF(26, 44), QPointF(46, 32)]
    )
    painter.end()
    return QIcon(pixmap)


def apply_theme(app: QApplication | None = None) -> None:
    application = app or QApplication.instance()
    if application is None:
        return
    if application.property("vidgrabThemeApplied"):
        return
    application.setStyle("Fusion")
    application.setPalette(dark_palette())
    application.setStyleSheet(STYLE)
    application.setProperty("vidgrabThemeApplied", True)


def enable_dark_title_bar(window) -> None:
    """Тёмный заголовок окна в Windows 10/11 (если поддерживается)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
            if result == 0:
                return
    except Exception:  # noqa: BLE001 - оформление не должно ломать запуск
        return
