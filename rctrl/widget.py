#!/usr/bin/env python3
"""R-Ctrl — Whisperer: floating desktop widget (Right Ctrl hotkey, local Whisper)."""

import os
import sys
import tempfile
import threading
import time
from contextlib import suppress
from enum import Enum, auto
from pathlib import Path
from typing import Protocol

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QLockFile, QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QSystemTrayIcon,
    QWidget,
)

from core.autostart import default_launch_command
from core.autostart import is_enabled as autostart_enabled
from core.autostart import set_enabled as set_autostart
from core.config import save_config
from core.engine import TranscriptionEngine
from core.inbox_ui import ack_inbox, inbox_unread_count
from core.inject import copy_to_clipboard, paste_text

# Re-export for tests and external imports
from rctrl.controller import DictationController, State  # noqa: F401
from rctrl.inbox import DictationInboxDialog
from ui.brand import ENGINE_LINE, HOTKEY_LINE, PRODUCT_DISPLAY, PRODUCT_NAME
from ui.i18n import translate

HISTORY_MENU_LIMIT = 10

# A press shorter than this switches to hands-free toggle mode instead of
# push-to-talk.
TOGGLE_THRESHOLD_SEC = 0.35

# Pointer travel (Manhattan) above which a left-press counts as a drag.
DRAG_THRESHOLD_PX = 5

VISUALIZER_FPS_MS = 33

# Single global hotkey hook — never call keyboard.unhook_all() (breaks other apps).
_hotkey_hook_installed = False
_hotkey_widget: "RCtrlWidget | None" = None

# Capsule chrome — status emoji and level meter share one vertical band.
_STATUS_ICON_PX = 22
_VISUALIZER_W = 28
_VISUALIZER_H = 22
_CAPSULE_MARGIN_H = 14
_CAPSULE_MARGIN_V = 8
_CAPSULE_LAYOUT_SPACING = 8
# Transparent window margin — room for drop shadow (blur 24 + offset 4).
_CAPSULE_SHADOW_PAD = 24
_CAPSULE_MIN_HEIGHT = 40
# Width is sized for the idle capsule (Ready / Listening / …), not long flash lines.
_CAPSULE_WIDTH_KEYS = ("ready", "loading_model", "listening", "transcribing")


def _capsule_dimensions(label_font: QFont) -> tuple[int, int, int]:
    """Return (capsule_w, capsule_h, label_text_w) from font metrics."""
    fm = QFontMetrics(label_font)
    label_w = max(
        fm.horizontalAdvance(translate(lang, key))
        for lang in ("tr", "en")
        for key in _CAPSULE_WIDTH_KEYS
    )
    inner_h = max(_VISUALIZER_H, fm.height())
    capsule_h = max(_CAPSULE_MIN_HEIGHT, inner_h + 2 * _CAPSULE_MARGIN_V)
    status_w = _STATUS_ICON_PX + 6
    chrome = (
        2 * _CAPSULE_MARGIN_H
        + status_w
        + _CAPSULE_LAYOUT_SPACING
        + _VISUALIZER_W
        + _CAPSULE_LAYOUT_SPACING
    )
    capsule_w = chrome + label_w
    return capsule_w, capsule_h, label_w


