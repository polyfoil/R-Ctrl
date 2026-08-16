"""faster-whisper wrapper: model lifecycle and transcription."""

import gc
from typing import Any, BinaryIO

import numpy as np

from core.model_cache import ensure_model_cached
from core.text import format_transcript

# Resolved on first load instead of at import time. `faster_whisper` drags in
# ctranslate2 and torch, which costs seconds and hundreds of megabytes — the
# widget should be on screen before any of that happens, and tests that supply
# their own model double should never pay for it at all.
WhisperModel: Any = None


def _model_class() -> Any:
    global WhisperModel
    if WhisperModel is None:
        from faster_whisper import WhisperModel as _WhisperModel
        WhisperModel = _WhisperModel
    return WhisperModel

# Silero VAD settings. 300 ms trails off quickly enough for dictation while
# still bridging the pauses inside a sentence.
VAD_MIN_SILENCE_MS = 300
NO_SPEECH_THRESHOLD = 0.6

CPU_DEVICE = "cpu"
CPU_COMPUTE = "int8"


class TranscriptionEngine:
    """Loads a Whisper model and turns audio into cleaned-up text."""

    def __init__(self, model_size: str, device: str, compute: str, language: str | None = None):
        self.model_size = model_size
        self.device = device
        self.compute = compute
        self.language = language
        self.model: Any = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self, log=None) -> tuple[bool, str]:
        """Load the model, falling back to CPU when the GPU path fails.

        Returns (ok, description). The previous model is released first so the
        two never occupy VRAM at the same time — switching small -> large-v3
        used to be able to OOM on 8 GB cards for that reason.
        """
        self.release()
        try:
            model_cls = _model_class()
        except Exception as import_error:
            return False, f"faster-whisper could not be imported: {import_error}"

        if log is not None:
            try:
                ensure_model_cached(self.model_size, log)
            except Exception as e:
                log(f"Model download warning: {e}")

        try:
            self.model = model_cls(self.model_size, device=self.device, compute_type=self.compute)
            return True, f"{self.model_size} ({self.device})"
        except Exception as gpu_error:
            try:
                self.model = model_cls(
                    self.model_size, device=CPU_DEVICE, compute_type=CPU_COMPUTE
                )
                self.device = CPU_DEVICE
                self.compute = CPU_COMPUTE
                return True, f"{self.model_size} ({CPU_DEVICE}, GPU failed: {gpu_error})"
            except Exception as cpu_error:
                self.model = None
                return False, str(cpu_error)

    def release(self) -> None:
        """Drop the model and reclaim its memory."""
        if self.model is not None:
            self.model = None
            gc.collect()

    def transcribe(self, audio: np.ndarray | BinaryIO | str) -> str:
        """Transcribe in-memory audio (or a file-like object) to cleaned text.

        NumPy input is passed straight through as float32 — no temp file is
        written anywhere in this path.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded")

        if isinstance(audio, np.ndarray):
            audio = audio.flatten().astype(np.float32)

        kwargs: dict[str, Any] = {"language": self.language} if self.language else {}
        segments, _ = self.model.transcribe(
            audio,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": VAD_MIN_SILENCE_MS},
            condition_on_previous_text=False,
            no_speech_threshold=NO_SPEECH_THRESHOLD,
            **kwargs,
        )
        raw_text = " ".join(seg.text.strip() for seg in segments).strip()
        return format_transcript(raw_text)
