"""Widget inbox menu wiring (unread badge + ack on open)."""

import pytest
from PyQt6.QtWidgets import QMenu

import rctrl.controller as c
import rctrl.inbox
import rctrl.widget as w
from rctrl.widget import AudioSignals
from tests.test_controller import FakeEngine, FakeRecorder, InlineThread


@pytest.fixture
def widget(qapp, monkeypatch):
    monkeypatch.setattr(c, "Recorder", FakeRecorder)
    monkeypatch.setattr(c, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(c.threading, "Thread", InlineThread)
    monkeypatch.setattr(c, "save_config", lambda cfg: None)
    monkeypatch.setattr(c, "load_items", lambda limit: ["alpha", "beta"])
    monkeypatch.setattr(c, "save_items", lambda items: None)
    monkeypatch.setattr(c, "clear_storage", lambda: None)
    monkeypatch.setattr(w, "_ensure_hotkey_hook", lambda: None)

    config = {
        "model": "tiny",
        "device": "cpu",
        "compute": "int8",
        "language": "tr",
        "ui_language": "tr",
        "hotkey": "right ctrl",
        "input_device": None,
        "inbox_ack_len": 0,
    }
    signals = AudioSignals()
    engine = FakeEngine(model_size="tiny", device="cpu", compute="int8")
    engine.ready = True
    controller = c.DictationController(config, signals, engine=engine)
    controller.history = ["alpha", "beta"]
    return w.RCtrlWidget(config, controller, signals)


def test_capsule_size_unchanged_after_long_status(widget):
    w0, h0 = widget.capsule.width(), widget.capsule.height()
    widget._set_status_label("çok uzun bir dikte metni " * 20)
    assert widget.capsule.width() == w0
    assert widget.capsule.height() == h0
    widget._on_state_changed("success", "merhaba dünya " * 30)
    assert widget.capsule.width() == w0


def test_inbox_menu_shows_unread_count(widget):
    menu = QMenu()
    widget._build_inbox_action(menu)
    label = menu.actions()[0].text()
    assert "(2)" in label


def test_open_inbox_acks_history(widget, monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(w, "save_config", lambda cfg: saved.append(dict(cfg)))
    widget._open_inbox()
    assert widget.config["inbox_ack_len"] == 2
    assert saved
    assert widget._inbox_dialog is not None


def test_open_inbox_reuses_dialog_instance(widget, monkeypatch):
    monkeypatch.setattr(w, "save_config", lambda cfg: None)
    widget._open_inbox()
    first = widget._inbox_dialog
    widget._open_inbox()
    assert widget._inbox_dialog is first


def test_inbox_copy_all_flashes_widget_capsule(widget, monkeypatch):
    monkeypatch.setattr(rctrl.inbox, "copy_to_clipboard", lambda t: None)
    monkeypatch.setattr(w, "save_config", lambda cfg: None)
    widget._open_inbox()
    widget._inbox_dialog._copy_all()
    assert widget.label.text() == "Tümünü kopyaladı"
