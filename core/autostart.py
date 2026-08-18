"""Windows autostart via HKCU Run key (B-001)."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "R-Ctrl"


def supported() -> bool:
    return sys.platform == "win32"


def _open_run_key(access: int):
    import winreg

    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def _query_value(key, name: str):
    import winreg

    return winreg.QueryValueEx(key, name)


def _set_value(key, name: str, value: str) -> None:
    import winreg

    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _delete_value(key, name: str) -> None:
    import winreg

    winreg.DeleteValue(key, name)


def is_enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with _open_run_key(winreg.KEY_READ) as key:
            _query_value(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool, command: str | None = None) -> None:
    if not supported():
        return
    import winreg

    if enabled:
        if not command:
            raise ValueError("command is required when enabling autostart")
        with _open_run_key(winreg.KEY_SET_VALUE) as key:
            _set_value(key, VALUE_NAME, command)
    else:
        try:
            with _open_run_key(winreg.KEY_SET_VALUE) as key:
                _delete_value(key, VALUE_NAME)
        except OSError:
            pass


def default_launch_command(repo_root: Path | None = None) -> str:
    """Launch via the elevated batch file so global hotkeys keep working."""
    root = repo_root or Path(__file__).resolve().parent.parent
    bat = root / "scripts" / "Widget.bat"
    return f'"{bat}"'
