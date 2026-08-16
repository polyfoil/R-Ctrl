"""Tests for widget file logging helper."""

from core import widget_log


def test_log_dir_creates_under_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = widget_log.log_dir()
    assert path.is_dir()
    assert path.name == "R-Ctrl"
