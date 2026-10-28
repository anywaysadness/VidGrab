import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VIDGRAB_APPDATA", str(ROOT / ".tmp" / "pytest-appdata"))


@pytest.fixture()
def appdata(tmp_path, monkeypatch):
    target = tmp_path / "appdata"
    monkeypatch.setenv("VIDGRAB_APPDATA", str(target))
    return target


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
