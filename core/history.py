"""Persisted dictation history (B-005 / future Dictation Inbox storage)."""

import json
from pathlib import Path

from core.config import CONFIG_PATH

INBOX_PATH = CONFIG_PATH.parent / "inbox.json"
_SCHEMA_VERSION = 1
INBOX_MAX_ITEMS = 20


def _log(msg: str) -> None:
    print(f"[rctrl-history] {msg}", flush=True)


def _read_all_items(path: Path | None = None) -> list[str]:
    """Load every stored item (newest-first order on disk)."""
    inbox = path if path is not None else INBOX_PATH
    if not inbox.exists():
        return []
    try:
        with open(inbox, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _log(f"Could not read {inbox.name} ({e}) — treating as empty.")
        return []
    if not isinstance(data, dict):
        return []
    raw = data.get("items")
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            stripped = entry.strip()
            if stripped:
                items.append(stripped)
    return items


def load_items(limit: int, path: Path | None = None) -> list[str]:
    """Return up to `limit` newest items from disk, or [] if missing or invalid."""
    if limit <= 0:
        return []
    return _read_all_items(path)[:limit]


def save_items(items: list[str], path: Path | None = None) -> None:
    """Write the full history list (newest first, already capped by caller)."""
    inbox = path if path is not None else INBOX_PATH
    payload = {"version": _SCHEMA_VERSION, "items": items}
    try:
        with open(inbox, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f"Could not save {inbox.name}: {e}")


def clear_storage(path: Path | None = None) -> None:
    """Remove persisted history."""
    inbox = path if path is not None else INBOX_PATH
    try:
        if inbox.exists():
            inbox.unlink()
    except Exception as e:
        _log(f"Could not delete {inbox.name}: {e}")


def append_item(
    text: str,
    limit: int = INBOX_MAX_ITEMS,
    path: Path | None = None,
) -> bool:
    """Prepend text to inbox storage (dedupe, cap). Used by widget and server."""
    item = text.strip()
    if not item:
        return False
    items = _read_all_items(path)
    if item in items:
        items.remove(item)
    items.insert(0, item)
    del items[limit:]
    save_items(items, path=path)
    return True
