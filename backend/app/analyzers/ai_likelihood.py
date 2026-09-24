"""Local, multi-signal AI-likelihood estimator.

This is a *stylometric* estimator: it measures properties that, in the
literature and in practice, tend to differ between LLM output and human
academic prose (low burstiness, formulaic phrasing, uniform discourse
patterns, low concrete specificity, ...). No single signal decides the
result, each signal is calibrated per language, and the output is an
estimate with a confidence label — never proof of authorship.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from app.analyzers.languages.base import LanguageProfile
from app.analyzers.text_utils import (
    CITATION_RE,
    NUMBER_RE,
    clip,
    cv,
    mattr,
    normalize,
    split_sentences,
    std,
    window_ttrs,
    words,
)

METHOD_VERSION = "local-stylometry-1.0"

# Relative importance of each signal. Documented in docs/methodology.md.
WEIGHTS: dict[str, float] = {
    "sentence_length_cv": 1.4,
    "generic_phrase_density": 1.6,
    "transition_start_ratio": 1.1,
    "opening_repetition": 0.6,
    "template_repetition": 0.8,
    "specificity_density": 1.3,
    "lexical_uniformity": 0.5,
    "triad_density": 0.5,
    "formalization_density": 0.4,
    "qualifier_density": 0.7,
    "paragraph_uniformity": 0.5,
    "style_shift": 0.6,
}

CONFIDENCE_ORDER = ["low", "medium", "high"]
_QUOTE_RE = re.compile(r"[«»“”\"]")
_PAREN_RE = re.compile(r"\([^()]{2,}\)")


@dataclass
class SectionContext:
    paragraph_length_cv: float | None = None


@dataclass
class PassageScore:
    score: float | None  # 0..100, None when the passage is too short to assess
    confidence: str
    characteristics: list[dict] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    subscores: dict[str, float] = field(default_factory=dict)
    word_count: int = 0


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _starts_with_any(sentence: str, phrases: frozenset[str]) -> bool:
    s = sentence.lower().lstrip("\"'«“([ ")
    for p in phrases:
        if s.startswith(p) and (len(s) == len(p) or not s[len(p)].isalnum()):
            return True
    return False


def _shape(tok: str, stop: frozenset[str]) -> str:
    lt = tok.lower()
    return lt if lt in stop else "W"


def compute_features(text: str, profile: LanguageProfile, ctx: SectionContext | None = None) -> dict[str, float]:
    text = normalize(text)
    toks = words(text)
    n = len(toks)
    if n == 0:
        return {}
    lower = [t.lower() for t in toks]
    sents = [s for s in split_sentences(text, profile.abbreviations) if len(words(s)) >= 3]
    lens = [len(words(s)) for s in sents]
    f: dict[str, float] = {"word_count": n, "sentence_count": len(sents), "mean_sentence_length": (sum(lens) / len(lens)) if lens else 0.0}
    f["mattr"] = mattr(lower)

    if len(lens) >= 4:
        f["sentence_length_cv"] = cv(lens)
    rx = profile.generic_phrase_regex()
    if rx is not None:
        f["generic_phrase_density"] = len(rx.findall(text.lower())) / n * 100
    if len(sents) >= 3 and profile.transitions:
        f["transition_start_ratio"] = sum(_starts_with_any(s, profile.transitions) for s in sents) / len(sents)
    if len(sents) >= 4:
        firsts = [words(s)[0].lower() for s in sents]
        c = Counter(firsts)
        f["opening_repetition"] = sum(v for v in c.values() if v > 1) / len(firsts)
        shapes = []
        for s in sents:
            sh = [_shape(t, profile.stopwords) for t in words(s)]
            shapes.extend(tuple(sh[i : i + 4]) for i in range(len(sh) - 3) if sum(x != "W" for x in sh[i : i + 4]) >= 2)
        if len(shapes) >= 10:
            sc = Counter(shapes)
            f["template_repetition"] = sum(v for v in sc.values() if v > 1) / len(shapes)
    # concrete specificity: numbers, citations, parenthetical detail, quotes, proper names
    caps = 0
    for s in sents:
        ws = words(s)
        caps += sum(1 for w in ws[1:] if w[:1].isupper() and len(w) > 1)
    spec = (
        len(NUMBER_RE.findall(text))
        + 2 * len(CITATION_RE.findall(text))
        + len(_PAREN_RE.findall(text))
        + len(_QUOTE_RE.findall(text)) / 2
        + caps
    )
    f["specificity_density"] = spec / n * 100
    ttrs = window_ttrs(lower, 40)
    if len(ttrs) >= 3:
        f["lexical_uniformity"] = std(ttrs)
    if len(sents) >= 3:
        conj = re.escape(profile.conjunction_and)
        triads = re.findall(rf"\w+(?:\s\w+)?,\s+\w+(?:\s\w+)?,?\s+{conj}\s+\w+", text, flags=re.IGNORECASE)
        f["triad_density"] = len(triads) / len(sents)
    frx = profile.formal_regex()
    if frx is not None:
        f["formalization_density"] = sum(1 for t in lower if len(t) > 5 and frx.search(t)) / n * 100
    if profile.qualifiers:
        q = 0
        for t in lower:
            for p in profile.qualifiers:
                if (len(p) >= 5 and t.startswith(p)) or t == p:
                    q += 1
                    break
        f["qualifier_density"] = q / n * 100
    if ctx and ctx.paragraph_length_cv is not None:
        f["paragraph_uniformity"] = ctx.paragraph_length_cv
    return f


def subscores(features: dict[str, float], profile: LanguageProfile) -> dict[str, float]:
    out = {}
    for name, base in profile.baselines.items():
        if name in features:
            z = base.direction * (features[name] - base.midpoint) / base.scale
            out[name] = _sigmoid(z)
    return out


def combine(subs: dict[str, float]) -> float | None:
    usable = {k: v for k, v in subs.items() if k in WEIGHTS}
    if len(usable) < 3:
        return None
    tot = sum(WEIGHTS[k] for k in usable)
    return 100.0 * sum(WEIGHTS[k] * v for k, v in usable.items()) / tot


def confidence_for(score: float, subs: dict[str, float], n_words: int, profile: LanguageProfile, is_ocr: bool = False) -> str:
    extremity = abs(score - 50)
    direction = 1 if score >= 50 else -1
    decisive = [v for v in subs.values() if abs(v - 0.5) > 0.15]
    agreement = (sum(1 for v in decisive if (v - 0.5) * direction > 0) / len(decisive)) if decisive else 0.0
    if n_words >= 150 and extremity >= 22 and agreement >= 0.75 and len(subs) >= 7:
        level = "high"
    elif n_words >= 80 and extremity >= 10 and agreement >= 0.6:
        level = "medium"
    else:
        level = "low"
    cap = profile.max_confidence
    if is_ocr:
        cap = "medium" if cap == "high" else cap
    return CONFIDENCE_ORDER[min(CONFIDENCE_ORDER.index(level), CONFIDENCE_ORDER.index(cap))]


def characteristics(subs: dict[str, float], features: dict[str, float], threshold: float = 0.68) -> list[dict]:
    out = []
    for name, v in sorted(subs.items(), key=lambda kv: -kv[1]):
        if v >= threshold and name in WEIGHTS:
            out.append({"code": name, "strength": round(v, 3), "value": round(features.get(name, 0.0), 4)})
    return out


def score_passage(
    text: str, profile: LanguageProfile, ctx: SectionContext | None = None, is_ocr: bool = False
) -> PassageScore:
    feats = compute_features(text, profile, ctx)
    n = int(feats.get("word_count", 0))
    if n < 40:
        return PassageScore(None, "low", [], feats, {}, n)
    subs = subscores(feats, profile)
    score = combine(subs)
    if score is None:
        return PassageScore(None, "low", [], feats, subs, n)
    conf = confidence_for(score, subs, n, profile, is_ocr)
    return PassageScore(round(score, 1), conf, characteristics(subs, feats), feats, subs, n)


STYLE_KEYS = (
    "mean_sentence_length", "sentence_length_cv", "mattr", "transition_start_ratio", "generic_phrase_density",
    "specificity_density", "formalization_density", "qualifier_density",
)


def robust_stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    s = sorted(values)
    med = s[len(s) // 2]
    mad = sorted(abs(v - med) for v in s)[len(s) // 2] * 1.4826
    return med, (mad if mad > 1e-9 else (std(values) or 1.0))


def apply_style_shift(scores: list[PassageScore], profile: LanguageProfile) -> None:
    """Add a 'sudden style change' signal to passages that deviate from the document's own style.

    Only deviations towards the AI-like side increase the score, so a genuinely
    human passage inside an otherwise uniform document is not penalised.
    """
    valid = [s for s in scores if s.score is not None]
    if len(valid) < 6:
        return
    stats = {k: robust_stats([s.metrics[k] for s in valid if k in s.metrics]) for k in STYLE_KEYS}
    doc_median_score = robust_stats([s.score for s in valid])[0]
    for s in valid:
        zs = [abs(s.metrics[k] - m) / d for k, (m, d) in stats.items() if k in s.metrics]
        if not zs:
            continue
        z = sum(sorted(zs, reverse=True)[:4]) / min(4, len(zs))
        s.metrics["style_deviation"] = round(z, 3)
        if s.score > doc_median_score and z > 1.5:
            sub = clip(_sigmoid((z - 2.2) / 0.6))
            s.subscores["style_shift"] = sub
            new = combine(s.subscores)
            if new is not None:
                s.score = round(new, 1)
            s.characteristics = characteristics(s.subscores, {**s.metrics, "style_shift": z})
            s.confidence = confidence_for(s.score, s.subscores, s.word_count, profile)
