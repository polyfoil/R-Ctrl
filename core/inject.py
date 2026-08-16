"""Text injection into the focused window.

Injection is always clipboard paste (`pyperclip.copy` + Ctrl+V), never
`keyboard.write()`: only the clipboard round-trip preserves Turkish characters
reliably on Windows.
"""

import contextlib
import time

import keyboard
import pyperclip

# Windows delivers clipboard changes to the target window through its message
# loop. Pressing Ctrl+V in the same instant we write the clipboard can make a
# busy application paste the *previous* contents. `tests/test_inject.py` asserts
# the call ordering so this delay cannot quietly disappear again.
_CLIPBOARD_SETTLE_SEC = 0.05

# Give the target window time to service the paste before we put the user's
# original clipboard back.
_PASTE_SETTLE_SEC = 0.15


def paste_text(text: str, restore_clipboard: bool = True) -> bool:
    """Paste `text` into the focused window.

    Returns False for empty input or when clipboard/keyboard operations fail.
    When `restore_clipboard` is true the user's previous clipboard content is
    put back afterwards on success.
    """
    if not text:
        return False

    previous = None
    if restore_clipboard:
        with contextlib.suppress(Exception):
            previous = pyperclip.paste()

    to_paste = text if text.endswith("\n") else text.rstrip(' \t') + " "

    try:
        pyperclip.copy(to_paste)
        time.sleep(_CLIPBOARD_SETTLE_SEC)
        keyboard.send('ctrl+v')
        time.sleep(_PASTE_SETTLE_SEC)
    except Exception:
        return False

    if previous is not None:
        with contextlib.suppress(Exception):
            pyperclip.copy(previous)
    return True


def copy_to_clipboard(text: str) -> None:
    """Put text on the clipboard without pasting it anywhere."""
    if text:
        pyperclip.copy(text)
