"""Qt tests for DictationInboxDialog (B-021 / widget coverage)."""

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

import rctrl_controller as c
import rctrl_inbox
from tests.test_controller import FakeEngine, FakeRecorder, FakeSignals, InlineThread
from ui.i18n import translate


@pytest.fixture
def inbox_controller(monkeypatch):
    monkeypatch.setattr(c, "Recorder", FakeRecorder)
    monkeypatch.setattr(c, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(c.threading, "Thread", InlineThread)
    monkeypatch.setattr(c, "save_config", lambda cfg: None)
    monkeypatch.setattr(c, "paste_text", lambda text: True)
    monkeypatch.setattr(c, "load_items", lambda limit: ["bir", "iki"])
    monkeypatch.setattr(c, "save_items", lambda items: None)
    monkeypatch.setattr(c, "clear_storage", lambda: None)
    monkeypatch.setattr(c, "copy_to_clipboard", lambda text: None)

    signals = FakeSignals()
    config = {"ui_language": "tr", "language": "tr", "model": "tiny", "device": "cpu", "compute": "int8"}
    engine = FakeEngine(model_size="tiny", device="cpu", compute="int8")
    engine.ready = True
    return c.DictationController(config, signals, engine=engine)


def test_inbox_dialog_lists_history(qapp, inbox_controller):
    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, lambda k: k
    )
    assert dlg.list.count() == 2
    from PyQt6.QtCore import Qt

    first = dlg.list.item(0).data(Qt.ItemDataRole.UserRole)
    assert first == "bir"


def test_inbox_delete_refreshes_list(qapp, inbox_controller, monkeypatch):
    monkeypatch.setattr(rctrl_inbox, "paste_text", lambda t: True)
    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, lambda k: k
    )
    dlg._delete("bir")
    assert dlg.list.count() == 1


def test_inbox_show_event_acks_config(qapp, inbox_controller, monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(rctrl_inbox, "save_config", lambda cfg: saved.append(dict(cfg)))
    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, lambda k: k
    )
    dlg.show()
    QApplication.processEvents()
    assert inbox_controller.config.get("inbox_ack_len") == 2
    assert saved


def test_inbox_copy_all_joins_history(qapp, inbox_controller, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(rctrl_inbox, "copy_to_clipboard", lambda t: copied.append(t))
    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, lambda k: k
    )
    copied.clear()
    dlg._copy_all()
    assert copied == ["bir\niki"]
    assert dlg.hint.text() == "inbox_copied_all"


def test_inbox_copy_all_turkish_feedback(qapp, inbox_controller, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(rctrl_inbox, "copy_to_clipboard", lambda t: copied.append(t))
    inbox_controller.config["ui_language"] = "tr"

    def tr(key: str) -> str:
        return translate("tr", key)

    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, tr
    )
    copied.clear()
    dlg._copy_all()
    assert copied == ["bir\niki"]
    assert dlg.hint.text() == "Tümünü kopyaladı"


def test_inbox_selecting_row_copies_to_clipboard(qapp, inbox_controller, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(rctrl_inbox, "copy_to_clipboard", lambda t: copied.append(t))
    parent = QWidget()
    dlg = rctrl_inbox.DictationInboxDialog(
        parent, inbox_controller, inbox_controller.config, lambda k: k
    )
    assert copied == ["bir"]
    dlg.list.setCurrentRow(1)
    assert copied[-1] == "iki"