def configure_stdio_utf8() -> None:
    """Windows consoles often default to cp1252; log lines use emoji and Turkish."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")


def _log(msg: str) -> None:
    line = f"[rctrl-widget] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


class AudioSignals(QObject):
    state_changed = pyqtSignal(str, str)
    audio_level = pyqtSignal(float)
    model_ready = pyqtSignal(bool, str)


# Windows queries 16px (and 32px on high-DPI) for the tray. Alpha holes in
# that pixmap plus setContextMenu() on Win11 make Explorer's hover flyout crash.
_TRAY_ICON_SIZES = (16, 32, 64)

# Background + microphone accent — aligned with capsule `_update_style` palette.
_TRAY_ICON_PALETTE: dict[str, tuple[str, str]] = {
    "idle": ("#1e293b", "#3b82f6"),
    "loading": ("#1e293b", "#3b82f6"),
    "recording": ("#271216", "#ef4444"),
    "processing": ("#251d10", "#f59e0b"),
    "success": ("#0f2316", "#22c55e"),
    "paste_failed": ("#251d10", "#f59e0b"),
    "error": ("#271216", "#dc2626"),
}


class TrayAction(Enum):
    NONE = auto()
    SHOW = auto()
    TOGGLE = auto()
    MENU = auto()


def tray_activation_action(reason: QSystemTrayIcon.ActivationReason) -> TrayAction:
    """Map shell activation to what we do — never toggle on Trigger (Win11 hover)."""
    if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
        return TrayAction.TOGGLE
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
        return TrayAction.SHOW
    if reason == QSystemTrayIcon.ActivationReason.Context:
        return TrayAction.MENU
    return TrayAction.NONE


class TrayActivationTarget(Protocol):
    def isVisible(self) -> bool: ...
    def show(self) -> None: ...
    def activateWindow(self) -> None: ...
    def toggle_visibility(self) -> None: ...
    def show_tray_menu(self) -> None: ...


def apply_tray_activation(
    widget: TrayActivationTarget, reason: QSystemTrayIcon.ActivationReason
) -> None:
    action = tray_activation_action(reason)
    if action is TrayAction.TOGGLE:
        widget.toggle_visibility()
    elif action is TrayAction.SHOW:
        if not widget.isVisible():
            widget.show()
            widget.activateWindow()
    elif action is TrayAction.MENU:
        widget.show_tray_menu()


def _paint_tray_pixmap(size: int, *, bg: str = "#1e293b", accent: str = "#3b82f6") -> QPixmap:
    """Paint one fully-opaque microphone pixmap at `size`."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(bg))
    painter = QPainter(pixmap)
    if not painter.isActive():
        return pixmap
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 64.0
    mic = QColor(accent)
    painter.setBrush(QBrush(mic))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(int(20 * scale), int(10 * scale), int(24 * scale), int(28 * scale), 8 * scale, 8 * scale)
    painter.setPen(QPen(mic, max(1, int(4 * scale))))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(int(12 * scale), int(22 * scale), int(40 * scale), int(28 * scale), 0, -180 * 16)
    mid = size // 2
    painter.drawLine(mid, int(50 * scale), mid, int(56 * scale))
    painter.drawLine(int(22 * scale), int(56 * scale), int(42 * scale), int(56 * scale))
    painter.end()
    return pixmap


def tray_icon_for_state(state: str) -> QIcon:
    """Tray microphone colours follow widget state (idle blue, recording red, …)."""
    bg, accent = _TRAY_ICON_PALETTE.get(state, _TRAY_ICON_PALETTE["idle"])
    icon = QIcon()
    for tray_size in _TRAY_ICON_SIZES:
        icon.addPixmap(_paint_tray_pixmap(tray_size, bg=bg, accent=accent))
    return icon


def _create_tray_icon() -> QIcon:
    """Default idle tray icon."""
    return tray_icon_for_state("idle")


def _ensure_hotkey_hook() -> None:
    """Register one process-wide hook; R-Ctrl is single-instance."""
    global _hotkey_hook_installed
    if _hotkey_hook_installed:
        return
    import keyboard

    def _on_key_event(e):
        widget = _hotkey_widget
        if widget is not None:
            widget._dispatch_hotkey(e)

    keyboard.hook(_on_key_event, suppress=False)
    _hotkey_hook_installed = True


