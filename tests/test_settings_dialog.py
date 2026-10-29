from vidgrab import strings
from vidgrab.settings import Settings
from vidgrab.settings_dialog import SettingsDialog


def test_dialog_loads_current_values(qapp):
    settings = Settings(
        cookies_from_browser="edge",
        cookies_file="",
        youtube_client="web",
    )
    dialog = SettingsDialog(settings)
    assert dialog.cookies_combo.currentData() == "edge"
    assert dialog.client_combo.currentData() == "web"
    assert not dialog.file_edit.isEnabled()
    dialog.close()


def test_dialog_saves_browser(qapp):
    settings = Settings(cookies_file="C:/old/cookies.txt")
    dialog = SettingsDialog(settings)
    dialog.cookies_combo.setCurrentIndex(dialog.cookies_combo.findData("firefox"))
    dialog._on_save()
    assert settings.cookies_from_browser == "firefox"
    assert settings.cookies_file == ""
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog.close()


def test_dialog_saves_cookie_file(qapp, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    settings = Settings()
    dialog = SettingsDialog(settings)
    dialog.cookies_combo.setCurrentIndex(dialog.cookies_combo.findData("file"))
    dialog.file_edit.setText(str(cookies))
    dialog._on_save()
    assert settings.cookies_from_browser == ""
    assert settings.cookies_file == str(cookies)
    dialog.close()


def test_dialog_rejects_missing_cookie_file(qapp, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "vidgrab.settings_dialog.QMessageBox.warning",
        staticmethod(lambda *a, **k: warnings.append(a[2] if len(a) > 2 else "")),
    )
    settings = Settings()
    dialog = SettingsDialog(settings)
    dialog.cookies_combo.setCurrentIndex(dialog.cookies_combo.findData("file"))
    dialog.file_edit.setText(str(tmp_path / "нет-такого.txt"))
    dialog._on_save()
    assert warnings
    assert settings.cookies_from_browser == ""
    assert settings.cookies_file == ""
    dialog.close()


def test_dialog_rejects_empty_cookie_file(qapp, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "vidgrab.settings_dialog.QMessageBox.warning",
        staticmethod(lambda *a, **k: warnings.append(a[2] if len(a) > 2 else "")),
    )
    settings = Settings()
    dialog = SettingsDialog(settings)
    dialog.cookies_combo.setCurrentIndex(dialog.cookies_combo.findData("file"))
    dialog._on_save()
    assert warnings == [strings.SETTINGS_COOKIES_FILE_EMPTY]
    dialog.close()


def test_dialog_clears_cookies(qapp):
    settings = Settings(cookies_from_browser="chrome", cookies_file="C:/x/cookies.txt")
    dialog = SettingsDialog(settings)
    dialog.cookies_combo.setCurrentIndex(0)
    dialog._on_save()
    assert settings.cookies_from_browser == ""
    assert settings.cookies_file == ""
    dialog.close()
