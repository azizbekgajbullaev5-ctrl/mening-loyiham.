"""Registry of language profiles + a lightweight, dependency-free language detector.

To add a language: create ``<code>.py`` with a ``LanguageProfile`` and add it to
``PROFILES``. The detector uses script + stopword evidence, so a new profile
with a stopword list is detected automatically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.analyzers.languages.base import DEFAULT_BASELINES, LanguageProfile
from app.analyzers.languages.en import ENGLISH
from app.analyzers.languages.ru import RUSSIAN
from app.analyzers.languages.uz import UZBEK
from app.analyzers.text_utils import normalize, words_lower

# Fallback for unsupported languages: generic features only, LOW confidence cap.
GENERIC = LanguageProfile(
    code="unknown",
    name="Unknown / unsupported",
    script="mixed",
    max_confidence="low",
    reliability_note="Language not supported by a dedicated module; results are indicative only.",
    baselines=dict(DEFAULT_BASELINES),
)

PROFILES: dict[str, LanguageProfile] = {p.code: p for p in (UZBEK, RUSSIAN, ENGLISH)}

_CYR = re.compile(r"[а-яёА-ЯЁ]")
_UZ_CYR = re.compile(r"[ўқғҳЎҚҒҲ]")
_LAT = re.compile(r"[a-zA-Z]")
_UZ_LATIN_MARKERS = re.compile(r"\b\w*(?:o'|g')\w*|\b\w+(?:lar|ning|dagi|lari|ligi|ni|ga|dan|da)\b", re.IGNORECASE)


def get_profile(code: str | None) -> LanguageProfile:
    return PROFILES.get(code or "", GENERIC)


@dataclass
class LanguageGuess:
    code: str
    confidence: float
    scores: dict[str, float]


def detect_language(text: str) -> LanguageGuess:
    text = normalize(text)
    toks = words_lower(text)
    if len(toks) < 3:
        return LanguageGuess("unknown", 0.0, {})
    cyr = len(_CYR.findall(text))
    lat = len(_LAT.findall(text))
    total = cyr + lat or 1
    scores: dict[str, float] = {}
    for code, prof in PROFILES.items():
        script_share = (cyr if prof.script == "cyrillic" else lat) / total
        hits = sum(1 for t in toks if t in prof.stopwords)
        scores[code] = script_share * (hits / len(toks))
    # Uzbek-specific orthographic evidence separates it from English in Latin script.
    uz_marks = len(_UZ_LATIN_MARKERS.findall(text)) / len(toks)
    scores["uz"] = scores.get("uz", 0.0) + 0.5 * uz_marks * (lat / total)
    if _UZ_CYR.search(text) and cyr / total > 0.5:
        # Uzbek Cyrillic is not yet supported by a dedicated module.
        return LanguageGuess("unknown", 0.5, {"uz-Cyrl": 1.0, **scores})
    best = max(scores, key=scores.get)
    ordered = sorted(scores.values(), reverse=True)
    top, second = ordered[0], (ordered[1] if len(ordered) > 1 else 0.0)
    if top < 0.05:
        return LanguageGuess("unknown", 0.0, scores)
    conf = min(1.0, (top - second) / top + min(len(toks), 200) / 1000)
    return LanguageGuess(best, round(conf, 3), scores)


def detect_distribution(paragraphs: list[str]) -> tuple[str, float, dict[str, float]]:
    """Word-weighted language distribution over paragraphs -> (dominant, confidence, shares)."""
    weights: dict[str, float] = {}
    conf_acc: dict[str, float] = {}
    for p in paragraphs:
        n = len(words_lower(p))
        if n < 5:
            continue
        g = detect_language(p)
        weights[g.code] = weights.get(g.code, 0) + n
        conf_acc[g.code] = conf_acc.get(g.code, 0) + n * g.confidence
    total = sum(weights.values())
    if not total:
        return "unknown", 0.0, {}
    shares = {k: round(v / total, 4) for k, v in sorted(weights.items(), key=lambda kv: -kv[1])}
    dominant = next(iter(shares))
    confidence = round(shares[dominant] * conf_acc[dominant] / weights[dominant], 3)
    return dominant, confidence, shares
