"""Tests for core.text — transcript cleanup without spoken punctuation macros."""

import pytest

from core.text import HALLUCINATIONS, clean_hallucinations, format_transcript

# --- hallucination filtering ---------------------------------------------

@pytest.mark.parametrize("phrase", [
    "altyazı",
    "altyazi",
    "altyazı m.k.",
    "altyazı: mehmet kaya",
    "izlediğiniz için teşekkürler",
    "abone olmayı unutmayın",
    "beğenmeyi unutmayın",
    "thank you for watching",
    "subtitles by",
    "alooo",
])
def test_known_hallucinations_are_dropped(phrase):
    assert clean_hallucinations(phrase) == ""


def test_hallucination_match_is_case_insensitive():
    assert clean_hallucinations("ALTYAZI") == ""
    assert clean_hallucinations("Thank You For Watching") == ""


def test_hallucination_match_ignores_surrounding_punctuation():
    assert clean_hallucinations("  altyazı!  ") == ""
    assert clean_hallucinations('"hoşça kalın"') == ""


def test_hallucination_prefix_with_colon_is_dropped():
    assert clean_hallucinations("altyazı: bir şeyler") == ""


def test_real_speech_survives():
    assert clean_hallucinations("bugün hava çok güzel") == "bugün hava çok güzel"


def test_word_containing_hallucination_is_not_dropped():
    assert clean_hallucinations("you should see this") == "you should see this"


def test_empty_input_returns_empty():
    assert clean_hallucinations("") == ""
    assert clean_hallucinations("   ") == ""


def test_widget_only_entries_are_present_everywhere_now():
    for phrase in ["beğenmeyi unutmayın", "altyazı: mehmet kaya", "alooo"]:
        assert phrase in HALLUCINATIONS


# --- spoken words stay literal (no voice-command macros) -------------------

@pytest.mark.parametrize("spoken", [
    "nokta",
    "virgül",
    "soru işareti",
    "ünlem",
    "noktalı virgül",
    "üç nokta",
    "tire",
    "iki nokta",
])
def test_punctuation_words_are_not_converted(spoken):
    assert format_transcript(spoken) == spoken.capitalize()


def test_natural_sentence_with_virgul_and_nokta():
    raw = "her virgül dediğimde bir şey olmamalı nokta"
    assert format_transcript(raw) == "Her virgül dediğimde bir şey olmamalı nokta"


def test_newline_phrase_stays_words():
    assert format_transcript("merhaba yeni satır dünya") == "Merhaba yeni satır dünya"


# --- punctuation and spacing ---------------------------------------------

def test_space_before_punctuation_is_removed():
    assert format_transcript("merhaba , dünya") == "Merhaba, dünya"


def test_space_after_punctuation_is_added():
    assert format_transcript("tamam.şimdi gidelim") == "Tamam. şimdi gidelim"


def test_decimal_numbers_keep_their_dot():
    assert format_transcript("değer 3.14 kadar") == "Değer 3.14 kadar"


def test_repeated_whitespace_collapses():
    assert format_transcript("çok    fazla     boşluk") == "Çok fazla boşluk"


def test_first_letter_is_capitalised():
    assert format_transcript("merhaba") == "Merhaba"


def test_leading_non_letter_is_left_alone():
    assert format_transcript("123 test") == "123 test"


def test_whitespace_around_newline_is_trimmed():
    assert format_transcript("bir\n   iki") == "Bir\niki"


# --- end to end -----------------------------------------------------------

def test_full_chain_keeps_spoken_punctuation_words():
    raw = "merhaba dünya virgül nasılsın soru işareti iyiyim nokta"
    assert format_transcript(raw) == "Merhaba dünya virgül nasılsın soru işareti iyiyim nokta"


def test_hallucination_short_circuits_the_whole_chain():
    assert format_transcript("altyazı m.k.") == ""


def test_empty_transcript_returns_empty():
    assert format_transcript("") == ""
    assert format_transcript("   \t  ") == ""
