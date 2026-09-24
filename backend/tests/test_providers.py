"""External provider adapters: success, retries, failures, caching, comparison — never fabricated."""
import httpx
import pytest
from pydantic import SecretStr

from app.core import config
from app.providers import registry
from app.providers.base import AIAnalysisProvider, AIProviderResult, PassageInput, ProviderError
from app.providers.external_http import HTTPAIDetectorProvider, HTTPSimilarityProvider
from app.providers.resilience import with_retries
from tests.conftest import upload


@pytest.fixture
def detector_env(monkeypatch):
    s = config.get_settings()
    monkeypatch.setattr(s, "AI_DETECTOR_API_URL", "https://detector.test/v1/score")
    monkeypatch.setattr(s, "AI_DETECTOR_API_KEY", SecretStr("k"))
    monkeypatch.setattr(s, "AI_DETECTOR_RPM", 100000)
    return s


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_not_configured_provider_returns_no_scores():
    p = HTTPAIDetectorProvider()
    assert not p.is_configured()
    res = p.analyze([PassageInput(1, "text", "en", "h")])
    assert res[0].score is None and res[0].error == "not_configured"
    assert HTTPSimilarityProvider().check([]).error == "not_configured"


def test_detector_success_scale_and_cache(detector_env):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        assert req.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"ai_probability": 0.62})

    p = HTTPAIDetectorProvider(client=_client(handler))
    inp = [PassageInput(1, "some passage text", "en", "hash-success-1")]
    r1 = p.analyze(inp)[0]
    r2 = p.analyze(inp)[0]
    assert r1.score == 62.0 and not r1.cached
    assert r2.score == 62.0 and r2.cached and calls["n"] == 1  # cached: no second paid call


def test_detector_retries_on_429_then_succeeds(detector_env, monkeypatch):
    monkeypatch.setattr("app.providers.resilience.time.sleep", lambda s: None)
    seq = iter([httpx.Response(429, headers={"retry-after": "0"}), httpx.Response(503), httpx.Response(200, json={"ai_probability": 0.3})])
    p = HTTPAIDetectorProvider(client=_client(lambda req: next(seq)))
    assert p.analyze([PassageInput(1, "t", "en", "hash-retry-1")])[0].score == 30.0


def test_detector_failure_is_reported_not_fabricated(detector_env, monkeypatch):
    monkeypatch.setattr("app.providers.resilience.time.sleep", lambda s: None)
    p = HTTPAIDetectorProvider(client=_client(lambda req: httpx.Response(500)))
    r = p.analyze([PassageInput(1, "t", "en", "hash-fail-1")])[0]
    assert r.score is None and "500" in r.error
    p401 = HTTPAIDetectorProvider(client=_client(lambda req: httpx.Response(401)))
    assert p401.analyze([PassageInput(1, "t", "en", "hash-fail-2")])[0].score is None
    bad = HTTPAIDetectorProvider(client=_client(lambda req: httpx.Response(200, json={"other": 1})))
    assert bad.analyze([PassageInput(1, "t", "en", "hash-fail-3")])[0].error == "score field missing in response"


def test_with_retries_gives_up():
    n = {"c": 0}

    def fn():
        n["c"] += 1
        raise ProviderError("x", retryable=True, retry_after=0)

    with pytest.raises(ProviderError):
        with_retries(fn, max_retries=2, sleep=lambda s: None)
    assert n["c"] == 3


def test_similarity_provider_batches_and_sources(monkeypatch):
    s = config.get_settings()
    monkeypatch.setattr(s, "SIMILARITY_API_URL", "https://sim.test/check")
    monkeypatch.setattr(s, "SIMILARITY_API_KEY", SecretStr("k"))
    monkeypatch.setattr(s, "SIMILARITY_RPM", 100000)
    batches = []

    def handler(req):
        import json

        body = json.loads(req.content)
        batches.append(len(body["passages"]))
        return httpx.Response(200, json={"coverage": 10.0, "matches": [{"passage_id": body["passages"][0]["id"], "similarity": 0.9, "source_title": "Real Source", "source_url": "https://src.example/a"}]})

    p = HTTPSimilarityProvider(client=_client(handler))
    res = p.check([PassageInput(i, "word " * 10, "en", str(i)) for i in range(45)])
    assert batches == [20, 20, 5]
    assert res.coverage == 10.0 and len(res.sources) == 3 and res.sources[0].source_title == "Real Source"


class FakeDetector(AIAnalysisProvider):
    kind = "external"

    def __init__(self, name, score):
        self.name, self._score = name, score

    def analyze(self, passages):
        return [AIProviderResult(p.id, self._score) for p in passages]


class BrokenDetector(AIAnalysisProvider):
    kind = "external"
    name = "broken"

    def analyze(self, passages):
        return [AIProviderResult(p.id, None, error="HTTP 500") for p in passages]


def test_deep_analysis_compares_providers_transparently(user_client, samples):
    registry.set_overrides(ai=[FakeDetector("Provider A", 20.0), FakeDetector("Provider B", 95.0), BrokenDetector()])
    aid = upload(user_client, "deep.docx", samples["en.docx"], depth="deep")["analysis"]["id"]
    res = user_client.get(f"/api/analyses/{aid}", params={"lang": "en"}).json()["result"]
    comp = res["provider_comparison"]
    names = {p["name"]: p for p in comp["providers"]}
    assert names["Provider A"]["mean_score"] == 20.0 and names["Provider B"]["mean_score"] == 95.0
    assert names["broken"]["mean_score"] is None and names["broken"]["errors"] == ["HTTP 500"]
    assert comp["summary"] == "methods_vary"
    assert "should not treat any individual score as definitive" in comp["summary_text"]
    statuses = {p["name"]: p["status"] for p in res["providers"]}
    assert statuses["broken"] == "failed" and statuses["Provider A"] == "used"
    # the headline estimate remains the local one; provider scores are shown per passage
    passages = user_client.get(f"/api/analyses/{aid}/passages").json()
    assert any(ps["provider"] == "Provider B" for p in passages for ps in p["provider_scores"])


def test_standard_depth_never_calls_external(user_client, samples):
    class Exploding(AIAnalysisProvider):
        name, kind = "exploding", "external"

        def analyze(self, passages):
            raise AssertionError("external provider must not be called outside DEEP analysis")

    registry.set_overrides(ai=[Exploding()])
    aid = upload(user_client, "std.txt", samples["en.txt"], depth="standard")["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed"
    assert {p["name"]: p["status"] for p in a["result"]["providers"]}["exploding"] == "not_used_depth"
