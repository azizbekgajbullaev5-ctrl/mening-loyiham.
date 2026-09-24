"""Local similarity analysis (kept strictly separate from AI-likelihood).

Scope of the *local* analysis:
  * internal duplication — passages re-used elsewhere in the same document;
  * own-corpus similarity — overlap with the same user's earlier uploads
    (hashed fingerprints only, never other users' documents);
  * repeated phrases;
  * paraphrase indicators — passages with high meaning-level (TF-IDF) overlap
    but low verbatim overlap.
No internet or database search is performed locally. External similarity is
only reported when an external provider is actually configured.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.analyzers.text_utils import normalize, stable_hash64, words_lower

SHINGLE = 6
WINNOW_WINDOW = 4
REPEATED_PHRASE_MIN = 5
REPEATED_PHRASE_MAX = 9


@dataclass
class SimPassage:
    id: int
    section_order: int
    paragraph_start: int
    page: int | None
    text: str
    excluded: bool = False


@dataclass
class Match:
    match_type: str
    passage_id: int
    other_passage_id: int | None
    similarity: float
    matched_document_id: str | None = None
    matched_paragraph_index: int | None = None
    matched_page: int | None = None


@dataclass
class SimilarityOutcome:
    internal_coverage: float  # 0..100 share of words in internally duplicated passages
    corpus_coverage: float | None  # 0..100, None if not run
    overall: float  # 0..100 union of local coverage
    per_section: dict[int, float] = field(default_factory=dict)
    per_passage: dict[int, int] = field(default_factory=dict)  # passage id -> covered words
    matches: list[Match] = field(default_factory=list)
    paraphrases: list[Match] = field(default_factory=list)
    repeated_phrases: list[dict] = field(default_factory=list)


def _tokens(text: str) -> list[str]:
    return words_lower(normalize(text))


def shingles(tokens: list[str], stop: frozenset[str], k: int = SHINGLE) -> list[tuple[int, int]]:
    """(hash, start_token) for k-word shingles containing >=2 non-stopwords."""
    out = []
    for i in range(len(tokens) - k + 1):
        win = tokens[i : i + k]
        if sum(1 for t in win if t not in stop) >= 2:
            out.append((stable_hash64(" ".join(win)), i))
    return out


def winnow(hashes: list[int], w: int = WINNOW_WINDOW) -> set[int]:
    if len(hashes) <= w:
        return set(hashes)
    return {min(hashes[i : i + w]) for i in range(len(hashes) - w + 1)}


def fingerprints(passages: list[SimPassage], stop: frozenset[str]) -> list[tuple[int, int, int | None]]:
    """Winnowed fingerprints for storage: (hash, paragraph_index, page)."""
    out = []
    for p in passages:
        if p.excluded:
            continue
        hs = [h for h, _ in shingles(_tokens(p.text), stop)]
        out.extend((h, p.paragraph_start, p.page) for h in winnow(hs))
    return out


def analyze(
    passages: list[SimPassage],
    stop: frozenset[str],
    corpus_index: dict[int, list[tuple[str, int, int | None]]] | None = None,
    run_paraphrase: bool = True,
) -> SimilarityOutcome:
    toks = {p.id: _tokens(p.text) for p in passages}
    sh = {p.id: shingles(toks[p.id], stop) for p in passages if not p.excluded}
    total_words = sum(len(toks[p.id]) for p in passages if not p.excluded) or 1

    # ---- internal duplication
    by_hash: dict[int, list[int]] = defaultdict(list)
    for pid, lst in sh.items():
        for h in {h for h, _ in lst}:
            by_hash[h].append(pid)
    pos = {p.id: i for i, p in enumerate(passages)}
    covered: dict[int, set[int]] = defaultdict(set)  # passage -> covered token positions
    pair_hits: Counter = Counter()
    for pid, lst in sh.items():
        for h, start in lst:
            others = [o for o in by_hash[h] if o != pid and abs(pos[o] - pos[pid]) > 0]
            if others:
                covered[pid].update(range(start, start + SHINGLE))
                for o in others:
                    pair_hits[(min(pid, o), max(pid, o))] += 1
    matches: list[Match] = []
    for (a, b), hits in pair_hits.items():
        denom = max(1, min(len(sh.get(a, [])), len(sh.get(b, []))))
        sim = hits / denom / 2  # counted from both sides
        if sim >= 0.15 and hits >= 6:
            matches.append(Match("internal_duplicate", b, a, round(min(1.0, sim), 3)))

    internal_cov_words = sum(len(v) for v in covered.values())

    # ---- own-corpus (other documents of the same user)
    corpus_cov: dict[int, set[int]] = defaultdict(set)
    corpus_coverage = None
    if corpus_index is not None:
        doc_hits: dict[tuple[int, str, int], int] = Counter()
        doc_meta: dict[tuple[int, str, int], int | None] = {}
        for pid, lst in sh.items():
            for h, start in lst:
                if h in corpus_index:
                    corpus_cov[pid].update(range(start, start + SHINGLE))
                    for doc_id, para, page in corpus_index[h][:3]:
                        doc_hits[(pid, doc_id, para)] += 1
                        doc_meta[(pid, doc_id, para)] = page
        best: dict[tuple[int, str], tuple[int, int]] = {}
        for (pid, doc_id, para), hits in doc_hits.items():
            if hits > best.get((pid, doc_id), (0, 0))[0]:
                best[(pid, doc_id)] = (hits, para)
        for (pid, doc_id), (hits, para) in best.items():
            sim = len(corpus_cov[pid]) / max(1, len(toks[pid]))
            if hits >= 3:
                matches.append(
                    Match("cross_document", pid, None, round(min(1.0, sim), 3), doc_id, para, doc_meta[(pid, doc_id, para)])
                )
        corpus_coverage = 100 * sum(len(v) for v in corpus_cov.values()) / total_words

    union_words = 0
    per_passage: dict[int, int] = {}
    per_section_cov: dict[int, int] = defaultdict(int)
    per_section_tot: dict[int, int] = defaultdict(int)
    for p in passages:
        if p.excluded:
            continue
        c = len(covered.get(p.id, set()) | corpus_cov.get(p.id, set()))
        c = min(c, len(toks[p.id]))
        per_passage[p.id] = c
        union_words += c
        per_section_cov[p.section_order] += c
        per_section_tot[p.section_order] += len(toks[p.id])

    outcome = SimilarityOutcome(
        internal_coverage=round(100 * internal_cov_words / total_words, 2),
        corpus_coverage=round(corpus_coverage, 2) if corpus_coverage is not None else None,
        overall=round(100 * union_words / total_words, 2),
        per_section={s: round(100 * per_section_cov[s] / t, 2) for s, t in per_section_tot.items() if t},
        per_passage=per_passage,
        matches=sorted(matches, key=lambda m: -m.similarity),
        repeated_phrases=repeated_phrases(passages, toks, stop),
    )
    if run_paraphrase:
        outcome.paraphrases = paraphrase_candidates(passages, pair_hits, sh)
    return outcome


def repeated_phrases(passages: list[SimPassage], toks: dict[int, list[str]], stop: frozenset[str], top: int = 25) -> list[dict]:
    counts: Counter = Counter()
    for p in passages:
        if p.excluded:
            continue
        t = toks[p.id]
        seen_here = set()
        for n in range(REPEATED_PHRASE_MIN, REPEATED_PHRASE_MAX + 1):
            for i in range(len(t) - n + 1):
                g = tuple(t[i : i + n])
                if sum(1 for x in g if x not in stop) >= 3 and g not in seen_here:
                    seen_here.add(g)
                    counts[g] += 1
    frequent = {g: c for g, c in counts.items() if c >= 3}
    # keep maximal phrases only
    # keep maximal phrases only; drop shifted windows of an already-kept phrase
    maximal = []
    for g, c in sorted(frequent.items(), key=lambda kv: (-len(kv[0]), -kv[1])):
        s = " ".join(g)
        gs = set(g)
        if any((s in " ".join(m) or len(gs & set(m)) >= 0.6 * len(gs)) and c <= mc for m, mc in maximal):
            continue
        maximal.append((g, c))
    maximal.sort(key=lambda gc: (-gc[1], -len(gc[0])))
    return [{"phrase": " ".join(g), "count": c} for g, c in maximal[:top]]


def paraphrase_candidates(passages: list[SimPassage], pair_hits: Counter, sh: dict, limit: int = 30) -> list[Match]:
    """High TF-IDF (char n-gram) cosine + low verbatim overlap => paraphrase indicator."""
    usable = [p for p in passages if not p.excluded and len(p.text) > 200]
    if len(usable) < 3:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:  # pragma: no cover
        return []
    texts = [re.sub(r"\d+", " ", normalize(p.text).lower()) for p in usable]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(4, 5), sublinear_tf=True, min_df=1, max_features=60000)
    X = vec.fit_transform(texts)
    sims = (X @ X.T).tocoo()
    out: list[Match] = []
    for i, j, v in zip(sims.row, sims.col, sims.data):
        if i >= j or v < 0.55:
            continue
        a, b = usable[i], usable[j]
        if abs(a.paragraph_start - b.paragraph_start) <= 1:
            continue
        hits = pair_hits.get((min(a.id, b.id), max(a.id, b.id)), 0)
        denom = max(1, min(len(sh.get(a.id, [])), len(sh.get(b.id, []))))
        verbatim = hits / denom / 2
        if verbatim < 0.2:
            out.append(Match("paraphrase", b.id, a.id, round(float(v), 3)))
    out.sort(key=lambda m: -m.similarity)
    return out[:limit]
