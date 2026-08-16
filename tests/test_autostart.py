"""Tests for Windows autostart helpers."""

import sys
from contextlib import contextmanager

import pytest

from core import autostart


def test_default_launch_command_points_at_bat():
    cmd = autostart.default_launch_command()
    assert "rctrl_widget.bat" in cmd.lower()


class _FakeKey:
    def __init__(self, store: dict | None = None):
        self._store = store if store is not None else {}

    def query(self, name):
        if name not in self._store:
            raise OSError
        return self._store[name]

    def set(self, name, value):
        self._store[name] = value

    def delete(self, name):
        del self._store[name]


def test_is_enabled_reads_registry(monkeypatch):
    store: dict[str, str] = {autostart.VALUE_NAME: "cmd"}
    key = _FakeKey(store)

    @contextmanager
    def _open(_access):
        yield key

    monkeypatch.setattr(autostart, "_open_run_key", _open)
    monkeypatch.setattr(autostart, "_query_value", lambda k, n: (k.query(n), 1))
    assert autostart.is_enabled() is True


def test_autostart_round_trip(monkeypatch):
    store: dict[str, str] = {}
    key = _FakeKey(store)

    @contextmanager
    def _open(_access):
        yield key

    monkeypatch.setattr(autostart, "_open_run_key", _open)
    monkeypatch.setattr(autostart, "_set_value", lambda k, n, v: k.set(n, v))
    monkeypatch.setattr(autostart, "_delete_value", lambda k, n: k.delete(n))
    autostart.set_enabled(True, '"C:\\test\\rctrl_widget.bat"')
    assert store[autostart.VALUE_NAME] == '"C:\\test\\rctrl_widget.bat"'
    autostart.set_enabled(False)
    assert autostart.VALUE_NAME not in store


@pytest.mark.skipif(sys.platform != "win32", reason="win32-only API")
def test_supported_on_windows():
    assert autostart.supported() is True
