# Contributing to R-Ctrl

## Widget work

Use `scripts\Widget.bat` or `python -m rctrl.launch` so CUDA loads before Qt.
Do not start from `python -m rctrl.widget`.

## Tests and lint

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements_widget.txt
python -m pytest
python -m ruff check .
python -m mypy
```

Add tests for logic you change. Coverage must stay at or above the
`fail_under` ratchet in `pyproject.toml`.

## Do not commit

`config.json`, `inbox.json`, `.pm/`, `Docs/`, `.cursor/`, release zips,
or the gitignored `R-Ctrl-Widget/` tree.

Paste injection only via `core.inject.paste_text()`. The server stays on
localhost unless you add auth and TLS.

## License

Contributions are accepted under the [MIT License](LICENSE).
