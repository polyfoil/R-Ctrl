"""Widget-only device sync and startup fatal dialog."""

import json
from unittest.mock import MagicMock

import pytest

from core import config as cfg
from core import widget_log


def test_launch_widget_calls_device_sync(monkeypatch):
    import rctrl.launch as lw

    calls: list[tuple] = []

    def _sync(conf, hw):
        calls.append((conf.copy(), hw))
        conf = dict(conf)
        conf["device"] = "cpu"
        return conf

    monkeypatch.setattr(lw, "load_or_create_config", lambda: ({"model": "small", "ui_language": "en"}, {"reason": "t"}))
    monkeypatch.setattr(lw, "sync_widget_device_with_hardware", _sync)
    monkeypatch.setattr(lw, "configure_widget_file_log", lambda: None)
    monkeypatch.setattr(lw, "TranscriptionEngine", lambda **kw: MagicMock(load=lambda log=None: (True, "ok")))
    monkeypatch.setattr(lw, "fatal_widget_startup", lambda *a, **k: None)

    import rctrl.widget as widget

    monkeypatch.setattr(widget, "run_app", lambda *a, **k: None)
    lw.main()
    assert len(calls) == 1


def test_fatal_widget_startup_exits_and_logs(monkeypatch, capsys):
    monkeypatch.setattr(widget_log.sys, "platform", "linux")
    with pytest.raises(SystemExit) as exc:
        widget_log.fatal_widget_startup("boom", ui_language="en")
    assert exc.value.code == 1
    assert "boom" in capsys.readouterr().out


def test_fatal_widget_startup_uses_turkish_copy(monkeypatch):
    captured: dict = {}

    def _msgbox(_hwnd, body, title, _flags):
        captured["body"] = body
        captured["title"] = title

    import ctypes

    monkeypatch.setattr(widget_log.sys, "platform", "win32")
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", _msgbox)
    with pytest.raises(SystemExit):
        widget_log.fatal_widget_startup("hata", ui_language="tr")
    assert "CUDA Toolkit gerekmez" in captured["body"]
    assert captured["title"]


def test_server_load_does_not_set_gpu_auto_fallback(tmp_path, monkeypatch):
    """rctrl.server uses load_or_create_config only — no widget device sync."""
    from tests.test_config import _fake_probe

    _fake_probe(monkeypatch, cuda_devices=0, vram_mb=12000)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"device": "cuda", "model": "large-v3"}), encoding="utf-8")
    conf, _ = cfg.load_or_create_config(path)
    assert conf["device"] == "cuda"
    assert cfg.GPU_AUTO_FALLBACK_KEY not in conf
