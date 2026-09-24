"""Tokenisation, sentence splitting and normalisation shared by all analyzers."""
from __future__ import annotations

import hashlib
import re
import unicodedata

# Uzbek Latin uses several apostrophe look-alikes for oʻ / gʻ / tutuq belgisi.
APOSTROPHES = "ʻʼ’‘`´ʹ′"
_APOS_TABLE = str.maketrans({c: "'" for c in APOSTROPHES})

WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*", re.UNICODE)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?%?")
CITATION_RE = re.compile(
    r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*(?:\s*[,;]\s*(?:p|pp|s|b|с|стр|bet)\.?\s*\d+(?:\s*[–-]\s*\d+)?)?\s*\]"
    r"|\((?:[^()]{0,80}?(?:19|20)\d{2}[a-z]?(?:[,;:]\s*(?:p|pp|s|с|b)\.?\s*\d+)?)\)",
    re.IGNORECASE,
)
_SENT_END_RE = re.compile(r"([.!?…]+)([\"'»”)\]]*)\s+(?=[\"'«“(\[]?[A-ZА-ЯЁЎҚҒҲ0-9])")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_APOS_TABLE)
    text = text.replace("­", "")  # soft hyphen
    return text


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def words(text: str) -> list[str]:
    return WORD_RE.findall(normalize(text))


def words_lower(text: str) -> list[str]:
    return [w.lower() for w in words(text)]


def split_sentences(text: str, abbreviations: tuple[str, ...] = ()) -> list[str]:
    """Rule-based sentence splitter with abbreviation and initials protection."""
    text = collapse_ws(normalize(text))
    if not text:
        return []
    abbr = {a.lower() for a in abbreviations}
    sentences: list[str] = []
    start = 0
    for m in _SENT_END_RE.finditer(text):
        end = m.end(2)
        candidate = text[start:end]
        last_token = candidate.rsplit(" ", 1)[-1].lower()
        # Initials ("A. Karimov") and known abbreviations do not end a sentence.
        if re.fullmatch(r"[^\W\d_]\.", last_token) or last_token in abbr:
            continue
        if any(candidate.lower().endswith(" " + a) for a in abbr if " " in a):
            continue
        sentences.append(candidate.strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return [s for s in sentences if WORD_RE.search(s)]


def sha256_text(text: str) -> str:
    return hashlib.sha256(collapse_ws(normalize(text)).lower().encode("utf-8")).hexdigest()


def stable_hash64(s: str) -> int:
    """Deterministic signed 64-bit hash (fits PostgreSQL BIGINT)."""
    h = int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")
    return h - (1 << 63)


def mattr(tokens: list[str], window: int = 50) -> float:
    """Moving-average type-token ratio (length-robust lexical diversity)."""
    if not tokens:
        return 0.0
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    vals = []
    step = max(1, window // 5)
    for i in range(0, len(tokens) - window + 1, step):
        seg = tokens[i : i + window]
        vals.append(len(set(seg)) / window)
    return sum(vals) / len(vals)


def window_ttrs(tokens: list[str], window: int = 40) -> list[float]:
    if len(tokens) < window * 2:
        return []
    return [len(set(tokens[i : i + window])) / window for i in range(0, len(tokens) - window + 1, window // 2)]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def cv(xs: list[float]) -> float:
    m = mean(xs)
    return std(xs) / m if m else 0.0


def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
