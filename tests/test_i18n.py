"""Tests for ui.i18n."""

from ui.i18n import I18N, translate


def test_translate_falls_back_to_turkish():
    assert translate("xx", "ready") == I18N["tr"]["ready"]


def test_translate_english():
    assert translate("en", "ready") == "R-Ctrl · Ready"
