"""Local (in-process) providers. Always available, no network calls."""
from __future__ import annotations

from app.analyzers.ai_likelihood import score_passage
from app.analyzers.languages.registry import PROFILES, detect_distribution, get_profile
from app.providers.base import AIAnalysisProvider, AIProviderResult, LanguageAnalysisProvider, PassageInput


class LocalStylometricProvider(AIAnalysisProvider):
    name = "local_stylometry"
    kind = "local"
    description = "Local multi-signal linguistic analysis (uz / ru / en profiles)."

    def analyze(self, passages: list[PassageInput]) -> list[AIProviderResult]:
        out = []
        for p in passages:
            s = score_passage(p.text, get_profile(p.language))
            out.append(
                AIProviderResult(
                    passage_id=p.id,
                    score=s.score,
                    confidence=s.confidence,
                    characteristics=[c["code"] for c in s.characteristics],
                )
            )
        return out


class LocalLanguageProvider(LanguageAnalysisProvider):
    name = "local_language_detector"
    kind = "local"
    description = "Script + stopword language identification for: " + ", ".join(PROFILES)

    def detect(self, paragraphs: list[str]) -> tuple[str, float, dict[str, float]]:
        return detect_distribution(paragraphs)
