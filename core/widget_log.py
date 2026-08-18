"""File logging when the widget runs without a console (B-023)."""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
    path = Path(base) / "R-Ctrl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return log_dir() / "widget.log"


class _Tee:
    def __init__(self, stream, file):
        self._stream = stream
        self._file = file

    def write(self, data: str) -> int:
        if self._stream is not None:
            with suppress(Exception):
                self._stream.write(data)
        self._file.write(data)
        self._file.flush()
        return len(data)

    def flush(self) -> None:
        if self._stream is not None:
            with suppress(Exception):
                self._stream.flush()
        self._file.flush()


def configure_widget_file_log() -> Path:
    """Mirror stdout/stderr to widget.log (safe under pythonw). Returns log file path."""
    path = log_path()
    handle = open(path, "a", encoding="utf-8", errors="replace")  # noqa: SIM115
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    handle.write(f"\n--- session {stamp} ---\n")
    handle.flush()
    sys.stdout = _Tee(sys.stdout, handle)
    sys.stderr = _Tee(sys.stderr, handle)
    return path


def fatal_widget_startup(message: str, *, ui_language: str = "en", title: str | None = None) -> None:
    """Log, show a Windows error dialog when there is no console, then exit."""
    from ui.i18n import translate

    print(message, flush=True)
    if sys.platform == "win32":
        log_file = log_path()
        lang = ui_language if ui_language in ("tr", "en") else "en"
        body = translate(lang, "startup_fatal_body").format(message=message, log_path=log_file)
        box_title = title or translate(lang, "startup_fatal_title")
        with suppress(Exception):
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, body, box_title, 0x10)
    raise SystemExit(1)
