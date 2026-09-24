"""Provider registry: builds provider instances from configuration.

To add a provider, implement one of the interfaces in ``base.py`` and add it
to the relevant factory list below.
"""
from __future__ import annotations

from app.providers.anthropic_review import AnthropicReviewProvider
from app.providers.base import AIAnalysisProvider, LanguageAnalysisProvider, SimilarityProvider
from app.providers.external_http import HTTPAIDetectorProvider, HTTPSimilarityProvider
from app.providers.local import LocalLanguageProvider, LocalStylometricProvider
from app.providers.openai_review import OpenAIReviewProvider

# Test hooks: tests replace these lists with fakes.
_ai_overrides: list[AIAnalysisProvider] | None = None
_sim_overrides: list[SimilarityProvider] | None = None


def local_ai_provider() -> AIAnalysisProvider:
    return LocalStylometricProvider()


def external_ai_providers() -> list[AIAnalysisProvider]:
    """All external/LLM AI providers, configured or not (for status display)."""
    if _ai_overrides is not None:
        return list(_ai_overrides)
    return [HTTPAIDetectorProvider(), AnthropicReviewProvider(), OpenAIReviewProvider()]


def external_similarity_providers() -> list[SimilarityProvider]:
    if _sim_overrides is not None:
        return list(_sim_overrides)
    return [HTTPSimilarityProvider()]


def language_provider() -> LanguageAnalysisProvider:
    return LocalLanguageProvider()


def providers_status() -> list[dict]:
    """Public status list — contains no secrets."""
    items = [local_ai_provider().info() | {"category": "ai"}, language_provider().info() | {"category": "language"}]
    items += [p.info() | {"category": "ai"} for p in external_ai_providers()]
    items += [p.info() | {"category": "similarity"} for p in external_similarity_providers()]
    items.append(
        {"name": "local_similarity", "kind": "local", "configured": True, "status": "configured", "category": "similarity",
         "description": "Internal duplication + same-user document corpus (no internet search)."}
    )
    return items


def set_overrides(ai: list[AIAnalysisProvider] | None = None, sim: list[SimilarityProvider] | None = None) -> None:
    global _ai_overrides, _sim_overrides
    _ai_overrides, _sim_overrides = ai, sim
