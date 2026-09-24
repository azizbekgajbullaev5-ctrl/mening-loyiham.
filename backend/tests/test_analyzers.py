import pytest

from app.analyzers import similarity as sim
from app.analyzers.academic import analyze_academic
from app.analyzers.ai_likelihood import WEIGHTS, apply_style_shift, score_passage
from app.analyzers.languages.registry import get_profile
from app.document_processing.structure import build_sections, detect_headings
from app.document_processing.types import Block
from tests.fixtures.sample_texts import SAMPLES


# ---------------------------------------------------------------- AI-likelihood scoring
@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_ai_style_scores_higher_than_human_style(lang):
    prof = get_profile(lang)
    human = [score_passage(t, prof).score for t in SAMPLES[lang]["human"]]
    ai = [score_passage(t, prof).score for t in SAMPLES[lang]["ai"]]
    assert all(s is not None and 0 <= s <= 100 for s in human + ai)
    assert min(ai) > max(human), (human, ai)
    assert sum(ai) / len(ai) - sum(human) / len(human) > 30


def test_score_is_not_driven_by_a_single_rule():
    """Long sentences alone must not make text 'AI-like'."""
    prof = get_profile("en")
    long_human = (
        "In the autumn of 2022 we visited 18 groups at three universities in Tashkent, and in only 7 of them were assignments marked "
        "before the final exam, which Karimov [3] had already described as a structural problem of workload allocation. "
    ) * 3
    s = score_passage(long_human, prof)
    assert s.score is not None and s.score < 60


def test_short_passage_is_not_scored():
    s = score_passage("Too short to assess reliably.", get_profile("en"))
    assert s.score is None and s.confidence == "low"


def test_uzbek_confidence_is_capped_at_medium():
    prof = get_profile("uz")
    text = " ".join(SAMPLES["uz"]["ai"] * 2)
    s = score_passage(text, prof)
    assert s.score > 60
    assert s.confidence in ("low", "medium")


def test_characteristics_are_explained_codes():
    s = score_passage(SAMPLES["en"]["ai"][0] + " " + SAMPLES["en"]["ai"][1], get_profile("en"))
    codes = {c["code"] for c in s.characteristics}
    assert codes and codes <= set(WEIGHTS)
    assert "generic_phrase_density" in codes


def test_style_shift_only_raises_ai_side():
    prof = get_profile("en")
    scores = [score_passage(t, prof) for t in SAMPLES["en"]["human"] * 2] + [score_passage(SAMPLES["en"]["ai"][0], prof)]
    before = [s.score for s in scores]
    apply_style_shift(scores, prof)
    for b, s in zip(before, scores):
        assert s.score >= b - 1e-6 or "style_shift" not in s.subscores


# ---------------------------------------------------------------- similarity
def _sp(i, text, section=0, excluded=False):
    return sim.SimPassage(i, section, i * 2, 1, text, excluded)


def test_internal_duplicate_detected():
    stop = get_profile("en").stopwords
    a = SAMPLES["en"]["human"][0]
    ps = [_sp(0, a), _sp(1, SAMPLES["en"]["human"][1]), _sp(2, SAMPLES["en"]["human"][2]), _sp(3, a)]
    out = sim.analyze(ps, stop, None)
    assert any(m.match_type == "internal_duplicate" and {m.passage_id, m.other_passage_id} == {0, 3} for m in out.matches)
    assert 40 <= out.internal_coverage <= 60
    assert out.corpus_coverage is None  # not run -> not fabricated


def test_no_similarity_for_distinct_text():
    stop = get_profile("en").stopwords
    ps = [_sp(i, t) for i, t in enumerate(SAMPLES["en"]["human"])]
    out = sim.analyze(ps, stop, None)
    assert out.overall == 0 and not [m for m in out.matches if m.match_type == "internal_duplicate"]


def test_cross_document_fingerprints():
    stop = get_profile("ru").stopwords
    other = [_sp(0, SAMPLES["ru"]["human"][1])]
    idx = {}
    for h, para, page in sim.fingerprints(other, stop):
        idx.setdefault(h, []).append(("doc-other", para, page))
    mine = [_sp(0, SAMPLES["ru"]["human"][0]), _sp(1, SAMPLES["ru"]["human"][1])]
    out = sim.analyze(mine, stop, idx)
    cross = [m for m in out.matches if m.match_type == "cross_document"]
    assert cross and cross[0].matched_document_id == "doc-other" and cross[0].passage_id == 1
    assert out.corpus_coverage > 30


def test_excluded_passages_not_counted():
    stop = get_profile("en").stopwords
    a = SAMPLES["en"]["human"][0]
    ps = [_sp(0, a), _sp(1, a, excluded=True)]
    assert sim.analyze(ps, stop, None).overall == 0


def test_repeated_phrases_and_paraphrase_candidates():
    stop = get_profile("en").stopwords
    ps = [_sp(i, t) for i, t in enumerate(SAMPLES["en"]["ai"] + SAMPLES["en"]["human"])]
    out = sim.analyze(ps, stop, None)
    assert isinstance(out.repeated_phrases, list)
    for m in out.paraphrases:
        assert m.match_type == "paraphrase" and 0.55 <= m.similarity <= 1.0


# ---------------------------------------------------------------- academic writing
def test_academic_citations_and_references():
    lines = [
        "INTRODUCTION",
        "Prior work [1] and later studies [2, 4] disagree; see also [9]. " * 3,
        "CONCLUSION",
        "We conclude with a summary of results in 2021.",
        "REFERENCES",
        "1. Author A. Title one. 2019.",
        "2. Author B. Title two. 2020.",
        "3. Author C. Title three.",
        "4. Author D. Title four. 2021.",
    ]
    blocks = [Block(i, t) for i, t in enumerate(lines)]
    sections = build_sections(detect_headings(blocks, "en"), len(blocks))
    res = analyze_academic(blocks, sections, get_profile("en"), "article")
    codes = {i["code"] for i in res["issues"]}
    assert res["citations"]["style"] == "numeric"
    assert res["citations"]["missing_references"] == [9]
    assert res["citations"]["uncited_references"] == [3]
    assert res["references"]["missing_year"] == [3]
    assert {"citation_without_reference", "uncited_references", "references_missing_year"} <= codes
    assert "missing_component" in codes  # article without abstract/methodology


def test_uzbek_apostrophe_variants_flagged():
    text = "O'zbekiston va oʻzbek tili, g'oya va gʻoya, o`quv jarayoni, o'quvchi, oʻquvchi, o'qituvchi."
    blocks = [Block(0, "KIRISH"), Block(1, text * 3)]
    sections = build_sections(detect_headings(blocks, "uz"), len(blocks))
    res = analyze_academic(blocks, sections, get_profile("uz"), "article")
    assert "mixed_apostrophes" in {i["code"] for i in res["issues"]}
