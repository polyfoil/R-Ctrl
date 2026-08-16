#!/usr/bin/env python3
"""R-Ctrl cloud CLI — push-to-talk dictation via the OpenAI Whisper API.

**Legacy / optional mode.** Prefer `launch_widget.py` for offline GPU dictation.
This entry point does not read `config.json` (hotkey and language are fixed below).
"""

import io
import os
import sys
import threading

import keyboard
import numpy as np
import soundfile as sf
from openai import OpenAI

from core.audio import SAMPLE_RATE, Recorder
from core.config import load_or_create_config
from core.inject import paste_text
from core.text import format_transcript

HOTKEY = 'right ctrl'
LANGUAGE = 'tr'
MODEL = 'whisper-1'
API_KEY = os.environ.get('OPENAI_API_KEY', '')

client: OpenAI | None = None
recorder = Recorder()
_busy = False


def _log(msg: str) -> None:
    print(f"[rctrl] {msg}", flush=True)


def transcribe(audio: np.ndarray) -> str:
    """Upload the recording straight from memory and clean up the result."""
    if client is None:
        raise RuntimeError("OpenAI client is not initialised — main() must run first")
    buffer = io.BytesIO()
    sf.write(buffer, audio, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buffer.seek(0)

    kwargs: dict = {"model": MODEL, "file": ("audio.wav", buffer, "audio/wav")}
    if LANGUAGE:
        kwargs["language"] = LANGUAGE
    result = client.audio.transcriptions.create(**kwargs)
    return format_transcript(result.text.strip())


def _on_key_event(e) -> None:
    global _busy

    # Strict name check: keyboard reports name=None for some keys, and a
    # loose check would also fire on Left Ctrl.
    if not e.name or e.name.lower().strip() != HOTKEY:
        return

    if e.event_type == 'down':
        if _busy or recorder.active:
            return
        try:
            recorder.start()
        except Exception as ex:
            _log(f"✗  Microphone error: {ex}")
            return
        _log("🎙 Recording started... (release key to finish)")

    elif e.event_type == 'up':
        if not recorder.active:
            return
        audio, reason = recorder.stop()
        if audio is None:
            _log(f"  (skipped: {reason.value})")
            return
        _log(f"  Recording complete: {recorder.duration(audio):.1f}s")
        threading.Thread(target=_work, args=(audio,), daemon=True).start()


def _work(audio: np.ndarray) -> None:
    global _busy
    _busy = True
    try:
        _log("  Requesting transcription...")
        text = transcribe(audio)
        if text:
            preview = text[:70] + ('...' if len(text) > 70 else '')
            paste_text(text)
            _log(f'✓  "{preview}"')
        else:
            _log("  (empty transcription)")
    except Exception as ex:
        _log(f"✗  Error: {ex}")
    finally:
        _busy = False


def main() -> None:
    global client, HOTKEY, LANGUAGE

    cfg, _ = load_or_create_config()
    HOTKEY = cfg.get("hotkey", HOTKEY)
    LANGUAGE = cfg.get("language", LANGUAGE)

    if not API_KEY:
        print()
        print("ERROR: OPENAI_API_KEY environment variable not found.")
        print()
        print("Solution:")
        print("  Windows: set OPENAI_API_KEY=sk-...")
        print("  Permanent: setx OPENAI_API_KEY sk-...  (requires new terminal)")
        print()
        sys.exit(1)

    client = OpenAI(api_key=API_KEY)

    print()
    print("=" * 52)
    print("  R-Ctrl — Voice Typing (OpenAI Whisper)")
    print("=" * 52)
    print(f"  Hotkey   : {HOTKEY.upper()}")
    print(f"  Language : {LANGUAGE or 'auto'}")
    print(f"  Model    : {MODEL}")
    print()
    print("  Hold key -> Speak -> Release -> Paste text")
    print("  To exit: Ctrl+C")
    print("=" * 52)
    print()

    keyboard.hook(_on_key_event, suppress=False)

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        _log("Terminated.")


if __name__ == '__main__':
    main()
