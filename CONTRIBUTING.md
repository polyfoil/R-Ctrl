**Language / Dil:** **English** · [Türkçe](CONTRIBUTING.tr.md)

# Contributing

1. Use `launch_widget.py` / `rctrl_widget.bat` for widget work on Windows (CUDA before Qt).
2. Add or update tests for logic you touch; run `python -m pytest`, `python -m ruff check .`, `python -m mypy`.
3. Do not commit `config.json`, `inbox.json`, model caches, `.pm/`, `Docs/`, or zip bundles under `dist/`.
4. Do not edit `R-Ctrl-Widget/` — it is a gitignored legacy copy; work only in repo root sources.

### Behaviour constraints (summary)

- Text into apps: clipboard paste via `core.inject.paste_text()` only (not `keyboard.write()`).
- Audio path: 16 kHz mono float32 in memory; no temp WAV for local Whisper.
- Server must stay on `127.0.0.1` unless you add auth and TLS first.

Pull requests welcome; open an issue for large features first.

Documentation: [README.md](README.md) (English), [README.tr.md](README.tr.md) (Türkçe).
