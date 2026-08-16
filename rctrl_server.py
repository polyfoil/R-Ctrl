#!/usr/bin/env python3
"""R-Ctrl local server — browser dictation UI backed by the local GPU.

SECURITY: binds to localhost only (ADR-002). Transcriptions can be saved to the
shared inbox via POST /dictate — no keystroke injection. Do not change HOST to
"0.0.0.0" without token auth and TLS.
"""

import io
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import load_or_create_config
from core.engine import TranscriptionEngine
from core.history import append_item

HOST = "127.0.0.1"
PORT = 5000

# Roughly 12 minutes of 16 kHz 16-bit mono audio. Bodies are read into memory,
# so this cap is what stops a stray large upload from exhausting RAM.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

_engine: TranscriptionEngine | None = None


def _log(msg: str) -> None:
    print(f"[rctrl-server] {msg}", flush=True)


def _build_engine() -> TranscriptionEngine:
    config, hw = load_or_create_config()
    _log(hw["reason"])
    return TranscriptionEngine(
        model_size=config["model"],
        device=config["device"],
        compute=config["compute"],
        language=config.get("language"),
    )


def _load_model() -> None:
    if _engine is None:
        _log("No engine to load — lifespan did not run.")
        return
    _log(f"Loading model: {_engine.model_size}/{_engine.device} ...")
    ok, info = _engine.load()
    _log(f"Model ready: {info}" if ok else f"Model load failed: {info}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The engine is built here, not in main(): `uvicorn rctrl_server:app` never
    # calls main(), and a server that can never load a model is worse than one
    # that fails loudly. Every startup path goes through the lifespan.
    global _engine
    if _engine is None:
        _engine = _build_engine()
    threading.Thread(target=_load_model, daemon=True).start()
    yield
    if _engine is not None:
        _engine.release()


app = FastAPI(lifespan=lifespan)

# No CORS middleware on purpose: the UI is served from this same origin, so
# cross-origin access is never needed. The previous allow_origins=["*"] let any
# page the user visited reach these endpoints.


@app.get("/health")
def health():
    return {
        "ok": True,
        "ready": _engine is not None and _engine.ready,
        "model": _engine.model_size if _engine else None,
        "device": _engine.device if _engine else None,
    }


@app.post("/transcribe")
def transcribe(audio: UploadFile = File(...)):
    """Transcribe an uploaded WAV. Runs sync so FastAPI puts it on a worker
    thread — an async def here would block the event loop during inference."""
    if _engine is None or not _engine.ready:
        raise HTTPException(503, "Model is not ready yet, please wait")

    data = audio.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Audio exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if not data:
        raise HTTPException(400, "Empty upload")

    t0 = time.time()
    # Straight from memory — no temp file round-trip.
    text = _engine.transcribe(io.BytesIO(data))
    elapsed = round(time.time() - t0, 2)
    _log(f"{elapsed}s → {text[:70]}")
    return {"text": text, "elapsed": elapsed}


class DictateReq(BaseModel):
    text: str


@app.post("/dictate")
def dictate(req: DictateReq):
    """Store transcribed text in inbox.json (ADR-005 / B-022). No paste/inject."""
    if not append_item(req.text):
        return {"ok": False}
    _log(f"Inbox: {req.text[:60]}")
    return {"ok": True}


# Mounted last: StaticFiles at "/" swallows every path, so any route declared
# after this line would silently never match.
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def main() -> None:
    # The engine is intentionally NOT built here — the lifespan owns it, so
    # that `uvicorn rctrl_server:app` behaves identically to this entry point.
    print()
    print("=" * 58)
    print("  R-Ctrl Server — Browser Dictation (local only)")
    print("=" * 58)
    print(f"  Open     : http://localhost:{PORT}")
    print()
    print("  Bound to localhost only. Other devices on the network")
    print("  cannot reach this server — see the note at the top of")
    print("  rctrl_server.py before changing that.")
    print()
    print("  To stop: Ctrl+C")
    print("=" * 58)
    print()

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
