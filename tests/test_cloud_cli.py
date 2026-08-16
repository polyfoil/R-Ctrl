"""Tests for rctrl.py — the OpenAI Whisper API entry point.

This mode kept its own hotkey handling long after the widget fixed the Left
Ctrl overlap, so the strict-name and None-guard behaviour is pinned here too.
"""

import types

import numpy as np
import pytest

import rctrl
from core.audio import StopReason


def _event(name, event_type):
    return types.SimpleNamespace(name=name, event_type=event_type)


class FakeRecorder:
    def __init__(self):
        self.active = False
        self.started = 0
        self.start_error: Exception | None = None
        self.next_result = (np.zeros(16000, dtype=np.float32), StopReason.OK)

    def start(self):
        if self.start_error:
            raise self.start_error
        self.active = True
        self.started += 1

    def stop(self):
        self.active = False
        return self.next_result

    def duration(self, audio):
        return len(audio) / 16000


class InlineThread:
    def __init__(self, target=None, args=(), daemon=None, **kw):
        self._target, self._args = target, args

    def start(self):
        if self._target:
            self._target(*self._args)


@pytest.fixture
def cli(monkeypatch):
    rec = FakeRecorder()
    pasted: list[str] = []
    monkeypatch.setattr(rctrl, "recorder", rec)
    monkeypatch.setattr(rctrl, "_busy", False)
    monkeypatch.setattr(rctrl.threading, "Thread", InlineThread)
    monkeypatch.setattr(rctrl, "paste_text", lambda t: pasted.append(t) or True)
    monkeypatch.setattr(rctrl, "transcribe", lambda audio: "merhaba dünya")
    return rec, pasted


# --- hotkey filtering -----------------------------------------------------

def test_target_hotkey_starts_recording(cli):
    rec, _ = cli
    rctrl._on_key_event(_event("right ctrl", "down"))
    assert rec.active is True


def test_left_ctrl_is_ignored(cli):
    """`on_press_key` used to fire for Left Ctrl too — hence the strict check."""
    rec, _ = cli
    rctrl._on_key_event(_event("ctrl", "down"))
    assert rec.active is False
    assert rec.started == 0


def test_other_keys_are_ignored(cli):
    rec, _ = cli
    rctrl._on_key_event(_event("a", "down"))
    assert rec.started == 0


def test_event_without_a_name_does_not_raise(cli):
    """Media and unknown scan codes arrive with name=None."""
    rec, _ = cli
    rctrl._on_key_event(_event(None, "down"))
    assert rec.started == 0


def test_hotkey_match_is_case_insensitive(cli):
    rec, _ = cli
    rctrl._on_key_event(_event("Right Ctrl", "down"))
    assert rec.active is True


# --- recording lifecycle --------------------------------------------------

def test_release_transcribes_and_pastes(cli):
    rec, pasted = cli
    rctrl._on_key_event(_event("right ctrl", "down"))
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == ["merhaba dünya"]


def test_release_without_recording_does_nothing(cli):
    _, pasted = cli
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == []


def test_too_short_recording_is_skipped(cli):
    rec, pasted = cli
    rctrl._on_key_event(_event("right ctrl", "down"))
    rec.next_result = (None, StopReason.TOO_SHORT)
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == []


def test_silent_microphone_is_skipped(cli):
    rec, pasted = cli
    rctrl._on_key_event(_event("right ctrl", "down"))
    rec.next_result = (None, StopReason.NO_AUDIO)
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == []


def test_microphone_failure_is_survivable(cli):
    rec, pasted = cli
    rec.start_error = OSError("device busy")
    rctrl._on_key_event(_event("right ctrl", "down"))
    assert rec.active is False
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == []


def test_empty_transcription_is_not_pasted(cli, monkeypatch):
    _, pasted = cli
    monkeypatch.setattr(rctrl, "transcribe", lambda audio: "")
    rctrl._on_key_event(_event("right ctrl", "down"))
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert pasted == []


def test_transcription_error_does_not_crash_the_hook(cli, monkeypatch):
    def _boom(audio):
        raise RuntimeError("api down")

    monkeypatch.setattr(rctrl, "transcribe", _boom)
    rctrl._on_key_event(_event("right ctrl", "down"))
    rctrl._on_key_event(_event("right ctrl", "up"))
    assert rctrl._busy is False, "the busy flag must be cleared even on failure"


def test_key_repeat_does_not_restart_recording(cli):
    """Holding the key fires repeated 'down' events."""
    rec, _ = cli
    for _ in range(5):
        rctrl._on_key_event(_event("right ctrl", "down"))
    assert rec.started == 1


# --- upload path ----------------------------------------------------------

def test_audio_is_uploaded_from_memory(monkeypatch):
    """No temp WAV file: the request body is built in a BytesIO buffer."""
    captured = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(text=" merhaba dünya ")

    fake_client = types.SimpleNamespace(
        audio=types.SimpleNamespace(transcriptions=FakeTranscriptions())
    )
    monkeypatch.setattr(rctrl, "client", fake_client)

    result = rctrl.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == "Merhaba dünya"
    name, buffer, mime = captured["file"]
    assert name.endswith(".wav")
    assert mime == "audio/wav"
    assert hasattr(buffer, "read"), "a file path would mean a temp file on disk"
    assert buffer.read(4) == b"RIFF"


def test_language_is_sent_when_configured(monkeypatch):
    captured = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(text="test")

    monkeypatch.setattr(rctrl, "client", types.SimpleNamespace(
        audio=types.SimpleNamespace(transcriptions=FakeTranscriptions())
    ))
    monkeypatch.setattr(rctrl, "LANGUAGE", "tr")
    rctrl.transcribe(np.zeros(16000, dtype=np.float32))
    assert captured["language"] == "tr"
    assert captured["model"] == rctrl.MODEL