class AudioVisualizer(QWidget):
    """Four-bar level meter. Repaints only while audio is actually flowing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_VISUALIZER_W, _VISUALIZER_H)
        self.level = 0.0
        self.active = False
        self._bar_count = 4

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

    def set_level(self, level: float, active: bool) -> None:
        self.level = level
        if active == self.active:
            return
        self.active = active
        # Idling at 30 fps forever kept the CPU awake for no visible change.
        if active:
            self._timer.start(VISUALIZER_FPS_MS)
        else:
            self._timer.stop()
            self.update()  # one final repaint to draw the bars at rest

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        bar_w, gap = 3, 3
        total_w = self._bar_count * bar_w + (self._bar_count - 1) * gap
        start_x = (self.width() - total_w) // 2

        t = time.time()
        for i in range(self._bar_count):
            if self.active:
                jitter = (np.sin(t * 14 + i * 1.8) + 1) * 0.25
                bar_h = max(4, min(h, int(h * (self.level * 0.65 + jitter))))
                color = QColor("#ef4444")
            else:
                bar_h = 5
                color = QColor("#71717a")

            x = start_x + i * (bar_w + gap)
            y = (h - bar_h) // 2
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 1.5, 1.5)


class RCtrlWidget(QWidget):
    def __init__(self, config: dict, controller: DictationController, signals: AudioSignals):
        super().__init__()
        self.config = config
        self.controller = controller
        self.signals = signals
        self.tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None

        self.drag_pos = QPoint()
        self.press_pos = QPoint()
        self.is_dragging = False
        self.state = "loading"
        self._key_down_time = 0.0
        self._is_toggle_mode = False
        self._input_devices: list[tuple[int, str]] = []
        self._inbox_dialog: DictationInboxDialog | None = None

        self._init_ui()
        self._connect_signals()
        self._setup_hotkey()
        self._refresh_input_devices_async()

    def t(self, key: str) -> str:
        return translate(self.config.get("ui_language", "tr"), key)

    def _apply_status_icon_style(self, *, mic: bool = False) -> None:
        size = "21px" if mic else "15px"
        color = "#3b82f6" if mic else "#f4f4f5"
        self.status_dot.setStyleSheet(
            f"font-size: {size}; color: {color}; background: transparent; border: none;"
        )

    # --- UI construction ---------------------------------------------------

    def _init_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(
            _CAPSULE_SHADOW_PAD,
            _CAPSULE_SHADOW_PAD,
            _CAPSULE_SHADOW_PAD,
            _CAPSULE_SHADOW_PAD,
        )
        root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.capsule = QFrame(self)
        self.capsule.setObjectName("Capsule")
        self.capsule.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        capsule_layout = QHBoxLayout(self.capsule)
        capsule_layout.setContentsMargins(
            _CAPSULE_MARGIN_H, _CAPSULE_MARGIN_V, _CAPSULE_MARGIN_H, _CAPSULE_MARGIN_V
        )
        capsule_layout.setSpacing(_CAPSULE_LAYOUT_SPACING)
        capsule_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.status_dot = QLabel("🎙", self.capsule)
        self.status_dot.setFixedSize(_STATUS_ICON_PX + 6, _VISUALIZER_H)
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_status_icon_style(mic=True)

        self.visualizer = AudioVisualizer(self.capsule)

        self.label = QLabel(self.t("loading_model"), self.capsule)
        self.label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.label.setStyleSheet("color: #f4f4f5; background: transparent; border: none;")

        cap_w, cap_h, label_w = _capsule_dimensions(self.label.font())
        self._label_elide_px = label_w
        self.label.setFixedWidth(label_w)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.capsule.setFixedSize(cap_w, cap_h)
        pad = _CAPSULE_SHADOW_PAD
        self.setFixedSize(cap_w + 2 * pad, cap_h + 2 * pad)

        align = Qt.AlignmentFlag.AlignVCenter
        capsule_layout.addWidget(self.status_dot, 0, align)
        capsule_layout.addWidget(self.visualizer, 0, align)
        capsule_layout.addWidget(self.label, 0, align)
        root_layout.addWidget(self.capsule, 0, Qt.AlignmentFlag.AlignCenter)

        shadow = QGraphicsDropShadowEffect(self.capsule)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 4)
        self.capsule.setGraphicsEffect(shadow)

        self._update_style()
        self._center_on_top_screen()

    def _center_on_top_screen(self) -> None:
        primary = QApplication.primaryScreen()
        if primary is None:
            return
        geometry = primary.geometry()
        self.move((geometry.width() - self.width()) // 2, 35)

    def _set_status_label(self, text: str) -> None:
        """Keep capsule width fixed — truncate with ellipsis when text is long."""
        fm = QFontMetrics(self.label.font())
        self.label.setText(
            fm.elidedText(text, Qt.TextElideMode.ElideRight, self._label_elide_px)
        )

    def _update_style(self) -> None:
        palette = {
            "recording": ("#271216", "#ef4444"),
            "processing": ("#251d10", "#f59e0b"),
            "success": ("#0f2316", "#22c55e"),
            "paste_failed": ("#251d10", "#f59e0b"),
            "error": ("#271216", "#dc2626"),
        }
        bg, border = palette.get(self.state, ("#18181b", "#3f3f46"))
        radius = max(16, capsule_h // 2) if (capsule_h := self.capsule.height()) > 0 else 20
        self.capsule.setStyleSheet(f"""
            #Capsule {{
                background-color: {bg};
                border: 1.5px solid {border};
                border-radius: {radius}px;
            }}
        """)

    def _connect_signals(self) -> None:
        self.signals.state_changed.connect(self._on_state_changed)
        self.signals.audio_level.connect(self._on_audio_level)
        self.signals.model_ready.connect(self._on_model_ready)

    # --- hotkey ------------------------------------------------------------

    def _dispatch_hotkey(self, e) -> None:
        target_hotkey = self.config.get("hotkey", "right ctrl").lower().strip()
        if not e.name or e.name.lower().strip() != target_hotkey:
            return

        if e.event_type == 'down':
            if self.controller.recording:
                if self._is_toggle_mode:
                    self._is_toggle_mode = False
                    self.controller.stop_recording()
                return
            if not self.controller.busy and self.state != "loading":
                self._key_down_time = time.time()
                self._is_toggle_mode = False
                self.controller.start_recording()

        elif e.event_type == 'up':
            if self.controller.recording:
                if time.time() - self._key_down_time <= TOGGLE_THRESHOLD_SEC:
                    self._is_toggle_mode = True
                else:
                    self._is_toggle_mode = False
                    self.controller.stop_recording()

    def _setup_hotkey(self) -> None:
        global _hotkey_widget
        _hotkey_widget = self
        try:
            _ensure_hotkey_hook()
        except Exception as e:
            _log(f"Hotkey hook error: {e}")

    # --- signal handlers ---------------------------------------------------

    def _on_model_ready(self, ok: bool, info: str) -> None:
        if ok:
            maybe_install_tray(self)
            self.state = "idle"
            self._set_status_label(self.t("ready"))
            self.status_dot.setText("🎙")
            self._apply_status_icon_style(mic=True)
        else:
            self.state = "error"
            self._set_status_label(self.t("load_failed"))
        self._update_style()
        self._sync_tray_icon()

    def _on_audio_level(self, level: float) -> None:
        if self.state == "recording":
            self.visualizer.set_level(level, active=True)

    def _on_state_changed(self, state: str, text: str) -> None:
        self.state = state
        self._update_style()
        self._sync_tray_icon()

        if state == "recording":
            self._set_status_label(self.t("listening"))
            self.status_dot.setText("🔴")
            self._apply_status_icon_style(mic=False)
            self.visualizer.set_level(0.2, active=True)
        elif state == "processing":
            self._set_status_label(self.t("transcribing"))
            self.status_dot.setText("⏳")
            self._apply_status_icon_style(mic=False)
            self.visualizer.set_level(0.0, active=False)
        elif state == "success":
            self._set_status_label(f'✓ {self.t("paste_success_hint")} · "{text}"')
            self.status_dot.setText("✨")
            self._apply_status_icon_style(mic=False)
            self.visualizer.set_level(0.0, active=False)
            QTimer.singleShot(2200, self._reset_to_idle)
        elif state == "paste_failed":
            self._set_status_label(f'{self.t("paste_failed")} · "{text}"')
            self.status_dot.setText("📋")
            self._apply_status_icon_style(mic=False)
            self.visualizer.set_level(0.0, active=False)
            QTimer.singleShot(3500, self._reset_to_idle)
        elif state == "error":
            _log(f"UI error state: {text}")
            self._set_status_label(text)
            self.status_dot.setText("⚠")
            self._apply_status_icon_style(mic=False)
            self.visualizer.set_level(0.0, active=False)
            QTimer.singleShot(2500, self._reset_to_idle)
        elif state == "idle":
            self._reset_to_idle()

    def _reset_to_idle(self) -> None:
        if self.state == "recording" or self.controller.busy:
            return
        self.state = "idle"
        self._set_status_label(self.t("ready"))
        self.status_dot.setText("🎙")
        self._apply_status_icon_style(mic=True)
        self.visualizer.set_level(0.0, active=False)
        self._update_style()
        self._sync_tray_icon()

    # --- mouse -------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_pos = event.globalPosition().toPoint()
            self.drag_pos = self.press_pos - self.frameGeometry().topLeft()
            self.is_dragging = False

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = (event.globalPosition().toPoint() - self.press_pos).manhattanLength()
            if delta > DRAG_THRESHOLD_PX or self.is_dragging:
                self.is_dragging = True
                self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.is_dragging:
            if self.state == "idle":
                self.controller.start_recording()
            elif self.state == "recording":
                self.controller.stop_recording()
        self.is_dragging = False

    # --- input devices -----------------------------------------------------

    def _refresh_input_devices_async(self) -> None:
        """Enumerate microphones off the UI thread.

        `sd.query_devices()` is a blocking OS call that can take 10-100 ms, so
        doing it inline made every right-click feel sluggish.
        """
        def _work():
            devices = []
            try:
                seen = set()
                for idx, d in enumerate(sd.query_devices()):
                    if d['max_input_channels'] <= 0:
                        continue
                    name = d['name'].strip()
                    if len(name) > 2 and name not in seen:
                        seen.add(name)
                        devices.append((idx, name))
            except Exception as e:
                _log(f"Could not enumerate input devices: {e}")
            self._input_devices = devices

        threading.Thread(target=_work, daemon=True).start()

    # --- context menu ------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        self.controller.reload_history_from_disk()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121215;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 6px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            QMenu::item { padding: 7px 24px 7px 14px; border-radius: 6px; margin: 1px 0px; }
            QMenu::item:selected { background-color: #2563eb; color: #ffffff; }
            QMenu::item:disabled { color: #52525b; }
            QMenu::separator { height: 1px; background-color: #27272a; margin: 5px 6px; }
        """)

        self._build_inbox_action(menu)
        self._build_history_menu(menu)
        menu.addSeparator()
        self._build_ui_language_menu(menu)
        self._build_voice_language_menu(menu)
        self._build_model_menu(menu)
        self._build_hotkey_menu(menu)
        self._build_mic_menu(menu)
        self._build_autostart_menu(menu)
        menu.addSeparator()

        menu.addAction(self.t("reset_pos")).triggered.connect(self._center_on_top_screen)
        if self.tray is not None:
            menu.addAction(self.t("minimize_to_tray")).triggered.connect(self._minimize_to_tray)
        menu.addAction(self.t("exit")).triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def _build_inbox_action(self, menu: QMenu) -> None:
        unread = inbox_unread_count(self.config, len(self.controller.history))
        label = self.t("inbox_menu")
        if unread:
            label = f"{label} ({unread})"
        menu.addAction(label).triggered.connect(self._open_inbox)

    def _open_inbox(self) -> None:
        self.controller.reload_history_from_disk()
        if self._inbox_dialog is None:
            self._inbox_dialog = DictationInboxDialog(self, self.controller, self.config, self.t)
        self._inbox_dialog._reload()
        self._inbox_dialog.show()
        self._inbox_dialog.raise_()
        self._inbox_dialog.activateWindow()
        ack_inbox(self.config, len(self.controller.history))
        save_config(self.config)

    def _build_autostart_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("autostart_menu"))
        on = QAction(self.t("autostart_on"), self)
        off = QAction(self.t("autostart_off"), self)
        on.setCheckable(True)
        off.setCheckable(True)
        enabled = autostart_enabled()
        on.setChecked(enabled)
        off.setChecked(not enabled)
        on.triggered.connect(lambda: self._set_autostart(True))
        off.triggered.connect(lambda: self._set_autostart(False))
        sub.addAction(on)
        sub.addAction(off)

    def _set_autostart(self, enabled: bool) -> None:
        try:
            cmd = default_launch_command()
            set_autostart(enabled, cmd if enabled else None)
            state = self.t("autostart_on") if enabled else self.t("autostart_off")
            self._flash(f"{self.t('autostart_menu')}: {state}")
        except Exception as e:
            _log(f"Autostart error: {e}")
            self._flash(self.t("mic_error"))

    def _build_history_menu(self, menu: QMenu) -> None:
        history_menu = menu.addMenu(self.t("history_menu"))
        if not self.controller.history:
            history_menu.addAction(self.t("history_empty")).setEnabled(False)
            return
        for item in self.controller.history[:HISTORY_MENU_LIMIT]:
            preview = item[:36] + ("..." if len(item) > 36 else "")
            act = history_menu.addAction(f'"{preview}"')
            act.triggered.connect(lambda checked, txt=item: self._paste_history_item(txt))
        history_menu.addSeparator()
        history_menu.addAction(self.t("clear_history")).triggered.connect(self._clear_history)

    def _build_ui_language_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("ui_lang_menu"))
        current = self.config.get("ui_language", "tr")
        for name, code in [("Türkçe", "tr"), ("English", "en")]:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(current == code)
            act.triggered.connect(lambda checked, c=code: self._change_ui_language(c))
            sub.addAction(act)

    def _build_voice_language_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("voice_lang_menu"))
        for name, code in [(self.t("lang_tr"), "tr"), (self.t("lang_en"), "en"),
                           (self.t("lang_auto"), None)]:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(self.controller.language == code)
            act.triggered.connect(lambda checked, c=code: self._change_voice_language(c))
            sub.addAction(act)

    def _build_model_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("model_menu"))
        for name in ["large-v3", "medium", "small", "base"]:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(self.controller.model_size == name)
            act.triggered.connect(lambda checked, m=name: self._change_model(m))
            sub.addAction(act)

    def _build_hotkey_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("hotkey_menu"))
        current = self.config.get("hotkey", "right ctrl").lower()
        for name, key in [("Right Ctrl", "right ctrl"), ("Right Alt / AltGr", "right alt"),
                          ("F12 Key", "f12"), ("Caps Lock", "caps lock")]:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(current == key)
            act.triggered.connect(lambda checked, k=key: self._change_hotkey(k))
            sub.addAction(act)

    def _build_mic_menu(self, menu: QMenu) -> None:
        sub = menu.addMenu(self.t("mic_menu"))
        default_act = QAction(self.t("default_mic"), self)
        default_act.setCheckable(True)
        default_act.setChecked(self.controller.input_device is None)
        default_act.triggered.connect(lambda: self._change_input_device(None))
        sub.addAction(default_act)
        sub.addSeparator()

        for idx, name in self._input_devices:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(self.controller.input_device == idx)
            act.triggered.connect(lambda checked, i=idx: self._change_input_device(i))
            sub.addAction(act)

        sub.addSeparator()
        sub.addAction(self.t("refresh_mics")).triggered.connect(self._refresh_input_devices_async)

    # --- menu actions ------------------------------------------------------

    def _flash(self, message: str, delay_ms: int = 1500) -> None:
        self._set_status_label(message)
        QTimer.singleShot(delay_ms, self._reset_to_idle)

    def _change_ui_language(self, lang_code: str) -> None:
        self.config["ui_language"] = lang_code
        save_config(self.config)
        _log(f"UI language changed: {lang_code}")
        _rebuild_tray_menu(self)
        self._flash(f"{self.t('ui_lang_changed')}: {self.t('lang_' + lang_code)}")

    def _change_voice_language(self, lang_code: str | None) -> None:
        self.controller.language = lang_code
        self.config["language"] = lang_code
        save_config(self.config)
        display = self.t("lang_" + lang_code) if lang_code else self.t("lang_auto")
        _log(f"Voice language set to: {lang_code or 'auto'}")
        self._flash(f"{self.t('lang_changed')}: {display}")

    def _change_input_device(self, dev_idx: int | None) -> None:
        self.controller.set_input_device(dev_idx)
        if dev_idx is None:
            name = self.t("default_mic")
        else:
            name = next((n for i, n in self._input_devices if i == dev_idx), str(dev_idx))[:22]
        _log(f"Microphone changed: {name}")
        self._flash(f"{self.t('mic_changed')}: {name}")

    def _change_hotkey(self, key_code: str) -> None:
        self.config["hotkey"] = key_code
        save_config(self.config)
        self._setup_hotkey()
        _log(f"Hotkey updated: {key_code.upper()}")
        self._flash(f"{self.t('key_changed')}: {key_code.upper()}")

    def _change_model(self, model_name: str) -> None:
        if not self.controller.change_model(model_name):
            # Refused because a recording or transcription is still running.
            self._flash(self.t("model_busy"))
            return
        self.state = "loading"
        self._set_status_label(f"{self.t('model_loading')}: {model_name}...")
        self._update_style()

    def _paste_history_item(self, text: str) -> None:
        if paste_text(text):
            self._flash(self.t("paste_success_hint"), 2200)
        else:
            copy_to_clipboard(text)
            self._flash(self.t("paste_failed"), 2800)

    def _copy_history_item(self, text: str) -> None:
        copy_to_clipboard(text)
        self.status_dot.setText("✓")
        _log(f'Copied from history: "{text[:40]}"')
        self._flash(self.t("copied"), 1800)

    def _clear_history(self) -> None:
        self.controller.clear_history()
        self._flash(self.t("history_cleared"))

    # --- tray integration --------------------------------------------------

    def set_tray(self, tray: QSystemTrayIcon) -> None:
        """Attach the system tray icon after construction."""
        self.tray = tray
        self._sync_tray_icon()

    def _sync_tray_icon(self) -> None:
        if self.tray is None:
            return
        self.tray.setIcon(tray_icon_for_state(self.state))
        if self.state == "recording":
            self.tray.setToolTip(f"{PRODUCT_NAME} — " + self.t("listening"))
        elif self.state == "processing":
            self.tray.setToolTip(f"{PRODUCT_NAME} — " + self.t("transcribing"))
        else:
            self.tray.setToolTip(PRODUCT_NAME)

    def _minimize_to_tray(self) -> None:
        """Hide the widget, leaving only the tray icon visible."""
        if self.tray is None or not self.tray.isVisible():
            return
        self.hide()

    def toggle_visibility(self) -> None:
        """Show/hide the widget — called from tray icon activation."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        apply_tray_activation(self, reason)

    def show_tray_menu(self) -> None:
        if self._tray_menu is None:
            return
        self._tray_menu.popup(QCursor.pos())


def _create_tray_menu(widget: RCtrlWidget) -> QMenu:
    """Build the system tray context menu, parented to the widget so it cannot be GC'd."""
    menu = QMenu(widget)
    menu.addAction(widget.t("tray_show")).triggered.connect(widget.show)
    menu.addAction(widget.t("tray_hide")).triggered.connect(widget.hide)
    menu.addSeparator()
    menu.addAction(widget.t("tray_quit")).triggered.connect(QApplication.quit)
    return menu


