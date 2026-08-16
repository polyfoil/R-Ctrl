"""Tests for DictationController — the Qt-free half of the widget.

This class was deliberately built to touch no Qt method (it only emits
signals), precisely so it could be tested without a display or a GPU. It then
shipped with no tests at all, and a concurrency hole went unnoticed: changing
the model mid-transcription ran `release()` + `gc.collect()` while inference
was still running.

The controller now owns an explicit, lock-guarded state machine, and these
tests pin the legal transitions down.
"""

import numpy as np
import pytest

import rctrl_controller as c
from core.audio import StopReason

# --- doubles --------------------------------------------------------------

class FakeSignals:
    """Stands in for AudioSignals, recording every emission."""

    def __init__(self):
        self.states: list[tuple[str, str]] = []
        self.levels: list[float] = []
        self.model_events: list[tuple[bool, str]] = []
        self.state_changed = self._Sig(self.states, pair=True)
        self.audio_level = self._Sig(self.levels)
        self.model_ready = self._Sig(self.model_events, pair=True)

    class _Sig:
        def __init__(self, sink, pair=False):
            self._sink = sink
            self._pair = pair

        def emit(self, *args):
            self._sink.append(args if self._pair else args[0])


class FakeRecorder:
    def __init__(self, device=None, on_level=None, **kw):
        self.device = device
        self.on_level = on_level
        self.active = False
        self.start_error: Exception | None = None
        self.next_result = (np.zeros(16000, dtype=np.float32), StopReason.OK)

    def start(self):
        if self.start_error:
            raise self.start_error
        self.active = True

    def stop(self):
        self.active = False
        return self.next_result

    def duration(self, audio):
        return len(audio) / 16000


class FakeEngine:
    def __init__(self, model_size="large-v3", device="cuda", compute="float16", language="tr"):
        self.model_size = model_size
        self.device = device
        self.compute = compute
        self.language = language
        self.ready = False
        self.load_calls = 0
        self.load_ok = True
        self.text = "merhaba dünya"
        self.transcribe_calls = 0

    def load(self, log=None, **_kw):
        self.load_calls += 1
        self.ready = self.load_ok
        return self.load_ok, f"{self.model_size} ({self.device})"

    def release(self):
        self.ready = False

    def transcribe(self, audio):
        self.transcribe_calls += 1
        return self.text


class InlineThread:
    """Runs the target immediately so tests stay deterministic."""

    def __init__(self, target=None, args=(), daemon=None, **kw):
        self._target = target
        self._args = args

    def start(self):
        if self._target:
            self._target(*self._args)


