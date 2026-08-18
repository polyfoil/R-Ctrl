**Language / Dil:** **English** · [Türkçe](README.tr.md)

# R-Ctrl — Whisperer (local)

**R-Ctrl — Whisperer** is local Windows dictation: hold a hotkey, speak, transcribe on your machine with **Whisper** (faster-whisper), and **paste** into the focused app. Default hotkey: **Right Ctrl** (`R-Ctrl`). Audio stays on-device; the widget needs no API key.

### Windows app (no Python install)

Download **`R-Ctrl-Whisperer-win64.zip`** from [GitHub Releases](https://github.com/polyfoil/R-Ctrl/releases), unzip, run **`Start-R-Ctrl-Whisperer.bat`** (UAC). First launch downloads the Whisper model (~3 GB). **CUDA Toolkit is not required.**

## Requirements

- **Windows 10/11**
- **End users (zip):** internet on first run; UAC for the global hotkey
- **Developers:** Python 3.11+; run `scripts\Widget.bat` (installs deps on first use, then UAC)

## Quick start

| Mode | Run |
|------|-----|
| **Widget** (primary) | `scripts\Widget.bat` → UAC → **R-Ctrl · Ready** |
| **Server** (browser) | `scripts\Server.bat` → http://127.0.0.1:5000 |

Widget usage:

- **Hold Right Ctrl** = push-to-talk; short tap = toggle
- **Click** capsule = start/stop recording
- **Right-click** = model, mic, language, history (`inbox.json`)
- **System tray** = show/hide and menu

### Entry points (developers)

| Use | Avoid |
|-----|--------|
| `python -m rctrl.launch` or `scripts\Widget.bat` | `python -m rctrl.widget` (Qt before CUDA) |
| `python -m rctrl.server` or `scripts\Server.bat` | Binding the server to `0.0.0.0` without auth/TLS |

`rctrl.launch` loads Whisper/CUDA before PyQt6.

### Model cache

```text
%USERPROFILE%\.cache\huggingface\hub
```

Optional: `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `HF_TOKEN`.

### Optional

```text
set RCTRL_NO_TRAY=1
scripts\Widget.bat
```

## Release zip (most users)

1. [Releases](https://github.com/polyfoil/R-Ctrl/releases) → `R-Ctrl-Whisperer-win64.zip`
2. Unzip, run **`Start-R-Ctrl-Whisperer.bat`** (UAC)
3. `config.json` / `inbox.json` next to the `.exe`; logs: `%LOCALAPPDATA%\R-Ctrl\widget.log`

GPU issues: set `"device": "cpu"`, `"model": "small"`, `"compute": "int8"` in `config.json`, or delete `config.json` and restart.

## Install from source

```bash
git clone <repo-url>
cd R-Ctrl
scripts\Widget.bat
```

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m mypy
```

The server saves transcriptions to `inbox.json` via **Save to Inbox** (no keystroke injection). Host stays **127.0.0.1**.

## Project layout

| Path | Role |
|------|------|
| `core/` | Audio, engine, config, inject, history — no Qt/FastAPI |
| `rctrl/` | App layer: `launch`, `widget`, `controller`, `inbox`, `server` |
| `ui/` | Branding and i18n strings |
| `scripts/` | `Widget.bat`, `Server.bat` |
| `tests/` | Unit and smoke tests |
| `packaging/` | PyInstaller spec, `build_widget.ps1` |
| `dist/` | Release output (gitignored); see `dist/README.md` |

Do not edit the gitignored `R-Ctrl-Widget/` folder (old zip copy).

## Contributing

1. Widget work: `scripts\Widget.bat` or `python -m rctrl.launch` (CUDA before Qt).
2. Add tests for logic you change; run `pytest`, `ruff check .`, `mypy`.
3. Do not commit `config.json`, `inbox.json`, `.pm/`, `Docs/`, or release zips.
4. Paste injection only via `core.inject.paste_text()`; server stays on localhost unless auth + TLS.

## Tests

```bash
python -m pytest
set RCTRL_E2E=1
python -m pytest -m slow
```

## Known limits

- Paste cannot be verified by Windows; clipboard fallback on failure.
- History menu row → paste; inbox (📥) row → copy.
- Windows only.

## License

MIT — see [LICENSE](LICENSE).
