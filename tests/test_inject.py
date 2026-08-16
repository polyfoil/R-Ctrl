"""Tests for core.inject — clipboard-based text injection.

The widget used to overwrite the clipboard without restoring it, so the
restore behaviour is pinned down here explicitly.
"""

import pytest

from core import inject


class FakeClipboard:
    def __init__(self, initial=""):
        self.content = initial
        self.writes = []

    def copy(self, text):
        self.content = text
        self.writes.append(text)

    def paste(self):
        return self.content


class FakeKeyboard:
    def __init__(self):
        self.sent = []

    def send(self, combo):
        self.sent.append(combo)


@pytest.fixture
def env(monkeypatch):
    clip = FakeClipboard("kullanıcının önceki panosu")
    kb = FakeKeyboard()
    monkeypatch.setattr(inject, "pyperclip", clip)
    monkeypatch.setattr(inject, "keyboard", kb)
    monkeypatch.setattr(inject.time, "sleep", lambda _: None)
    return clip, kb


# --- clipboard restore ----------------------------------------------------

def test_previous_clipboard_is_restored(env):
    clip, _ = env
    inject.paste_text("merhaba")
    assert clip.content == "kullanıcının önceki panosu"


def test_restore_can_be_disabled(env):
    clip, _ = env
    inject.paste_text("merhaba", restore_clipboard=False)
    assert clip.content == "merhaba "


def test_text_is_on_clipboard_at_paste_time(env):
    clip, _ = env
    inject.paste_text("merhaba")
    # The pasted value must have been written before the restore.
    assert clip.writes[0] == "merhaba "
    assert clip.writes[-1] == "kullanıcının önceki panosu"


def test_ctrl_v_is_sent(env):
    _, kb = env
    inject.paste_text("merhaba")
    assert kb.sent == ["ctrl+v"]


# --- trailing space rules -------------------------------------------------

def test_trailing_space_is_appended(env):
    clip, _ = env
    inject.paste_text("merhaba", restore_clipboard=False)
    assert clip.content == "merhaba "


def test_newline_ending_gets_no_trailing_space(env):
    clip, _ = env
    inject.paste_text("merhaba\n", restore_clipboard=False)
    assert clip.content == "merhaba\n"


def test_bare_newline_is_preserved(env):
    clip, _ = env
    inject.paste_text("\n", restore_clipboard=False)
    assert clip.content == "\n"


def test_existing_trailing_whitespace_is_normalised(env):
    clip, _ = env
    inject.paste_text("merhaba   ", restore_clipboard=False)
    assert clip.content == "merhaba "


# --- guards ---------------------------------------------------------------

def test_empty_text_is_a_no_op(env):
    clip, kb = env
    assert inject.paste_text("") is False
    assert kb.sent == []
    assert clip.writes == []


def test_successful_paste_returns_true(env):
    assert inject.paste_text("merhaba") is True


def test_paste_returns_false_when_keyboard_fails(env, monkeypatch):
    def _boom(_combo):
        raise OSError("hook failed")

    monkeypatch.setattr(env[1], "send", _boom)
    assert inject.paste_text("merhaba") is False


def test_paste_survives_unreadable_clipboard(monkeypatch, env):
    clip, kb = env

    def _boom():
        raise RuntimeError("clipboard busy")

    monkeypatch.setattr(clip, "paste", _boom)
    # A clipboard read failure must not prevent the dictation from landing.
    assert inject.paste_text("merhaba") is True
    assert kb.sent == ["ctrl+v"]


def test_copy_to_clipboard_does_not_paste(env):
    clip, kb = env
    inject.copy_to_clipboard("geçmişten bir şey")
    assert clip.content == "geçmişten bir şey"
    assert kb.sent == []


def test_copy_to_clipboard_ignores_empty(env):
    clip, _ = env
    inject.copy_to_clipboard("")
    assert clip.writes == []


# --- call ordering --------------------------------------------------------
#
# Asserting outcomes is not enough here. Two of the four pre-refactor
# implementations waited between writing the clipboard and pressing Ctrl+V, and
# consolidation silently dropped that wait from all of them — an outcome-only
# test still passed, because a fake clipboard is instantly consistent. These
# tests pin the *sequence* instead, so a vanished delay breaks the build.

@pytest.fixture
def journal(monkeypatch):
    """Records clipboard, keyboard and sleep calls in the order they happen."""
    events = []

    class RecordingClipboard:
        content = "önceki pano"

        def copy(self, text):
            events.append(("copy", text))
            self.content = text

        def paste(self):
            events.append(("read",))
            return self.content

    class RecordingKeyboard:
        def send(self, combo):
            events.append(("paste", combo))

    monkeypatch.setattr(inject, "pyperclip", RecordingClipboard())
    monkeypatch.setattr(inject, "keyboard", RecordingKeyboard())
    monkeypatch.setattr(inject.time, "sleep", lambda s: events.append(("sleep", s)))
    return events


def _kinds(events):
    return [e[0] for e in events]


def test_clipboard_is_given_time_to_settle_before_pasting(journal):
    """Ctrl+V must not be sent in the same instant the clipboard is written.

    On Windows the target window learns about a clipboard change through the
    message loop; pressing Ctrl+V too early pastes the *previous* contents.
    """
    inject.paste_text("merhaba")
    kinds = _kinds(journal)
    copy_at = kinds.index("copy")
    paste_at = kinds.index("paste")
    assert "sleep" in kinds[copy_at:paste_at], (
        "a settle delay must sit between clipboard write and Ctrl+V"
    )


def test_full_call_sequence(journal):
    inject.paste_text("merhaba")
    assert _kinds(journal) == ["read", "copy", "sleep", "paste", "sleep", "copy"]


def test_settle_delay_is_long_enough_to_matter(journal):
    inject.paste_text("merhaba")
    pre_paste_sleeps = []
    for event in journal:
        if event[0] == "paste":
            break
        if event[0] == "sleep":
            pre_paste_sleeps.append(event[1])
    assert pre_paste_sleeps, "no delay before paste"
    assert max(pre_paste_sleeps) >= 0.03, "delay too small to survive a busy window"


def test_clipboard_restore_happens_after_the_paste(journal):
    inject.paste_text("merhaba")
    kinds = _kinds(journal)
    assert kinds.index("paste") < len(kinds) - 1
    assert journal[-1] == ("copy", "önceki pano")


def test_no_restore_write_when_restore_disabled(journal):
    inject.paste_text("merhaba", restore_clipboard=False)
    copies = [e for e in journal if e[0] == "copy"]
    assert copies == [("copy", "merhaba ")]
