# External providers (optional)

All providers implement interfaces in `backend/app/providers/base.py`:

| Interface | Purpose | Built-in implementations |
|---|---|---|
| `AIAnalysisProvider` | AI-likelihood per passage | `LocalStylometricProvider` (always on), `HTTPAIDetectorProvider`, `AnthropicReviewProvider`, `OpenAIReviewProvider` |
| `SimilarityProvider` | matches against a source database | `HTTPSimilarityProvider` (+ the always-on local similarity module) |
| `LanguageAnalysisProvider` | language identification | `LocalLanguageProvider` |

Registration happens in `backend/app/providers/registry.py`. To add a vendor, subclass the interface (or the
generic HTTP adapter and override `build_request` / `parse_response`) and add it to the factory list.

## Guarantees

* A provider without credentials reports `not_configured` and returns **no score**.
* Errors are recorded per provider (`failed`, with the error code) and shown to the user; nothing is
  substituted.
* External calls happen **only in DEEP analysis**, only for the `EXTERNAL_MAX_PASSAGES` most suspicious
  passages (by the local estimate) — never the whole dissertation in one request.
* Rate limiting (`*_RPM`), retries with exponential backoff honouring `Retry-After` for 429/5xx, and a
  result cache keyed by the SHA-256 of the passage (`provider_cache` table) keep costs down.
* Keys are read from environment variables on the server only; the frontend never sees them, and
  `/api/system/providers` returns names and status only.

## Generic AI detector contract

```
POST $AI_DETECTOR_API_URL
Authorization: Bearer $AI_DETECTOR_API_KEY
{"text": "...", "language": "uz"}

200 → {"ai_probability": 0.73}
```

`AI_DETECTOR_SCORE_FIELD` (dot path, e.g. `result.score`) and `AI_DETECTOR_SCORE_SCALE` (1 for 0–1, 100 for
0–100) adapt it to a real service. If the vendor uses a different request shape, subclass
`HTTPAIDetectorProvider`.

## Generic similarity contract

```
POST $SIMILARITY_API_URL
Authorization: Bearer $SIMILARITY_API_KEY
{"passages": [{"id": 1, "text": "...", "language": "uz"}]}          # batched, 20 per request

200 → {"coverage": 12.5,
       "matches": [{"passage_id": 1, "similarity": 0.82, "source_title": "...",
                    "source_url": "https://...", "matched_text": "..."}]}
```

Only sources returned by the API are displayed.

## LLM-assisted stylistic review (experimental)

Enabled only with `LLM_REVIEW_ENABLED=true` plus `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`. The model is
asked for a JSON assessment of stylistic characteristics (score, confidence, characteristics, explanation),
instructed not to rewrite text and to be conservative for Uzbek. An LLM's judgement about authorship is
itself unvalidated; it is shown as one more method, never as ground truth. The Anthropic adapter uses the
official SDK (`messages.parse` with a Pydantic schema) and enables server-side fallback on refusals.
