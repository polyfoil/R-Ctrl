"""Dictation controller — Qt-free state machine shared by the widget entry point."""

from __future__ import annotations

import threading
import time
from enum import Enum

import numpy as np

from core.audio import Recorder, StopReason
from core.config import GPU_AUTO_FALLBACK_KEY, compute_for_device, save_config
from core.engine import TranscriptionEngine
from core.history import INBOX_MAX_ITEMS, clear_storage, load_items, save_items
from core.inject import copy_to_clipboard, paste_text

HISTORY_LIMIT = INBOX_MAX_ITEMS


def _log(msg: str) -> None:
    print(f"[rctrl-widget] {msg}", flush=True)


class State(Enum):
    LOADING = "loading"
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    FAILED = "failed"


LEGAL_TRANSITIONS: dict[State, set[State]] = {
    State.LOADING: {State.IDLE, State.FAILED},
    State.IDLE: {State.RECORDING, State.LOADING},
    State.RECORDING: {State.TRANSCRIBING, State.IDLE},
    State.TRANSCRIBING: {State.IDLE},
    State.FAILED: {State.LOADING},
}


class DictationController:
    """Owns the recorder, the model and the dictation history.

    UI updates go through `signals` only — no Qt imports here.
    """

    def __init__(self, config, signals, engine: TranscriptionEngine | None = None):
        self.config = config
        self.signals = signals

        if engine is not None:
            self.engine = engine
            initial = State.IDLE if engine.ready else State.LOADING
        else:
            self.engine = TranscriptionEngine(
                model_size=config.get("model", "large-v3"),
                device=config.get("device", "cuda"),
                compute=config.get("compute", "float16"),
                language=config.get("language"),
            )
            initial = State.LOADING
        self.input_device = config.get("input_device")
        self.recorder = Recorder(
            device=self.input_device,
            on_level=self.signals.audio_level.emit,
        )

        self.history: list[str] = load_items(HISTORY_LIMIT)
        self._state = initial
        self._lock = threading.RLock()

    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    def _transition(self, to: State) -> bool:
        with self._lock:
            if to not in LEGAL_TRANSITIONS[self._state]:
                return False
            self._state = to
            return True

    @property
    def recording(self) -> bool:
        return self.state is State.RECORDING

    @property
    def busy(self) -> bool:
        return self.state in (State.LOADING, State.TRANSCRIBING)

    @property
    def model_size(self) -> str:
        return self.engine.model_size

    @property
    def language(self) -> str | None:
        return self.engine.language

    @language.setter
    def language(self, value: str | None) -> None:
        self.engine.language = value

    def load_model_async(self) -> None:
        if self.engine.ready:
            if self.state is State.LOADING:
                self._transition(State.IDLE)
            info = f"{self.engine.model_size} ({self.engine.device})"
            self.signals.model_ready.emit(True, info)
            return
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self) -> None:
        _log(f"Loading model: {self.engine.model_size} ({self.engine.device}) ...")
        ok, info = self.engine.load(log=_log)
        if ok:
            _log(f"Model ready: {info}")
            self._transition(State.IDLE)
        else:
            _log(f"Model load error: {info}")
            self._transition(State.FAILED)
        self.signals.model_ready.emit(ok, info)

    def change_model(self, model_name: str) -> bool:
        if not self._transition(State.LOADING):
            _log(f"Model change to {model_name} refused while {self.state.value}")
            return False
        self.engine.model_size = model_name
        self.engine.compute = compute_for_device(self.engine.device)
        self.config["model"] = model_name
        self.config["compute"] = self.engine.compute
        self.config.pop(GPU_AUTO_FALLBACK_KEY, None)
        save_config(self.config)
        self.load_model_async()
        return True

    def set_input_device(self, device_index: int | None) -> None:
        self.input_device = device_index
        self.recorder.device = device_index
        self.config["input_device"] = device_index
        save_config(self.config)

    def start_recording(self) -> None:
        if not self._transition(State.RECORDING):
            return
        try:
            self.recorder.start()
        except Exception as e:
            _log(f"Microphone error: {e}")
            self._transition(State.IDLE)
            self.signals.state_changed.emit("error", "Microphone error")
            return
        _log("🎙 Recording started...")
        self.signals.state_changed.emit("recording", "Listening...")

    def stop_recording(self) -> None:
        if self.state is not State.RECORDING:
            return
        audio, reason = self.recorder.stop()
        if audio is None:
            self._transition(State.IDLE)
            message = "Too short" if reason is StopReason.TOO_SHORT else "No audio captured"
            _log(f"  ({message})")
            self.signals.state_changed.emit("idle", message)
            return
        if not self._transition(State.TRANSCRIBING):
            return
        _log(f"Recording complete ({self.recorder.duration(audio):.1f}s) — transcribing...")
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio: np.ndarray) -> None:
        self.signals.state_changed.emit("processing", "Transcribing...")
        try:
            t0 = time.time()
            text = self.engine.transcribe(audio)
            elapsed = round(time.time() - t0, 2)
            if text:
                _log(f'✓ ({elapsed}s) → "{text}"')
                self._add_to_history(text)
                pasted = paste_text(text)
                self._transition(State.IDLE)
                if pasted:
                    self.signals.state_changed.emit("success", text)
                else:
                    copy_to_clipboard(text)
                    self.signals.state_changed.emit("paste_failed", text)
                return
            _log("  (silence or filtered audio)")
            self._transition(State.IDLE)
            self.signals.state_changed.emit("idle", "Empty")
        except Exception as e:
            _log(f"Transcription error: {e}")
            self._transition(State.IDLE)
            self.signals.state_changed.emit("error", f"Error: {e}")

    def _add_to_history(self, text: str) -> None:
        item = text.strip()
        with self._lock:
            if item in self.history:
                self.history.remove(item)
            self.history.insert(0, item)
            del self.history[HISTORY_LIMIT:]
            save_items(self.history)

    def clear_history(self) -> None:
        with self._lock:
            self.history.clear()
            clear_storage()

    def remove_history_item(self, text: str) -> None:
        item = text.strip()
        with self._lock:
            if item in self.history:
                self.history.remove(item)
                save_items(self.history)

    def reload_history_from_disk(self) -> None:
        """Refresh in-memory list after another process (e.g. server) wrote inbox.json."""
        fresh = load_items(HISTORY_LIMIT)
        with self._lock:
            self.history[:] = fresh
