"""Microphone capture.

Deliberately free of any UI dependency: progress is reported through a plain
callable so both the Qt widget and the headless CLI can use the same recorder.
"""

import time
from collections.abc import Callable
from enum import Enum

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1

# Recordings shorter than this are treated as accidental key taps.
MIN_SEC = 0.3

# Level callbacks are throttled to roughly the visualiser's frame rate.
# Without this the audio thread fires ~86 times a second for a 30 fps widget.
_LEVEL_INTERVAL = 1.0 / 30.0

# Scales RMS (which sits well below 1.0 for speech) into a 0..1 display range.
_LEVEL_GAIN = 60.0


class StopReason(str, Enum):
    """Why a recording ended.

    NO_AUDIO and TOO_SHORT used to be indistinguishable — both came back as
    None — so a microphone that produced nothing was reported to the user as a
    recording that was too short.
    """

    OK = "ok"
    NO_AUDIO = "no_audio"
    TOO_SHORT = "too_short"


class Recorder:
    """Collects microphone blocks in memory and returns them as one array."""

    def __init__(
        self,
        device: int | None = None,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        min_sec: float = MIN_SEC,
        on_level: Callable[[float], None] | None = None,
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.min_sec = min_sec
        self.on_level = on_level

        self.active = False
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._last_level_at = 0.0

    def start(self) -> None:
        """Open the input stream. Raises on device errors so callers can react."""
        self._frames = []
        self._last_level_at = 0.0
        self.active = True
        try:
            self._stream = sd.InputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self.active = False
            self._stream = None
            raise

    def _callback(self, indata, frame_count, time_info, status) -> None:
        if not self.active:
            return
        self._frames.append(indata.copy())
        if self.on_level is None:
            return
        now = time.monotonic()
        if now - self._last_level_at < _LEVEL_INTERVAL:
            return
        self._last_level_at = now
        # dot() keeps this allocation-free; `indata ** 2` would build a new
        # array on every block, inside a realtime audio callback.
        flat = indata.reshape(-1)
        rms = float(np.sqrt(flat.dot(flat) / flat.size)) if flat.size else 0.0
        self.on_level(min(1.0, rms * _LEVEL_GAIN))

    def stop(self) -> tuple[np.ndarray | None, StopReason]:
        """Close the stream and return (recording, reason).

        The reason distinguishes "the microphone gave us nothing" from "you
        let go too quickly", which the caller needs in order to tell the user
        something true.
        """
        self.active = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                # Never let a driver hiccup swallow the recording itself.
                print(f"[rctrl-audio] Stream close failed: {e}", flush=True)
            self._stream = None

        if not self._frames:
            return None, StopReason.NO_AUDIO

        audio: np.ndarray = np.concatenate(self._frames, axis=0)
        self._frames = []
        if self.duration(audio) < self.min_sec:
            return None, StopReason.TOO_SHORT
        return audio, StopReason.OK

    def duration(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate
