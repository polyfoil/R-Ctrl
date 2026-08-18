**Language / Dil:** **English** · [Türkçe](README.tr.md)

# R-Ctrl — Whisperer (local)

**R-Ctrl — Whisperer** is local Windows dictation: hold a hotkey, speak, transcribe on your machine with **Whisper** (faster-whisper), and **paste** into the focused app. Default hotkey: **Right Ctrl** (`R-Ctrl`). Audio stays on-device; the widget needs no API key.

## Requirements

- **Windows 10/11**
- **Python 3.11+** (development tested on 3.13)
- **NVIDIA GPU** recommended (VRAM picks `large-v3` / `medium` / `small`; CPU falls back to `small`)
- First run downloads the model from **Hugging Face Hub** (up to **~3 GB**; no HF token required for public models)
- Run **`rctrl_widget.bat` as administrator (UAC)** for global hotkey and paste injection

## Quick start (widget — primary mode)

```text
setup_widget.bat    # once: dependencies
rctrl_widget.bat    # UAC → Yes
```

When the terminal shows `Model ready:`, the capsule reads **R-Ctrl · Ready**:

- **Hold Right Ctrl** = push-to-talk; short tap = toggle without holding
- **Click** the capsule = start/stop recording
- **Right-click** = model, microphone, language, history (`inbox.json`)
- **System tray** = double-click show/hide, right-click menu

### Correct entry point

| Use | Avoid |
|-----|--------|
| `rctrl_widget.bat` | `python rctrl_widget.py` (IDE Run) |
| `python launch_widget.py` | Two instances at once |

`rctrl_widget.bat` → `launch_widget.py`: loads Whisper/CUDA before PyQt6. A second launch exits with “already running”.

### Model cache

Weights are **not** stored in the repo. Default location:

```text
%USERPROFILE%\.cache\huggingface\hub
```

Optional: `HF_HOME` or `HUGGINGFACE_HUB_CACHE`. For rate limits or gated models, set `HF_TOKEN` or `huggingface-cli login`.

### Optional

```text
set RCTRL_NO_TRAY=1
rctrl_widget.bat
```

## Other modes

| Command | Description |
|---------|-------------|
| `setup_server.bat` + `rctrl_server.bat` | Browser UI: http://127.0.0.1:5000 (localhost only) |
| `setup.bat` + `rctrl.bat` | **Legacy** — OpenAI Whisper API (`OPENAI_API_KEY`) |

The server binds to **127.0.0.1**. Transcriptions are saved to `inbox.json` via **Save to Inbox** (no keystroke injection). **Do not bind to 0.0.0.0** without token auth and TLS.

## Download (recommended for most users)

1. Open **GitHub Releases** and download `R-Ctrl-Whisperer-win64.zip`.
2. Unzip anywhere (e.g. `Desktop\R-Ctrl-Whisperer`).
3. Run **`Start-R-Ctrl-Whisperer.bat`** and approve **UAC** (administrator — required for the global hotkey).
4. First launch downloads the Whisper model (up to ~3 GB). `config.json` and `inbox.json` appear **next to the `.exe`**.
5. Logs: `%LOCALAPPDATA%\R-Ctrl\widget.log` (no console window).

### GPU / CPU troubleshooting (release zip)

- **CUDA Toolkit is not required.** The app does not install NVIDIA CUDA Toolkit. First run only downloads the **Whisper model** from Hugging Face.
- **NVIDIA driver** is enough for GPU mode when the bundled runtime can use your card.
- If you see a CUDA or GPU error (or the app closes immediately), edit `config.json` next to the `.exe`:

```json
"model": "small",
"device": "cpu",
"compute": "int8"
```

- Or delete `config.json` and restart to re-detect hardware (CPU-only machines get this automatically).
- Always prefer **`Start-R-Ctrl-Whisperer.bat`** so UAC and logging work; check `widget.log` for details.
- Optional internal flag `gpu_auto_fallback` may appear after an automatic CPU downgrade; it is cleared when you pick a model from the menu or when CUDA works again on the next widget start.

Minimal CPU `config.json` (all keys the app understands):

```json
{
  "model": "small",
  "device": "cpu",
  "compute": "int8",
  "hotkey": "right ctrl",
  "language": null,
  "ui_language": "en",
  "input_device": null
}
```

Maintainers build the zip with `packaging\build_widget.ps1` (see `dist/README.md`).

## Install from source (developers)

```bash
git clone <repo-url>
cd R-Ctrl
setup_widget.bat
rctrl_widget.bat
```

Development:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m mypy
```

`config.json`, `inbox.json`, and model caches are gitignored.

## Project layout

| Path | Role |
|------|------|
| `core/` | Audio, engine, text, injection, history — no Qt/FastAPI |
| `launch_widget.py` | CUDA-first widget launcher |
| `rctrl_widget.py` | Capsule + tray + controller wiring |
| `rctrl_controller.py` | Qt-free dictation state machine |
| `rctrl_server.py` | Local HTTP dictation |
| `rctrl.py` | Optional cloud CLI |
| `tests/` | Unit and smoke tests |
| `dist/` | Release zip output (gitignored); see `dist/README.md` |
| `packaging/` | PyInstaller spec + `build_widget.ps1` |

### Do not use `R-Ctrl-Widget/`

That folder at the repo root is an **old / extracted zip copy** (gitignored). Edit only `launch_widget.py`, `rctrl_widget.py`, and `core/` here. Put release zips under `dist/` if needed.

## Tests

```bash
python -m pytest              # fast suite (excludes slow)
set RCTRL_E2E=1
python -m pytest -m slow        # real tiny Whisper + WAV path (downloads on first run)
```

Contributor guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## Known limits / roadmap

- If paste fails, text stays on the clipboard; the capsule warns; history is still saved.
- Windows cannot confirm paste landed in the target window — verify manually on success.
- **Dictation history** (context menu): clicking a row **pastes** (`paste_text`).
- **Dictation inbox** (📥): selecting a row **copies** to the clipboard; bulk copy joins lines with a single newline.
- Server `/dictate` entries reload from `inbox.json` when opening the widget menu or inbox.
- Broader integration: `RCTRL_E2E=1 pytest -m slow`.
- Presentation lives in `rctrl_widget.py`; logic in `rctrl_controller.py`.
- Windows only.

## License

MIT — see [LICENSE](LICENSE).
