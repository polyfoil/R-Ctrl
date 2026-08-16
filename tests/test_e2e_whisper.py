"""End-to-end pipeline: real tiny Whisper on CPU + in-memory WAV (B-008).

Skipped unless RCTRL_E2E=1 — downloads ~75 MB model on first run.

Scope: real tiny Whisper on CPU, in-memory WAV I/O, and `format_transcript`.
Uses silence (not spoken audio) so CI stays deterministic; a spoken fixture would
be optional manual QA only.
"""

import io
import os

import numpy as np
import pytest
import soundfile as sf

from core.audio import SAMPLE_RATE
from core.engine import TranscriptionEngine
from core.text import format_transcript


def _silent_wav_buffer(seconds: float = 1.5) -> io.BytesIO:
    samples = int(SAMPLE_RATE * seconds)
    audio = np.zeros(samples, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf


@pytest.mark.slow
def test_whisper_load_transcribe_bytesio_pipeline():
    if not os.environ.get("RCTRL_E2E"):
        pytest.skip("Set RCTRL_E2E=1 to run real-model integration test")

    engine = TranscriptionEngine("tiny", "cpu", "int8", language="tr")
    ok, info = engine.load()
    assert ok, info

    raw = engine.transcribe(_silent_wav_buffer())
    assert isinstance(raw, str)
    cleaned = format_transcript(raw)
    assert isinstance(cleaned, str)
    # Scope: pipeline + model load; silence should not yield a long hallucination.
    assert len(cleaned.strip()) < 80

    engine.release()
