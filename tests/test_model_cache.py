"""Tests for model cache helper (B-004)."""

from core import model_cache


def test_ensure_cached_skips_download_when_present(monkeypatch):
    calls: list[str] = []

    def fake_download(size, local_files_only=False, **kw):
        calls.append(f"{size}:{local_files_only}")
        return "/cache/model"

    import faster_whisper.utils as utils

    monkeypatch.setattr(utils, "download_model", fake_download)
    model_cache.ensure_model_cached("tiny", lambda m: None)
    assert calls == ["tiny:True"]


def test_ensure_cached_downloads_when_missing(monkeypatch):
    def fake_download(size, local_files_only=False, **kw):
        if local_files_only:
            raise FileNotFoundError("missing")
        return "/cache/model"

    import faster_whisper.utils as utils

    monkeypatch.setattr(utils, "download_model", fake_download)
    logs: list[str] = []
    model_cache.ensure_model_cached("tiny", logs.append)
    assert any("First run" in line for line in logs)
