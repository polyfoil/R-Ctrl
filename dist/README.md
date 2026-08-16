**Language / Dil:** **English** · [Türkçe](README.tr.md)

# Release artifacts (`dist/`)

This folder holds **local build output**, not source.

| Output | How |
|--------|-----|
| `R-Ctrl-Whisperer/` | Run `packaging\build_widget.ps1` (PyInstaller one-folder) |
| `R-Ctrl-Whisperer-win64.zip` | Same script; upload to **GitHub Releases** |

Zips and the `R-Ctrl-Whisperer/` tree are **gitignored**. Do not commit them.

End users: download the zip from Releases, unzip, run `Start-R-Ctrl-Whisperer.bat` (UAC).

Developers: clone the repo and use `setup_widget.bat` instead.