@pytest.fixture
def ctl(monkeypatch):
    monkeypatch.setattr(c, "Recorder", FakeRecorder)
    monkeypatch.setattr(c, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(c.threading, "Thread", InlineThread)
    monkeypatch.setattr(c, "save_config", lambda cfg: None)
    monkeypatch.setattr(c, "paste_text", lambda text: True)
    monkeypatch.setattr(c, "load_items", lambda limit: [])
    monkeypatch.setattr(c, "save_items", lambda items: None)
    monkeypatch.setattr(c, "clear_storage", lambda: None)
    monkeypatch.setattr(c, "copy_to_clipboard", lambda text: None)

    signals = FakeSignals()
    config = {
        "model": "large-v3", "device": "cuda", "compute": "float16",
        "language": "tr", "hotkey": "right ctrl", "input_device": None,
    }
    return c.DictationController(config, signals)


def _ready(ctl):
    """Take the controller from LOADING to IDLE."""
    ctl.load_model_async()
    return ctl


# --- initial state --------------------------------------------------------

def test_starts_in_loading_state(ctl):
    assert ctl.state is c.State.LOADING
    assert ctl.busy is True


def test_becomes_idle_after_a_successful_load(ctl):
    _ready(ctl)
    assert ctl.state is c.State.IDLE
    assert ctl.busy is False
    assert ctl.signals.model_events[-1][0] is True


def test_preloaded_engine_starts_idle_and_skips_thread_load(monkeypatch):
    monkeypatch.setattr(c, "Recorder", FakeRecorder)
    monkeypatch.setattr(c, "TranscriptionEngine", FakeEngine)
    monkeypatch.setattr(c.threading, "Thread", InlineThread)
    engine = FakeEngine()
    engine.ready = True
    signals = FakeSignals()
    config = {
        "model": "large-v3", "device": "cuda", "compute": "float16",
        "language": "tr", "hotkey": "right ctrl", "input_device": None,
    }
    ctl = c.DictationController(config, signals, engine=engine)
    assert ctl.state is c.State.IDLE
    ctl.load_model_async()
    assert ctl.engine.load_calls == 0
    assert signals.model_events[-1][0] is True


def test_enters_failed_state_when_load_fails(ctl):
    ctl.engine.load_ok = False
    ctl.load_model_async()
    assert ctl.state is c.State.FAILED
    assert ctl.signals.model_events[-1][0] is False


# --- recording transitions ------------------------------------------------

def test_recording_starts_from_idle(ctl):
    _ready(ctl)
    ctl.start_recording()
    assert ctl.state is c.State.RECORDING
    assert ("recording", "Listening...") in ctl.signals.states


def test_recording_cannot_start_while_loading(ctl):
    ctl.start_recording()
    assert ctl.state is c.State.LOADING
    assert ctl.recorder.active is False


def test_recording_cannot_start_twice(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.start_recording()
    assert ctl.state is c.State.RECORDING


def test_microphone_failure_returns_to_idle(ctl):
    _ready(ctl)
    ctl.recorder.start_error = OSError("device in use")
    ctl.start_recording()
    assert ctl.state is c.State.IDLE, "a failed start must not strand the controller"
    assert ctl.signals.states[-1][0] == "error"


def test_stop_runs_transcription_and_returns_to_idle(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.stop_recording()
    assert ctl.engine.transcribe_calls == 1
    assert ctl.state is c.State.IDLE
    assert ("success", "merhaba dünya") in ctl.signals.states


def test_stop_without_recording_is_a_no_op(ctl):
    _ready(ctl)
    ctl.stop_recording()
    assert ctl.engine.transcribe_calls == 0
    assert ctl.state is c.State.IDLE


def test_transcription_error_returns_to_idle(ctl):
    _ready(ctl)

    def _boom(audio):
        raise RuntimeError("cuda oom")

    ctl.engine.transcribe = _boom
    ctl.start_recording()
    ctl.stop_recording()
    assert ctl.state is c.State.IDLE
    assert ctl.signals.states[-1][0] == "error"


def test_empty_transcript_returns_to_idle_without_pasting(ctl, monkeypatch):
    pasted = []
    monkeypatch.setattr(c, "paste_text", lambda t: pasted.append(t))
    _ready(ctl)
    ctl.engine.text = ""
    ctl.start_recording()
    ctl.stop_recording()
    assert pasted == []
    assert ctl.state is c.State.IDLE


# --- stop reasons ---------------------------------------------------------
#
# stop() used to return None for both "no audio at all" and "too short", so a
# dead microphone was reported to the user as a short recording.

def test_too_short_recording_is_reported_as_such(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.recorder.next_result = (None, StopReason.TOO_SHORT)
    ctl.stop_recording()
    assert ctl.state is c.State.IDLE
    assert ctl.signals.states[-1] == ("idle", "Too short")


def test_silent_microphone_is_reported_differently(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.recorder.next_result = (None, StopReason.NO_AUDIO)
    ctl.stop_recording()
    assert ctl.state is c.State.IDLE
    assert ctl.signals.states[-1][1] != "Too short"


# --- model changes --------------------------------------------------------

def test_model_change_from_idle_is_accepted(ctl):
    _ready(ctl)
    assert ctl.change_model("medium") is True
    assert ctl.engine.model_size == "medium"
    assert ctl.config["model"] == "medium"


def test_model_change_is_rejected_while_transcribing(ctl):
    """gc.collect() must never run while inference is in flight."""
    _ready(ctl)
    seen = []

    def _slow_transcribe(audio):
        seen.append(ctl.change_model("medium"))
        return "sonuç"

    ctl.engine.transcribe = _slow_transcribe
    ctl.start_recording()
    ctl.stop_recording()
    assert seen == [False], "change_model must refuse while TRANSCRIBING"
    assert ctl.engine.model_size == "large-v3"


def test_model_change_is_rejected_while_recording(ctl):
    _ready(ctl)
    ctl.start_recording()
    assert ctl.change_model("medium") is False
    assert ctl.engine.model_size == "large-v3"


def test_model_change_rederives_compute_for_the_device(ctl):
    _ready(ctl)
    ctl.engine.device = "cpu"
    ctl.change_model("base")
    assert ctl.engine.compute == "int8"
    assert ctl.config["compute"] == "int8"


def test_model_change_can_recover_from_failed_state(ctl):
    ctl.engine.load_ok = False
    ctl.load_model_async()
    assert ctl.state is c.State.FAILED
    ctl.engine.load_ok = True
    assert ctl.change_model("small") is True
    assert ctl.state is c.State.IDLE


# --- input device ---------------------------------------------------------

def test_input_device_change_reaches_the_recorder(ctl):
    _ready(ctl)
    ctl.set_input_device(3)
    assert ctl.recorder.device == 3
    assert ctl.config["input_device"] == 3


# --- history --------------------------------------------------------------

def test_history_records_successful_dictations(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.stop_recording()
    assert ctl.history == ["merhaba dünya"]


def test_history_moves_repeats_to_the_front_without_duplicating(ctl):
    _ready(ctl)
    for text in ["bir", "iki", "bir"]:
        ctl.engine.text = text
        ctl.start_recording()
        ctl.stop_recording()
    assert ctl.history == ["bir", "iki"]


def test_history_is_capped(ctl):
    _ready(ctl)
    for i in range(c.HISTORY_LIMIT + 5):
        ctl.engine.text = f"dikte {i}"
        ctl.start_recording()
        ctl.stop_recording()
    assert len(ctl.history) == c.HISTORY_LIMIT
    assert ctl.history[0] == f"dikte {c.HISTORY_LIMIT + 4}"


def test_clear_history(ctl):
    _ready(ctl)
    ctl.start_recording()
    ctl.stop_recording()
    ctl.clear_history()
    assert ctl.history == []


def test_paste_failure_leaves_text_on_clipboard_signal(ctl, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(c, "paste_text", lambda text: False)
    monkeypatch.setattr(c, "copy_to_clipboard", lambda text: copied.append(text))

    _ready(ctl)
    ctl.start_recording()
    ctl.stop_recording()

    assert ("paste_failed", "merhaba dünya") in ctl.signals.states
    assert copied == ["merhaba dünya"]


def test_history_is_persisted_via_save_items(ctl, monkeypatch):
    saved: list[list[str]] = []
    monkeypatch.setattr(c, "save_items", lambda items: saved.append(list(items)))

    _ready(ctl)
    ctl.start_recording()
    ctl.stop_recording()

    assert saved[-1] == ["merhaba dünya"]


def test_remove_history_item_persists(ctl, monkeypatch):
    saved: list[list[str]] = []
    monkeypatch.setattr(c, "save_items", lambda items: saved.append(list(items)))
    ctl.history = ["a", "b"]
    ctl.remove_history_item("a")
    assert ctl.history == ["b"]
    assert saved == [["b"]]


def test_clear_history_calls_clear_storage(ctl, monkeypatch):
    cleared: list[bool] = []
    monkeypatch.setattr(c, "clear_storage", lambda: cleared.append(True))

    _ready(ctl)
    ctl.clear_history()
    assert cleared == [True]


# --- level forwarding -----------------------------------------------------

def test_recorder_level_callback_is_wired_to_the_signal(ctl):
    ctl.recorder.on_level(0.42)
    assert ctl.signals.levels == [0.42]


def test_reload_history_from_disk_replaces_memory(ctl, monkeypatch):
    _ready(ctl)
    ctl.history = ["stale"]
    monkeypatch.setattr(c, "load_items", lambda limit: ["from-disk", "also"])
    ctl.reload_history_from_disk()
    assert ctl.history == ["from-disk", "also"]
