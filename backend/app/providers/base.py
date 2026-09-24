"""Provider interfaces.

Every analysis source — local NLP, an external AI-detection API, an external
similarity service, an LLM reviewer — implements one of these interfaces.
Nothing in the pipeline is hard-wired to a specific vendor. A provider that
is not configured reports ``status="not_configured"`` and returns no scores:
results are never fabricated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PassageInput:
    id: int
    text: str
    language: str
    hash: str


@dataclass
class AIProviderResult:
    passage_id: int
    score: float | None  # 0..100 or None when unavailable
    confidence: str | None = None
    characteristics: list[str] = field(default_factory=list)
    explanation: str | None = None
    error: str | None = None
    cached: bool = False


@dataclass
class ExternalSource:
    passage_id: int
    similarity: float  # 0..1
    source_title: str | None
    source_url: str | None
    matched_text: str = ""


@dataclass
class SimilarityProviderResult:
    coverage: float | None  # 0..100 share of submitted text matched, None if unknown
    sources: list[ExternalSource] = field(default_factory=list)
    error: str | None = None


class ProviderInfoMixin:
    name: str = "provider"
    kind: str = "local"  # local | external | llm
    description: str = ""

    def is_configured(self) -> bool:
        return True

    def info(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "configured": self.is_configured(),
            "status": "configured" if self.is_configured() else "not_configured",
            "description": self.description,
        }


class AIAnalysisProvider(ProviderInfoMixin, ABC):
    #: languages the provider claims to support; None = any
    supported_languages: set[str] | None = None

    def supports(self, language: str) -> bool:
        return self.supported_languages is None or language in self.supported_languages

    @abstractmethod
    def analyze(self, passages: list[PassageInput]) -> list[AIProviderResult]:
        """Return one result per passage (same order). Must not raise for per-passage errors."""


class SimilarityProvider(ProviderInfoMixin, ABC):
    @abstractmethod
    def check(self, passages: list[PassageInput]) -> SimilarityProviderResult:
        """Compare passages against the provider's source database."""


class LanguageAnalysisProvider(ProviderInfoMixin, ABC):
    @abstractmethod
    def detect(self, paragraphs: list[str]) -> tuple[str, float, dict[str, float]]:
        """Return (dominant language code, confidence 0..1, distribution)."""


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
