"""Ensure Whisper weights are cached before model construction (B-004)."""

from __future__ import annotations

from collections.abc import Callable


def ensure_model_cached(model_size: str, log: Callable[[str], None]) -> None:
    """Download from Hugging Face Hub when missing; log clearly on first run."""
    try:
        from faster_whisper.utils import download_model
    except Exception as e:
        log(f"Could not import faster_whisper download helper: {e}")
        return

    try:
        download_model(model_size, local_files_only=True)
        return
    except Exception:
        pass

    log(
        f"First run: downloading '{model_size}' from Hugging Face Hub "
        "(up to ~3 GB for large-v3). Progress may appear in the log file."
    )
    download_model(model_size)
