"""Generic HTTP adapters for external AI-detection and similarity services.

These adapters speak a simple JSON contract so a legitimate third-party
service can be connected through configuration (or a thin custom subclass
that overrides ``build_request`` / ``parse_response``). They are inactive
unless both the URL and the API key are configured.

AI detector contract (default):
    POST {AI_DETECTOR_API_URL}
    {"text": "...", "language": "uz"}
    -> {"ai_probability": 0.73, ...}     # field name/scale configurable

Similarity contract (default):
    POST {SIMILARITY_API_URL}
    {"passages": [{"id": 1, "text": "...", "language": "uz"}]}
    -> {"coverage": 12.5,
        "matches": [{"passage_id": 1, "similarity": 0.82, "source_title": "...",
                     "source_url": "https://...", "matched_text": "..."}]}
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.providers.base import (
    AIAnalysisProvider,
    AIProviderResult,
    ExternalSource,
    PassageInput,
    ProviderError,
    SimilarityProvider,
    SimilarityProviderResult,
)
from app.providers.resilience import RateLimiter, cache_get, cache_put, with_retries


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code == 429 or resp.status_code >= 500:
        ra = resp.headers.get("retry-after")
        try:
            retry_after = float(ra) if ra else None
        except ValueError:
            retry_after = None
        raise ProviderError(f"HTTP {resp.status_code}", retryable=True, retry_after=retry_after)
    if resp.status_code >= 400:
        raise ProviderError(f"HTTP {resp.status_code}", retryable=False)


def _dig(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


class HTTPAIDetectorProvider(AIAnalysisProvider):
    kind = "external"
    description = "External AI-detection API (generic HTTP adapter)."

    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.name = s.AI_DETECTOR_NAME
        self.url = s.AI_DETECTOR_API_URL
        self._key = s.AI_DETECTOR_API_KEY.get_secret_value()
        self.score_field = s.AI_DETECTOR_SCORE_FIELD
        self.scale = s.AI_DETECTOR_SCORE_SCALE or 1.0
        self.limiter = RateLimiter(s.AI_DETECTOR_RPM)
        self.max_retries = s.PROVIDER_MAX_RETRIES
        self._client = client or httpx.Client(timeout=s.PROVIDER_TIMEOUT_SECONDS)

    def is_configured(self) -> bool:
        return bool(self.url and self._key)

    def build_request(self, p: PassageInput) -> dict:
        return {"text": p.text, "language": p.language}

    def parse_response(self, data: dict) -> float | None:
        v = _dig(data, self.score_field)
        if v is None:
            return None
        return max(0.0, min(100.0, float(v) * (100.0 / self.scale)))

    def _call(self, p: PassageInput) -> float | None:
        self.limiter.wait()
        try:
            resp = self._client.post(self.url, json=self.build_request(p), headers={"Authorization": f"Bearer {self._key}"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc.__class__.__name__}", retryable=True) from exc
        _raise_for(resp)
        return self.parse_response(resp.json())

    def analyze(self, passages: list[PassageInput]) -> list[AIProviderResult]:
        if not self.is_configured():
            return [AIProviderResult(p.id, None, error="not_configured") for p in passages]
        out = []
        for p in passages:
            cached = cache_get(self.name, p.hash)
            if cached is not None:
                out.append(AIProviderResult(p.id, cached.get("score"), cached=True))
                continue
            try:
                score = with_retries(lambda p=p: self._call(p), self.max_retries)
            except ProviderError as exc:
                out.append(AIProviderResult(p.id, None, error=str(exc)))
                continue
            except (ValueError, TypeError) as exc:
                out.append(AIProviderResult(p.id, None, error=f"bad response: {exc}"))
                continue
            if score is None:
                out.append(AIProviderResult(p.id, None, error="score field missing in response"))
                continue
            cache_put(self.name, p.hash, {"score": score})
            out.append(AIProviderResult(p.id, round(score, 1)))
        return out


class HTTPSimilarityProvider(SimilarityProvider):
    kind = "external"
    description = "External similarity/plagiarism API (generic HTTP adapter)."
    batch_size = 20

    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.name = s.SIMILARITY_API_NAME
        self.url = s.SIMILARITY_API_URL
        self._key = s.SIMILARITY_API_KEY.get_secret_value()
        self.limiter = RateLimiter(s.SIMILARITY_RPM)
        self.max_retries = s.PROVIDER_MAX_RETRIES
        self._client = client or httpx.Client(timeout=s.PROVIDER_TIMEOUT_SECONDS)

    def is_configured(self) -> bool:
        return bool(self.url and self._key)

    def _call(self, batch: list[PassageInput]) -> dict:
        self.limiter.wait()
        body = {"passages": [{"id": p.id, "text": p.text, "language": p.language} for p in batch]}
        try:
            resp = self._client.post(self.url, json=body, headers={"Authorization": f"Bearer {self._key}"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc.__class__.__name__}", retryable=True) from exc
        _raise_for(resp)
        return resp.json()

    def check(self, passages: list[PassageInput]) -> SimilarityProviderResult:
        if not self.is_configured():
            return SimilarityProviderResult(None, [], error="not_configured")
        sources: list[ExternalSource] = []
        covered_words = 0.0
        coverage_reported = False
        total_words = sum(len(p.text.split()) for p in passages) or 1
        for i in range(0, len(passages), self.batch_size):
            batch = passages[i : i + self.batch_size]
            try:
                data = with_retries(lambda b=batch: self._call(b), self.max_retries)
            except ProviderError as exc:
                return SimilarityProviderResult(None, sources, error=str(exc))
            batch_words = sum(len(p.text.split()) for p in batch)
            cov = data.get("coverage")
            if isinstance(cov, (int, float)):
                coverage_reported = True
                covered_words += batch_words * float(cov) / 100
            for m in data.get("matches", []) or []:
                try:
                    sources.append(
                        ExternalSource(
                            passage_id=int(m["passage_id"]),
                            similarity=float(m.get("similarity", 0.0)),
                            source_title=m.get("source_title"),
                            source_url=m.get("source_url"),
                            matched_text=str(m.get("matched_text", ""))[:1000],
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
        coverage = round(100 * covered_words / total_words, 2) if coverage_reported else None
        return SimilarityProviderResult(coverage, sources)