def _rebuild_tray_menu(widget: RCtrlWidget) -> None:
    """Recreate the tray menu so its labels match the current UI language."""
    widget._tray_menu = _create_tray_menu(widget)


def install_tray(app: QApplication, widget: RCtrlWidget) -> QSystemTrayIcon | None:
    """Attach a tray icon if the shell actually has a tray. Returns None on skip.

    `setQuitOnLastWindowClosed(False)` is applied only after the icon is
    confirmed visible — otherwise hiding the widget would leave a zombie
    process with no UI.
    """
    if not QSystemTrayIcon.isSystemTrayAvailable():
        _log("System tray is not available; running without a tray icon")
        return None

    tray = QSystemTrayIcon(_create_tray_icon(), widget)
    tray.setToolTip(PRODUCT_NAME)
    widget._tray_menu = _create_tray_menu(widget)
    tray.activated.connect(widget._on_tray_activated)
    tray.show()

    if not tray.isVisible():
        _log("System tray icon failed to show; running without a tray icon")
        tray.hide()
        tray.deleteLater()
        return None

    app.setQuitOnLastWindowClosed(False)
    widget.set_tray(tray)
    return tray


def tray_disabled() -> bool:
    return os.environ.get("RCTRL_NO_TRAY", "").strip().lower() in ("1", "true", "yes")


