"""Dictation inbox dialog (B-021)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import save_config
from core.inbox_ui import ack_inbox
from core.inject import copy_to_clipboard, paste_text
from rctrl.controller import DictationController


class DictationInboxDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        controller: DictationController,
        config: dict,
        translate,
    ):
        super().__init__(parent)
        self.controller = controller
        self.config = config
        self.t = translate
        self.setWindowTitle(self.t("inbox_title"))
        self.setMinimumSize(420, 320)

        layout = QVBoxLayout(self)
        self.hint = QLabel()
        layout.addWidget(self.hint)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_item_selected)
        self.list.itemDoubleClicked.connect(self._copy_item)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        self.copy_btn = QPushButton(self.t("inbox_copy_btn"))
        self.copy_btn.clicked.connect(self._copy_selected)
        copy_all = QPushButton(self.t("inbox_copy_all"))
        copy_all.clicked.connect(self._copy_all)
        close_btn = QPushButton(self.t("inbox_close"))
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(copy_all)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        items = list(self.controller.history)
        if not items:
            self.hint.setText(self.t("inbox_empty"))
            self.list.setEnabled(False)
            self.copy_btn.setEnabled(False)
            return
        self.hint.setText("")
        self.list.setEnabled(True)
        self.copy_btn.setEnabled(True)
        for text in items:
            preview = text if len(text) <= 120 else text[:117] + "..."
            item = QListWidgetItem(preview)
            item.setData(Qt.ItemDataRole.UserRole, text)
            item.setToolTip(text)
            self.list.addItem(item)
        self.list.setCurrentRow(0)

    def _item_text(self, item: QListWidgetItem | None) -> str | None:
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, str) else None

    def _selected_text(self) -> str | None:
        return self._item_text(self.list.currentItem())

    def _show_copied_hint(self, message: str, *, flash_parent: bool = False) -> None:
        self.hint.setText(message)
        if flash_parent:
            parent = self.parent()
            flash = getattr(parent, "_flash", None)
            if callable(flash):
                flash(message, 2200)

    def _copy_text(self, text: str, *, flash_parent: bool = False) -> None:
        copy_to_clipboard(text)
        self._show_copied_hint(self.t("inbox_copied_one"), flash_parent=flash_parent)

    def _on_item_selected(self, current: QListWidgetItem | None, _previous) -> None:
        text = self._item_text(current)
        if text:
            self._copy_text(text)

    def _copy_selected(self) -> None:
        text = self._selected_text()
        if text:
            self._copy_text(text)

    def _copy_item(self, item: QListWidgetItem) -> None:
        text = self._item_text(item)
        if text:
            self._copy_text(text)

    def _copy_all(self) -> None:
        if not self.controller.history:
            return
        lines = [t.strip() for t in self.controller.history if t.strip()]
        combined = "\n".join(lines)
        copy_to_clipboard(combined)
        self._show_copied_hint(self.t("inbox_copied_all"), flash_parent=True)

    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        text = self._item_text(item)
        if text is None:
            return
        menu = QMenu(self)
        menu.addAction(self.t("inbox_paste"), lambda: paste_text(text))
        menu.addAction(self.t("inbox_delete"), lambda: self._delete(text))
        menu.exec(self.list.mapToGlobal(pos))

    def _delete(self, text: str) -> None:
        self.controller.remove_history_item(text)
        self._reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        ack_inbox(self.config, len(self.controller.history))
        save_config(self.config)
