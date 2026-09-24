"""Optional LLM-assisted stylistic review using the OpenAI Chat Completions HTTP API.

Same contract and caveats as ``anthropic_review``: experimental, opt-in,
budgeted, and never treated as definitive.
"""
from __future__ import annotations

import json

import httpx

from app.core.config import get_settings
from app.providers.base import AIAnalysisProvider, AIProviderResult, PassageInput, ProviderError
from app.providers.external_http import _raise_for
from app.providers.llm_prompt import SYSTEM_PROMPT, user_prompt
from app.providers.resilience import RateLimiter, cache_get, cache_put, with_retries

_SCHEMA = {
    "type": "object",
    "properties": {
        "ai_likelihood": {"type": "integer", "minimum": 0, "maximum": 100},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "characteristics": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
    },
    "required": ["ai_likelihood", "confidence", "characteristics", "explanation"],
    "additionalProperties": False,
}


class OpenAIReviewProvider(AIAnalysisProvider):
    kind = "llm"
    description = "LLM-assisted stylistic review via the OpenAI API (experimental)."
    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.model = s.OPENAI_MODEL
        self.name = f"openai:{self.model}"
        self._key = s.OPENAI_API_KEY.get_secret_value()
        self.enabled = s.LLM_REVIEW_ENABLED
        self.limiter = RateLimiter(s.LLM_RPM)
        self.max_retries = s.PROVIDER_MAX_RETRIES
        self._client = client or httpx.Client(timeout=s.PROVIDER_TIMEOUT_SECONDS)

    def is_configured(self) -> bool:
        return bool(self.enabled and self._key)

    def _call(self, p: PassageInput) -> dict:
        self.limiter.wait()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(p.text, p.language)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {"name": "style_assessment", "schema": _SCHEMA, "strict": True}},
        }
        try:
            resp = self._client.post(self.endpoint, json=body, headers={"Authorization": f"Bearer {self._key}"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc.__class__.__name__}", retryable=True) from exc
        _raise_for(resp)
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    def analyze(self, passages: list[PassageInput]) -> list[AIProviderResult]:
        if not self.is_configured():
            return [AIProviderResult(p.id, None, error="not_configured") for p in passages]
        out = []
        for p in passages:
            cached = cache_get(self.name, p.hash)
            if cached is not None:
                out.append(AIProviderResult(p.id, cached["score"], cached.get("confidence"), cached.get("characteristics", []), cached.get("explanation"), cached=True))
                continue
            try:
                data = with_retries(lambda p=p: self._call(p), self.max_retries)
                result = {
                    "score": float(max(0, min(100, int(data["ai_likelihood"])))),
                    "confidence": str(data["confidence"]),
                    "characteristics": [str(c) for c in data.get("characteristics", [])][:10],
                    "explanation": str(data.get("explanation", ""))[:1000],
                }
            except ProviderError as exc:
                out.append(AIProviderResult(p.id, None, error=str(exc)))
                continue
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                out.append(AIProviderResult(p.id, None, error=f"bad response: {exc.__class__.__name__}"))
                continue
            cache_put(self.name, p.hash, result)
            out.append(AIProviderResult(p.id, result["score"], result["confidence"], result["characteristics"], result["explanation"]))
        return out