_instance_lock: QLockFile | None = None


def acquire_single_instance() -> bool:
    """Return False if another widget process already holds the lock."""
    global _instance_lock
    path = Path(tempfile.gettempdir()) / "rctrl-widget.lock"
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        return False
    _instance_lock = lock
    return True


def maybe_install_tray(widget: RCtrlWidget) -> QSystemTrayIcon | None:
    """Install the tray icon after the model is ready — same order as pre-B-002 startup.

    Initializing the shell tray before CUDA/Whisper load correlated with the
    process dying at 'Loading model...' and left the UI stuck busy (no hotkey).
    """
    if widget.tray is not None:
        return widget.tray
    if tray_disabled():
        _log("System tray disabled (RCTRL_NO_TRAY)")
        return None
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return None
    return install_tray(app, widget)


def run_app(
    config: dict,
    hw: dict,
    engine: TranscriptionEngine | None = None,
) -> None:
    """Start the Qt UI. Pass a pre-loaded `engine` when CUDA was initialized before PyQt."""
    configure_stdio_utf8()
    if not acquire_single_instance():
        print("[rctrl-widget] Zaten çalışıyor (tek örnek). / Already running.", flush=True)
        sys.exit(0)
    print()
    print("=" * 64)
    print(f"  {PRODUCT_DISPLAY}")
    print(f"  {ENGINE_LINE} on-device · {HOTKEY_LINE} hotkey")
    print("=" * 64)
    print(f"  Detected Hardware : {hw['reason']}")
    print(f"  Active Model      : {config['model']} ({config['device']}/{config['compute']})")
    print(f"  Active Hotkey     : {config['hotkey'].upper()} (push-to-talk / tap to toggle)")
    print("  Mouse Usage       : Click widget -> Speak -> Click to finish")
    print("  Settings & History: Right click the widget")
    print("  System Tray       : Double-click to show/hide, right-click for menu")
    print("=" * 64)
    print()

    app = QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationDisplayName(PRODUCT_NAME)

    signals = AudioSignals()
    controller = DictationController(config, signals, engine=engine)
    widget = RCtrlWidget(config, controller, signals)

    widget.show()
    widget.raise_()
    controller.load_model_async()
    sys.exit(app.exec())


def main() -> None:
    """Deprecated entry — use ``python -m rctrl.launch`` so Whisper loads before PyQt6."""
    from rctrl.launch import main as launch_main

    launch_main()


if __name__ == '__main__':
    main()
