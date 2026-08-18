"""Tray-icon lifecycle tests.

Windows 11 sends `Trigger` when Explorer inspects a new tray icon (~1s after
show, and again on hover). Treating that as a visibility toggle hides the
float bar. Binding a QMenu via `setContextMenu` plus an alpha pixmap makes
the hover flyout native-crash.

These tests pin:

1. Trigger shows (never toggles/hides); only DoubleClick toggles.
2. The tray icon's 16px pixmap is fully opaque (no alpha).
3. The context menu is owned by the widget, not installed with setContextMenu.
"""

import gc

import pytest
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QSystemTrayIcon, QWidget

import rctrl.widget as w
from ui.i18n import I18N, translate


class _TrayHost(QWidget):
    """Stand-in for RCtrlWidget — enough surface for tray helpers."""

    def __init__(self):
        super().__init__()
        self.config = {"ui_language": "tr"}
        self.tray: QSystemTrayIcon | None = None
        self._tray_menu = None

    def t(self, key: str) -> str:
        return translate(self.config.get("ui_language", "tr"), key)

    def set_tray(self, tray: QSystemTrayIcon) -> None:
        self.tray = tray

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def show_tray_menu(self) -> None:
        if self._tray_menu is not None:
            self._tray_menu.popup(self.mapToGlobal(self.rect().center()))

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        w.apply_tray_activation(self, reason)


def test_trigger_does_not_toggle_or_hide():
    reason = QSystemTrayIcon.ActivationReason
    assert w.tray_activation_action(reason.Trigger) is w.TrayAction.SHOW
    assert w.tray_activation_action(reason.DoubleClick) is w.TrayAction.TOGGLE
    assert w.tray_activation_action(reason.Context) is w.TrayAction.MENU
    assert w.tray_activation_action(reason.MiddleClick) is w.TrayAction.NONE


def test_apply_tray_trigger_keeps_visible_widget_visible(qapp):
    host = _TrayHost()
    host.show()
    w.apply_tray_activation(host, QSystemTrayIcon.ActivationReason.Trigger)
    assert host.isVisible() is True


def test_tray_menu_is_owned_by_the_widget(qapp):
    host = _TrayHost()
    menu = w._create_tray_menu(host)
    assert menu.parent() is host
    assert len(menu.actions()) >= 3


def test_tray_menu_survives_garbage_collection(qapp):
    host = _TrayHost()
    menu = w._create_tray_menu(host)
    host._tray_menu = menu
    del menu
    gc.collect()
    assert host._tray_menu is not None
    assert host._tray_menu.parent() is host
    assert len(host._tray_menu.actions()) >= 3


def test_tray_icon_16px_is_fully_opaque(qapp):
    icon = w._create_tray_icon()
    assert not icon.isNull()
    widths = {size.width() for size in icon.availableSizes()}
    assert {16, 32}.issubset(widths)
    image = icon.pixmap(16, 16).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for x, y in ((0, 0), (15, 0), (0, 15), (15, 15), (8, 8)):
        assert image.pixelColor(x, y).alpha() == 255, f"alpha hole at {x},{y}"


def test_maybe_install_tray_respects_disable_env(qapp, monkeypatch):
    monkeypatch.setenv("RCTRL_NO_TRAY", "1")
    host = _TrayHost()
    assert w.maybe_install_tray(host) is None
    assert host.tray is None


def test_install_tray_skips_when_unavailable(qapp, monkeypatch):
    monkeypatch.setattr(
        w.QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False)
    )
    qapp.setQuitOnLastWindowClosed(True)
    host = _TrayHost()
    assert w.install_tray(qapp, host) is None
    assert host.tray is None
    assert qapp.quitOnLastWindowClosed() is True


def test_install_tray_does_not_bind_context_menu(qapp):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        pytest.skip("no system tray on this session")
    host = _TrayHost()
    qapp.setQuitOnLastWindowClosed(True)
    tray = w.install_tray(qapp, host)
    try:
        if tray is None:
            pytest.skip("tray icon did not become visible")
        assert host.tray is tray
        assert tray.isVisible()
        assert tray.contextMenu() is None
        assert host._tray_menu is not None
        assert host._tray_menu.parent() is host
        assert qapp.quitOnLastWindowClosed() is False
    finally:
        if tray is not None:
            tray.hide()
        qapp.setQuitOnLastWindowClosed(True)


def test_rebuild_tray_menu_follows_ui_language(qapp):
    host = _TrayHost()
    host.tray = QSystemTrayIcon(w._create_tray_icon(), host)
    w._rebuild_tray_menu(host)
    host.config["ui_language"] = "en"
    w._rebuild_tray_menu(host)
    labels = [act.text() for act in host._tray_menu.actions() if act.text()]
    assert I18N["en"]["tray_show"] in labels
    assert I18N["en"]["tray_quit"] in labels


def test_tray_icon_recording_uses_red_accent(qapp):
    idle = w.tray_icon_for_state("idle")
    recording = w.tray_icon_for_state("recording")
    p_idle = idle.pixmap(16, 16).toImage().pixelColor(8, 12)
    p_rec = recording.pixmap(16, 16).toImage().pixelColor(8, 12)
    assert p_rec.red() > p_idle.red()
    assert p_rec.blue() < p_idle.blue()


def test_acquire_single_instance_succeeds_when_unlocked(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(w.tempfile, "gettempdir", lambda: str(tmp_path))
    w._instance_lock = None
    assert w.acquire_single_instance() is True
