import json

from vidgrab.main import _json_out


def test_json_out_is_ascii_safe(capsys):
    _json_out({"ok": True, "path": "видео ｜ файл.mp4"})
    output = capsys.readouterr().out
    assert "\\uff5c" in output
    assert json.loads(output)["path"] == "видео ｜ файл.mp4"
