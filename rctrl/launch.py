#!/usr/bin/env python3
"""Widget launcher — load faster-whisper before PyQt6.

On Windows, importing PyQt6 before CUDA/ctranslate2 initializes makes
`engine.load()` crash at the "Loading model..." line. The UI looked like a
tray regression, but the root cause is import order. This module loads the
model first, then imports `rctrl.widget` (which pulls in Qt).
"""

import sys
from contextlib import suppress

from core.config import load_or_create_config, sync_widget_device_with_hardware
from core.engine import TranscriptionEngine
from core.widget_log import configure_widget_file_log, fatal_widget_startup


def _log(msg: str) -> None:
    print(f"[rctrl-widget] {msg}", flush=True)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")

    configure_widget_file_log()

    config, hw = load_or_create_config()
    config = sync_widget_device_with_hardware(config, hw)
    engine = TranscriptionEngine(
        model_size=config.get("model", "large-v3"),
        device=config.get("device", "cuda"),
        compute=config.get("compute", "float16"),
        language=config.get("language"),
    )
    _log(
        "First run downloads the speech model from Hugging Face Hub "
        f"({engine.model_size}, up to ~3 GB). No API key for public models."
    )
    _log(
        "Cache folder: %USERPROFILE%\\.cache\\huggingface\\hub "
        "(override with HF_HOME or HUGGINGFACE_HUB_CACHE)."
    )
    _log(f"Loading model: {engine.model_size} ({engine.device}) ...")
    ok, info = engine.load(log=_log)
    if not ok:
        fatal_widget_startup(
            f"Model load error: {info}",
            ui_language=str(config.get("ui_language", "en")),
        )
    _log(f"Model ready: {info}")

    from rctrl import widget

    widget.run_app(config, hw, engine)


if __name__ == "__main__":
    main()
