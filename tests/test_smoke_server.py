"""Smoke tests that actually start the server app.

The 2026-08-15 refactor shipped a server that could never load a model when
started the normal way (`uvicorn rctrl.server:app`), because the engine was
only constructed inside `main()`. Nothing caught it: the code compiled and the
unit tests all passed. These tests drive the real ASGI app through its real
lifespan, which is the only thing that would have.
"""

import time

import pytest
from fastapi.testclient import TestClient

import rctrl.server as rctrl_server


class FakeEngine:
    """Engine double — no model download, no GPU."""

    def __init__(self, model_size="tiny", device="cpu", compute="int8", language="tr"):
        self.model_size = model_size
        self.device = device
        self.compute = compute
        self.language = language
        self.ready = False
        self.released = False
        self.transcribed: list[object] = []

    def load(self, log=None, **_kw):
        self.ready = True
        return True, f"{self.model_size} ({self.device})"

    def release(self):
        self.ready = False
        self.released = True

    def transcribe(self, audio):
        self.transcribed.append(audio)
        return "merhaba dünya"


@pytest.fixture
def client(monkeypatch):
    """A TestClient whose context manager runs the app's real lifespan."""
    monkeypatch.setattr(rctrl_server, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(rctrl_server, "load_or_create_config", lambda: (
        {"model": "tiny", "device": "cpu", "compute": "int8", "language": "tr"},
        {"reason": "stub"},
    ))
    monkeypatch.setattr(rctrl_server, "_engine", None)
    with TestClient(rctrl_server.app) as c:
        _wait_until_ready(c)
        yield c


def _wait_until_ready(c, timeout=5.0):
    """The model loads on a background thread; give it a moment."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if c.get("/health").json().get("ready"):
            return
        time.sleep(0.02)


@pytest.mark.smoke
def test_app_becomes_ready_when_started_through_lifespan(client):
    """Running the app as `uvicorn rctrl.server:app` must load a model.

    This is the regression test for the refactor bug: `main()` never runs in
    that scenario, so anything the app needs has to be built in the lifespan.
    """
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["ready"] is True, "engine must be constructed by the lifespan, not by main()"
    assert body["model"] == "tiny"
    assert body["device"] == "cpu"


@pytest.mark.smoke
def test_transcribe_returns_text(client):
    resp = client.post("/transcribe", files={"audio": ("a.wav", b"RIFFfake", "audio/wav")})
    assert resp.status_code == 200
    assert resp.json()["text"] == "merhaba dünya"


@pytest.mark.smoke
def test_transcribe_rejects_empty_upload(client):
    resp = client.post("/transcribe", files={"audio": ("a.wav", b"", "audio/wav")})
    assert resp.status_code == 400


@pytest.mark.smoke
def test_transcribe_rejects_oversized_upload(client):
    payload = b"x" * (rctrl_server.MAX_UPLOAD_BYTES + 10)
    resp = client.post("/transcribe", files={"audio": ("a.wav", payload, "audio/wav")})
    assert resp.status_code == 413


@pytest.mark.smoke
def test_transcribe_reads_from_memory_not_disk(client):
    """The audio must reach the engine as a file-like object, never a path."""
    client.post("/transcribe", files={"audio": ("a.wav", b"RIFFfake", "audio/wav")})
    handed_over = rctrl_server._engine.transcribed[0]
    assert not isinstance(handed_over, str), "a str would mean a temp file path"
    assert hasattr(handed_over, "read")


@pytest.mark.smoke
def test_dictate_endpoint_stores_in_inbox(client, tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.json"
    monkeypatch.setattr("core.history.INBOX_PATH", inbox)
    resp = client.post("/dictate", json={"text": "merhaba"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert inbox.exists()
    assert "merhaba" in inbox.read_text(encoding="utf-8")


@pytest.mark.smoke
def test_dictate_endpoint_ignores_empty_text(client, tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.json"
    monkeypatch.setattr("core.history.INBOX_PATH", inbox)
    assert client.post("/dictate", json={"text": ""}).json()["ok"] is False
    assert not inbox.exists()


@pytest.mark.smoke
def test_static_ui_is_served_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "R-Ctrl" in resp.text


@pytest.mark.smoke
def test_no_cors_headers_are_advertised(client):
    """A wildcard CORS policy once let any visited page reach these endpoints."""
    resp = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}


def test_server_binds_to_localhost_only():
    """Security boundary from ADR-002 — asserted so it cannot drift quietly."""
    assert rctrl_server.HOST == "127.0.0.1"


@pytest.mark.smoke
def test_engine_is_released_on_shutdown(monkeypatch):
    monkeypatch.setattr(rctrl_server, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(rctrl_server, "load_or_create_config", lambda: (
        {"model": "tiny", "device": "cpu", "compute": "int8", "language": "tr"},
        {"reason": "stub"},
    ))
    monkeypatch.setattr(rctrl_server, "_engine", None)
    with TestClient(rctrl_server.app) as c:
        _wait_until_ready(c)
        engine = rctrl_server._engine
    assert engine.released is True
