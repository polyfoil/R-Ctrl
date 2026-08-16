"""Tests for core.engine — model lifecycle and transcription plumbing."""

import numpy as np
import pytest

from core import engine as eng


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeModel:
    """Stands in for WhisperModel and records how it was called."""
    instances: list["FakeModel"] = []

    def __init__(self, model_size, device=None, compute_type=None):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.calls = []
        FakeModel.instances.append(self)

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        return [FakeSegment(" merhaba "), FakeSegment(" dünya ")], None


@pytest.fixture(autouse=True)
def reset_instances():
    FakeModel.instances = []
    yield
    FakeModel.instances = []


@pytest.fixture
def gpu_ok(monkeypatch):
    monkeypatch.setattr(eng, "WhisperModel", FakeModel)


@pytest.fixture
def gpu_fails(monkeypatch):
    def _factory(model_size, device=None, compute_type=None):
        if device == "cuda":
            raise RuntimeError("CUDA driver missing")
        return FakeModel(model_size, device, compute_type)

    monkeypatch.setattr(eng, "WhisperModel", _factory)


def _engine(**kw):
    defaults = {"model_size": "large-v3", "device": "cuda",
                "compute": "float16", "language": "tr"}
    defaults.update(kw)
    return eng.TranscriptionEngine(**defaults)


# --- loading --------------------------------------------------------------

def test_loads_on_gpu(gpu_ok):
    e = _engine()
    ok, info = e.load()
    assert ok and e.ready
    assert e.device == "cuda"
    assert "large-v3" in info


def test_not_ready_before_load(gpu_ok):
    assert _engine().ready is False


def test_falls_back_to_cpu_when_gpu_fails(gpu_fails):
    e = _engine()
    ok, info = e.load()
    assert ok and e.ready
    assert e.device == eng.CPU_DEVICE
    assert e.compute == eng.CPU_COMPUTE
    assert "GPU failed" in info


def test_reports_failure_when_both_paths_fail(monkeypatch):
    def _always_fails(*a, **k):
        raise RuntimeError("no backend at all")

    monkeypatch.setattr(eng, "WhisperModel", _always_fails)
    e = _engine()
    ok, info = e.load()
    assert ok is False
    assert e.ready is False
    assert "no backend" in info


def test_previous_model_is_released_before_reload(gpu_ok):
    """Switching models must not hold two models in VRAM at once."""
    e = _engine()
    e.load()
    first = e.model
    seen = []

    original_release = e.release

    def _tracking_release():
        seen.append(e.model)
        original_release()

    e.release = _tracking_release
    e.model_size = "medium"
    e.load()

    assert seen == [first], "release() must run before the new model is built"
    assert e.model is not first


def test_release_clears_the_model(gpu_ok):
    e = _engine()
    e.load()
    e.release()
    assert e.model is None
    assert e.ready is False


# --- transcription --------------------------------------------------------

def test_transcribe_requires_a_loaded_model():
    with pytest.raises(RuntimeError, match="not loaded"):
        _engine().transcribe(np.zeros(16000, dtype=np.float32))


def test_numpy_audio_is_passed_as_float32(gpu_ok):
    e = _engine()
    e.load()
    e.transcribe(np.zeros((16000, 1), dtype=np.float64))
    audio, _ = e.model.calls[0]
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert audio.ndim == 1, "audio must be flattened before inference"


def test_file_like_audio_is_passed_through_untouched(gpu_ok):
    import io
    e = _engine()
    e.load()
    buffer = io.BytesIO(b"RIFF....")
    e.transcribe(buffer)
    audio, _ = e.model.calls[0]
    assert audio is buffer, "no temp-file round trip for file-like input"


def test_segments_are_joined_and_formatted(gpu_ok):
    e = _engine()
    e.load()
    assert e.transcribe(np.zeros(16000, dtype=np.float32)) == "Merhaba dünya"


def test_vad_settings_are_applied(gpu_ok):
    e = _engine()
    e.load()
    e.transcribe(np.zeros(16000, dtype=np.float32))
    _, kwargs = e.model.calls[0]
    assert kwargs["vad_filter"] is True
    assert kwargs["vad_parameters"]["min_silence_duration_ms"] == eng.VAD_MIN_SILENCE_MS
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["no_speech_threshold"] == eng.NO_SPEECH_THRESHOLD


def test_language_is_forwarded_when_set(gpu_ok):
    e = _engine(language="en")
    e.load()
    e.transcribe(np.zeros(16000, dtype=np.float32))
    _, kwargs = e.model.calls[0]
    assert kwargs["language"] == "en"


def test_language_is_omitted_for_auto_detect(gpu_ok):
    e = _engine(language=None)
    e.load()
    e.transcribe(np.zeros(16000, dtype=np.float32))
    _, kwargs = e.model.calls[0]
    assert "language" not in kwargs
