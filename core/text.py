"""Transcript cleanup: hallucination filtering and light punctuation normalisation.

This module is the single source of truth for text post-processing. It has no
dependency on audio, Qt or the network, which makes it directly unit-testable.

Spoken punctuation macros ("nokta", "virgül", …) were removed: they broke natural
Turkish dictation. Whisper output is kept as words; users type punctuation or
let the model emit it when it does.
"""

import re

# Phrases Whisper invents during silence — mostly YouTube subtitle boilerplate.
HALLUCINATIONS = {
    "altyazı", "altyazı:", "altyazi", "altyazı m.k.", "altyazı m.k", "altyazi m.k.", "altyazı mk",
    "altyazı: m.k.", "altyazı: mehmet kaya", "izlediğiniz için teşekkürler",
    "izlediginiz icin tesekkurler", "abone olmayı unutmayın", "abone olmayi unutmayin",
    "beğenmeyi unutmayın", "hoşça kalın", "görüşmek üzere", "thank you for watching",
    "thanks for watching", "subtitles by", "translated by", "thank you",
    "alooo",
}

_TRIM_CHARS = " .!?:;-–—\"'"


def clean_hallucinations(text: str) -> str:
    """Return "" if the whole utterance is a known silence artefact."""
    cleaned = text.strip()
    lower = cleaned.lower().strip(_TRIM_CHARS)
    if lower in HALLUCINATIONS:
        return ""
    for h in HALLUCINATIONS:
        if lower.startswith(h + ".") or lower.startswith(h + ":"):
            return ""
    return cleaned


def format_transcript(text: str) -> str:
    """Apply the full cleanup chain to a raw transcript."""
    cleaned = clean_hallucinations(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r'[ \t]*\n[ \t]*', '\n', cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+([.,!?:;])', r'\1', cleaned)
    cleaned = re.sub(r'([.?!,:;])([^\s\d.?!,:;\n])', r'\1 \2', cleaned)
    cleaned = re.sub(r'\(\s+', '(', cleaned)
    cleaned = re.sub(r'\s+\)', ')', cleaned)
    cleaned = cleaned.strip(' \t')
    if cleaned and cleaned[0].isalpha():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned
