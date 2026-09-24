"""Language profile contract.

Each supported language provides its own profile: stopwords, discourse
markers, generic academic phrases, heading vocabulary, and baseline values for
the stylometric features. Adding a language = adding one profile module and
registering it in ``registry.py``. Nothing assumes that English-calibrated
values carry over to other languages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeatureBaseline:
    """Logistic mapping: sub-score = sigmoid(direction * (x - midpoint) / scale).

    ``direction`` = +1 when larger values are more AI-like, -1 when smaller are.
    """

    midpoint: float
    scale: float
    direction: int


@dataclass
class LanguageProfile:
    code: str
    name: str
    script: str  # "latin" | "cyrillic"
    # Highest confidence label the local detector may assign in this language.
    # Uzbek has no published, validated AI-text corpus, so it is capped.
    max_confidence: str = "high"
    reliability_note: str = ""
    stopwords: frozenset[str] = frozenset()
    transitions: frozenset[str] = frozenset()  # sentence-initial discourse markers
    generic_phrases: tuple[str, ...] = ()  # formulaic / generic academic phrasing
    qualifiers: tuple[str, ...] = ()  # vague intensifiers/qualifiers (prefix match)
    conjunction_and: str = "and"
    formal_suffix_regex: str = ""  # nominalisation endings (matched at word end)
    abbreviations: tuple[str, ...] = ()  # tokens ending with '.' that do not end a sentence
    chapter_patterns: tuple[str, ...] = ()
    section_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    academic_words: frozenset[str] = frozenset()
    baselines: dict[str, FeatureBaseline] = field(default_factory=dict)
    long_sentence_words: int = 40

    _compiled: dict = field(default_factory=dict, repr=False)

    def chapter_regex(self) -> list[re.Pattern]:
        if "chapter" not in self._compiled:
            self._compiled["chapter"] = [re.compile(p, re.IGNORECASE) for p in self.chapter_patterns]
        return self._compiled["chapter"]

    def formal_regex(self) -> re.Pattern | None:
        if "formal" not in self._compiled:
            self._compiled["formal"] = re.compile(self.formal_suffix_regex) if self.formal_suffix_regex else None
        return self._compiled["formal"]

    def generic_phrase_regex(self) -> re.Pattern | None:
        if "generic" not in self._compiled:
            if not self.generic_phrases:
                self._compiled["generic"] = None
            else:
                alts = sorted((re.escape(p) for p in self.generic_phrases), key=len, reverse=True)
                self._compiled["generic"] = re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)", re.IGNORECASE)
        return self._compiled["generic"]


# Shared defaults; profiles override where the language behaves differently.
DEFAULT_BASELINES: dict[str, FeatureBaseline] = {
    # coefficient of variation of sentence length (burstiness). Human academic
    # prose typically varies more than LLM output.
    "sentence_length_cv": FeatureBaseline(0.42, 0.08, -1),
    # formulaic phrases per 100 words
    "generic_phrase_density": FeatureBaseline(0.9, 0.45, +1),
    # share of sentences opening with a discourse marker
    "transition_start_ratio": FeatureBaseline(0.22, 0.08, +1),
    # share of sentences whose first word repeats another sentence's first word
    "opening_repetition": FeatureBaseline(0.30, 0.12, +1),
    # repetition of coarse sentence templates
    "template_repetition": FeatureBaseline(0.16, 0.07, +1),
    # concrete details (numbers, citations, parentheses, named entities) per 100 words
    "specificity_density": FeatureBaseline(3.2, 1.3, -1),
    # std of type-token ratio across windows (uniform vocabulary use)
    "lexical_uniformity": FeatureBaseline(0.045, 0.02, -1),
    # "A, B and C" enumerations per sentence
    "triad_density": FeatureBaseline(0.22, 0.12, +1),
    # nominalisation endings per 100 words
    "formalization_density": FeatureBaseline(9.0, 3.0, +1),
    # CV of paragraph lengths inside the section
    "paragraph_uniformity": FeatureBaseline(0.35, 0.12, -1),
    # vague intensifiers/qualifiers per 100 words
    "qualifier_density": FeatureBaseline(2.0, 0.9, +1),
}
