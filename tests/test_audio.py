"""Tests for core.audio — the microphone recorder."""

import numpy as np
import pytest

from core import audio as ca
from core.audio import StopReason


class FakeStream:
    """Captures the InputStream construction args and tracks open/closed state."""
    last = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        FakeStream.last = self

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture
def stream(monkeypatch):
    FakeStream.last = None
    monkeypatch.setattr(ca.sd, "InputStream", FakeStream)
    return FakeStream


def _block(samples, value=0.5):
    return np.full((samples, 1), value, dtype=np.float32)


def _feed(rec, blocks, samples_per_block=1600):
    for _ in range(blocks):
        rec._callback(_block(samples_per_block), samples_per_block, None, None)


# --- stream configuration -------------------------------------------------

def test_stream_uses_project_audio_format(stream):
    rec = ca.Recorder()
    rec.start()
    assert stream.last.kwargs["samplerate"] == 16000
    assert stream.last.kwargs["channels"] == 1
    assert stream.last.kwargs["dtype"] == "float32"


def test_selected_device_is_forwarded(stream):
    ca.Recorder(device=3).start()
    assert stream.last.kwargs["device"] == 3


def test_stream_is_closed_on_stop(stream):
    rec = ca.Recorder()
    rec.start()
    _feed(rec, 10)
    rec.stop()
    assert stream.last.closed is True
    assert rec.active is False


def test_start_failure_leaves_recorder_inactive(monkeypatch):
    def _boom(**kwargs):
        raise OSError("no such device")

    monkeypatch.setattr(ca.sd, "InputStream", _boom)
    rec = ca.Recorder()
    with pytest.raises(OSError):
        rec.start()
    assert rec.active is False


# --- minimum duration -----------------------------------------------------

def test_recording_below_minimum_is_discarded(stream):
    rec = ca.Recorder(min_sec=0.3)
    rec.start()
    _feed(rec, 1, samples_per_block=1600)  # 0.1 s
    audio, reason = rec.stop()
    assert audio is None
    assert reason is StopReason.TOO_SHORT


def test_recording_above_minimum_is_returned(stream):
    rec = ca.Recorder(min_sec=0.3)
    rec.start()
    _feed(rec, 10, samples_per_block=1600)  # 1.0 s
    audio, reason = rec.stop()
    assert audio is not None
    assert reason is StopReason.OK
    assert len(audio) == 16000


def test_no_audio_is_distinguishable_from_too_short(stream):
    """A dead microphone must not be reported as a short recording."""
    rec = ca.Recorder()
    rec.start()
    audio, reason = rec.stop()
    assert audio is None
    assert reason is StopReason.NO_AUDIO


def test_duration_is_computed_from_sample_rate():
    rec = ca.Recorder()
    assert rec.duration(np.zeros(8000, dtype=np.float32)) == pytest.approx(0.5)


def test_frames_are_cleared_between_recordings(stream):
    rec = ca.Recorder(min_sec=0.1)
    rec.start()
    _feed(rec, 10)
    first, _ = rec.stop()
    rec.start()
    _feed(rec, 5)
    second, _ = rec.stop()
    assert len(first) == 16000
    assert len(second) == 8000, "previous recording must not leak into the next"


def test_callback_ignores_blocks_after_stop(stream):
    rec = ca.Recorder(min_sec=0.1)
    rec.start()
    _feed(rec, 10)
    rec.stop()
    _feed(rec, 10)  # late blocks from a draining driver
    rec.start()
    _feed(rec, 2)
    audio, _ = rec.stop()
    assert len(audio) == 3200


# --- level callback -------------------------------------------------------

def test_level_callback_receives_normalised_value(stream):
    levels = []
    rec = ca.Recorder(on_level=levels.append)
    rec.start()
    rec._callback(_block(1600, value=0.5), 1600, None, None)
    assert levels
    assert 0.0 <= levels[0] <= 1.0


def test_level_reflects_signal_amplitude(stream):
    quiet, loud = [], []
    rec_q = ca.Recorder(on_level=quiet.append)
    rec_q.start()
    rec_q._callback(_block(1600, value=0.001), 1600, None, None)

    rec_l = ca.Recorder(on_level=loud.append)
    rec_l.start()
    rec_l._callback(_block(1600, value=0.5), 1600, None, None)

    assert loud[0] > quiet[0]


def test_level_is_clamped_to_one(stream):
    levels = []
    rec = ca.Recorder(on_level=levels.append)
    rec.start()
    rec._callback(_block(1600, value=1.0), 1600, None, None)
    assert levels[0] == 1.0


def test_level_callback_is_throttled(stream):
    """~86 audio blocks per second must not become 86 UI updates."""
    levels = []
    rec = ca.Recorder(on_level=levels.append)
    rec.start()
    _feed(rec, 50, samples_per_block=185)  # 50 blocks inside ~0.6 s of audio
    assert len(levels) < 50


def test_recording_works_without_a_level_callback(stream):
    rec = ca.Recorder(min_sec=0.1, on_level=None)
    rec.start()
    _feed(rec, 10)
    audio, _ = rec.stop()
    assert audio is not None
