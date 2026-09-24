"""Canonical text form used for all plagiarism comparisons.

* Uzbek/Russian Cyrillic is transliterated to Latin, so a Latin-script text is
  matched against its Cyrillic-script source (and vice versa).
* Homoglyphs (Cyrillic "а" inside a Latin word, Latin "o" inside a Cyrillic
  word, ...) are mapped back to the word's dominant script *before*
  transliteration, so letter-swapping tricks do not hide borrowings.
* Invisible characters (zero-width spaces, joiners, BOM, soft hyphen) are removed.
* All apostrophe variants of Uzbek oʻ/gʻ/tutuq belgisi become "'".

Tokens keep their character offsets in the (display) text so matches can be
highlighted in the document viewer and the report.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

INVISIBLE = "​‌‍‎‏⁠⁡⁢⁣⁤﻿­᠎"
_INVISIBLE_RE = re.compile(f"[{INVISIBLE}]")
APOSTROPHES = "ʻʼ’‘`´ʹ′"

# Cyrillic letters that look like Latin ones (and back)
CYR_TO_LAT_LOOKALIKE = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
    "і": "i", "ј": "j", "ѕ": "s", "һ": "h",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "У": "Y",
    "І": "I", "Ј": "J", "Ѕ": "S",
}
LAT_TO_CYR_LOOKALIKE = {
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х", "k": "к", "m": "м", "t": "т", "b": "в", "h": "н",
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н", "O": "О", "P": "Р", "C": "С", "T": "Т", "X": "Х", "Y": "У",
}

# Uzbek Cyrillic -> Uzbek Latin (official 1995 alphabet); also covers Russian letters.
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
_LATIN_RE = re.compile(r"[a-zA-Z]")
_CYR_RE = re.compile(r"[а-яёА-ЯЁўқғҳЎҚҒҲіјѕһІЈЅ]")
WORD_RE = re.compile(r"[^\W\d_]+(?:['ʻʼ’‘`][^\W\d_]+)*", re.UNICODE)


def strip_invisible(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def fix_homoglyphs(word: str) -> str:
    """Map look-alike letters to the word's dominant script."""
    lat = len(_LATIN_RE.findall(word))
    cyr = len(_CYR_RE.findall(word))
    if lat and cyr:
        if cyr >= lat:
            return "".join(LAT_TO_CYR_LOOKALIKE.get(ch, ch) for ch in word)
        return "".join(CYR_TO_LAT_LOOKALIKE.get(ch, ch) for ch in word)
    return word


def translit_word(word: str) -> str:
    w = word.lower()
    if not _CYR_RE.search(w):
        return w
    return "".join(_TRANSLIT.get(ch, ch) for ch in w)


def canonical_word(word: str) -> str:
    word = unicodedata.normalize("NFC", word)
    for a in APOSTROPHES:
        word = word.replace(a, "'")
    return translit_word(fix_homoglyphs(word))


@dataclass
class Token:
    text: str  # canonical form
    start: int  # char offset in the display text
    end: int


def display_text(text: str) -> str:
    """Text as shown to the user: NFC, invisible characters removed, apostrophes unified."""
    text = unicodedata.normalize("NFC", strip_invisible(text))
    return text.translate({ord(a): "'" for a in APOSTROPHES})


def tokenize(display: str) -> list[Token]:
    return [Token(canonical_word(m.group(0)), m.start(), m.end()) for m in WORD_RE.finditer(display)]


def canonical_words(text: str) -> list[str]:
    return [t.text for t in tokenize(display_text(text))]


_canonical_stop_cache: frozenset[str] | None = None


def canonical_stopwords() -> frozenset[str]:
    global _canonical_stop_cache
    if _canonical_stop_cache is None:
        from app.analyzers.languages.registry import PROFILES

        words: set[str] = set()
        for p in PROFILES.values():
            words |= {canonical_word(w) for w in p.stopwords}
        _canonical_stop_cache = frozenset(words)
    return _canonical_stop_cache
