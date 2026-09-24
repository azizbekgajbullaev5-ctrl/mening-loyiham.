"""Optional LLM-assisted stylistic review using the Anthropic (Claude) API.

Experimental and opt-in (LLM_REVIEW_ENABLED=true + ANTHROPIC_API_KEY). An LLM's
judgement about AI authorship is itself an unvalidated estimate; it is shown
side by side with other methods and never merged into a single "truth".
Only the most suspicious passages are sent (DEEP analysis, budgeted by
EXTERNAL_MAX_PASSAGES), never the whole document.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.providers.base import AIAnalysisProvider, AIProviderResult, PassageInput
from app.providers.llm_prompt import SYSTEM_PROMPT, user_prompt
from app.providers.resilience import RateLimiter, cache_get, cache_put


class StyleAssessment(BaseModel):
    ai_likelihood: int = Field(ge=0, le=100)
    confidence: Literal["low", "medium", "high"]
    characteristics: list[str]
    explanation: str


class AnthropicReviewProvider(AIAnalysisProvider):
    kind = "llm"
    description = "LLM-assisted stylistic review via the Anthropic API (experimental)."

    def __init__(self, client=None):
        s = get_settings()
        self.model = s.ANTHROPIC_MODEL
        self.name = f"anthropic:{self.model}"
        self._key = s.ANTHROPIC_API_KEY.get_secret_value()
        self.enabled = s.LLM_REVIEW_ENABLED
        self.limiter = RateLimiter(s.LLM_RPM)
        self._client = client
        self._timeout = s.PROVIDER_TIMEOUT_SECONDS
        self._retries = s.PROVIDER_MAX_RETRIES

    def is_configured(self) -> bool:
        return bool(self.enabled and self._key)

    def _get_client(self):
        if self._client is None:
            import anthropic

            # The SDK retries 408/409/429/5xx and connection errors with backoff.
            self._client = anthropic.Anthropic(api_key=self._key, timeout=self._timeout, max_retries=self._retries)
        return self._client

    def analyze(self, passages: list[PassageInput]) -> list[AIProviderResult]:
        if not self.is_configured():
            return [AIProviderResult(p.id, None, error="not_configured") for p in passages]
        import anthropic

        client = self._get_client()
        out = []
        for p in passages:
            cached = cache_get(self.name, p.hash)
            if cached is not None:
                out.append(AIProviderResult(p.id, cached["score"], cached.get("confidence"), cached.get("characteristics", []), cached.get("explanation"), cached=True))
                continue
            self.limiter.wait()
            extra: dict = {}
            if self.model.startswith(("claude-opus-5", "claude-fable")):
                # Server-side fallback when a request is declined by a safety classifier.
                extra = {"extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"}, "extra_body": {"fallbacks": "default"}}
            try:
                response = client.messages.parse(
                    model=self.model,
                    max_tokens=2048,  # short JSON assessment
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt(p.text, p.language)}],
                    output_format=StyleAssessment,
                    **extra,
                )
            except anthropic.RateLimitError:
                out.append(AIProviderResult(p.id, None, error="rate_limited"))
                continue
            except anthropic.APIStatusError as exc:
                out.append(AIProviderResult(p.id, None, error=f"api_error_{exc.status_code}"))
                continue
            except anthropic.APIConnectionError:
                out.append(AIProviderResult(p.id, None, error="connection_error"))
                continue
            if response.stop_reason == "refusal" or response.parsed_output is None:
                out.append(AIProviderResult(p.id, None, error=f"no_result:{response.stop_reason}"))
                continue
            a: StyleAssessment = response.parsed_output
            result = {"score": float(a.ai_likelihood), "confidence": a.confidence, "characteristics": a.characteristics[:10], "explanation": a.explanation[:1000]}
            cache_put(self.name, p.hash, result)
            out.append(AIProviderResult(p.id, result["score"], a.confidence, result["characteristics"], result["explanation"]))
        return out
