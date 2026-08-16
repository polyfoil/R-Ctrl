"""Tests for core.history — persisted dictation inbox storage."""

import json

from core import history


def test_load_returns_empty_when_file_missing(tmp_path):
    path = tmp_path / "inbox.json"
    assert history.load_items(20, path=path) == []


def test_round_trip_save_and_load(tmp_path):
    path = tmp_path / "inbox.json"
    items = ["üçüncü", "ikinci", "birinci"]
    history.save_items(items, path=path)
    assert history.load_items(20, path=path) == items


def test_load_respects_limit(tmp_path):
    path = tmp_path / "inbox.json"
    history.save_items([f"d{i}" for i in range(30)], path=path)
    assert history.load_items(5, path=path) == [f"d{i}" for i in range(5)]


def test_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "inbox.json"
    path.write_text("not json", encoding="utf-8")
    assert history.load_items(10, path=path) == []


def test_clear_storage_removes_file(tmp_path):
    path = tmp_path / "inbox.json"
    history.save_items(["a"], path=path)
    history.clear_storage(path=path)
    assert not path.exists()


def test_saved_payload_has_version(tmp_path):
    path = tmp_path / "inbox.json"
    history.save_items(["x"], path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["items"] == ["x"]


def test_append_item_prepends_and_dedupes(tmp_path):
    path = tmp_path / "inbox.json"
    history.save_items(["eski"], path=path)
    assert history.append_item("yeni", path=path) is True
    assert history.load_items(10, path=path) == ["yeni", "eski"]
    history.append_item("eski", path=path)
    assert history.load_items(10, path=path) == ["eski", "yeni"]


def test_append_item_rejects_blank(tmp_path):
    path = tmp_path / "inbox.json"
    assert history.append_item("  ", path=path) is False
