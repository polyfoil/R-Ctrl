R-Ctrl — Whisperer (local) — Windows package
============================================

1. Unzip this folder anywhere (e.g. Desktop\R-Ctrl-Whisperer).
2. Double-click Start-R-Ctrl-Whisperer.bat and approve UAC (administrator).
   Or run R-Ctrl-Whisperer.exe the same way — admin is required for the hotkey.
3. First launch downloads the speech model from Hugging Face (up to ~3 GB).
   Cache: %USERPROFILE%\.cache\huggingface\hub
4. config.json and inbox.json are created next to the .exe on first use.

Logs (no console window): %LOCALAPPDATA%\R-Ctrl\widget.log

NVIDIA GPU recommended. Needs Windows 10/11.

Source & issues: see the GitHub repository README.
