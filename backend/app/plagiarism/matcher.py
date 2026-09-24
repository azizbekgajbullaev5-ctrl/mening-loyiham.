"""Antiplagiat-style comparison: originality / borrowing / citation.

Sources:
  * reference corpus (winnowed fingerprints with positions),
  * the user's own earlier documents (winnowed fingerprints),
  * web pages found by the internet check (all shingles),
  * semantic (paraphrase) matches against reference-corpus chunk vectors.

Excluded from the percentages: reference list, TOC, title page, tables, formulas.
Quoted passages that carry a citation marker (or that match a source while
quoted) are counted as *citation*, not borrowing.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.document_processing.structure import Section
from app.document_processing.types import Block
from app.models import Document, DocumentFingerprint, RefDocument
from app.plagiarism import corpus, embeddings
from app.plagiarism.fingerprint import K, WINNOW, shingles
from app.plagiarism.textnorm import canonical_stopwords, display_text, tokenize

EXCLUDE_SECTION_KINDS = {"references": "references", "toc": "toc", "title": "title"}
_QUOTE_RE = re.compile(r"«[^«»]{12,1500}»|“[^“”]{12,1500}”|„[^„“”]{12,1500}[“”]|\"[^\"]{12,1500}\"")
_CITE_AFTER_RE = re.compile(r"^\s*[,.;:]?\s*(\[\s*\d+[^\]]{0,30}\]|\([^()]{0,80}?(19|20)\d{2}[a-z]?[^()]{0,20}\)|\[\s*[A-ZА-ЯЁa-z][^\]]{0,60}\])")
_MATH_CHARS = set("=+−-*/^_∑∫√≈≠≤≥×÷±∞∂∆∇αβγδεθλμπσφω(){}[]|<>0123456789.,")


def is_formula(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 400:
        return False
    compact = t.replace(" ", "")
    math = sum(1 for c in compact if c in _MATH_CHARS)
    letters_words = len(re.findall(r"[^\W\d_]{3,}", t))
    return ("=" in t or "∑" in t or "∫" in t) and math / max(1, len(compact)) > 0.35 and letters_words <= 6


@dataclass
class WebSource:
    url: str
    title: str
    hashes: set[int]


@dataclass
class Source:
    key: str
    module: str  # corpus | own | web | paraphrase
    title: str
    url: str | None = None
    authors: str = ""
    year: int | None = None
    ref_doc_id: str | None = None
    doc_kind: str | None = None
    covered: np.ndarray | None = None  # bool mask over checked tokens
    paraphrase: np.ndarray | None = None
    max_similarity: float | None = None


@dataclass
class Outcome:
    checked_words: int
    excluded_words: int
    originality: float
    borrowing: float
    citation: float
    paraphrase_share: float
    sources: list[dict]
    spans: list[list]
    exclusions: dict
    modules: dict = field(default_factory=dict)


@dataclass
class TokenStream:
    canon: list[str]
    block: list[int]
    start: list[int]
    end: list[int]
    words: list[str]
    quoted: np.ndarray
    cited: np.ndarray
    displays: dict[int, str]


def build_stream(blocks: list[Block], sections: list[Section]) -> tuple[TokenStream, dict]:
    excluded_idx: dict[int, str] = {}
    for s in sections:
        reason = EXCLUDE_SECTION_KINDS.get(s.kind)
        if reason:
            for i in range(s.start, s.end):
                excluded_idx[i] = reason
    exclusions = defaultdict(int)
    canon, blk, st, en, words, quoted, cited = [], [], [], [], [], [], []
    displays: dict[int, str] = {}
    for b in blocks:
        disp = display_text(b.text)
        toks = tokenize(disp)
        if b.kind == "table":
            exclusions["tables"] += len(toks)
            continue
        if b.index in excluded_idx:
            exclusions[excluded_idx[b.index]] += len(toks)
            continue
        if is_formula(disp):
            exclusions["formulas"] += max(1, len(toks))
            continue
        displays[b.index] = disp
        q_ranges = []
        for m in _QUOTE_RE.finditer(disp):
            has_cite = bool(_CITE_AFTER_RE.match(disp[m.end() : m.end() + 90]))
            q_ranges.append((m.start(), m.end(), has_cite))
        for t in toks:
            canon.append(t.text)
            blk.append(b.index)
            st.append(t.start)
            en.append(t.end)
            words.append(disp[t.start : t.end])
            q = next((r for r in q_ranges if r[0] <= t.start < r[1]), None)
            quoted.append(q is not None)
            cited.append(bool(q and q[2]))
    stream = TokenStream(canon, blk, st, en, words, np.array(quoted, dtype=bool), np.array(cited, dtype=bool), displays)
    return stream, dict(exclusions)


def _cover_from_hits(n: int, hits: list[tuple[int, int | None]]) -> np.ndarray:
    """Mark shingle hits and fill gaps between consistent neighbouring hits (winnowing leaves gaps)."""
    mask = np.zeros(n, dtype=bool)
    hits = sorted(hits)
    for i, (g, pos) in enumerate(hits):
        mask[g : g + K] = True
        if i + 1 < len(hits):
            g2, pos2 = hits[i + 1]
            gap = g2 - g
            # winnowing keeps >=1 hash in every window of WINNOW shingles, so a continuous copy has gaps <= WINNOW
            if 0 < gap <= WINNOW and (pos is None or pos2 is None or abs((pos2 - pos) - gap) <= 1):
                mask[g : g2 + K] = True
    return mask


def compare(
    db: Session,
    blocks: list[Block],
    sections: list[Section],
    document: Document | None = None,
    use_corpus: bool = True,
    web_sources: list[WebSource] | None = None,
    progress=None,
    run_paraphrase: bool = True,
    exclude_own: set[str] | frozenset[str] = frozenset(),
) -> tuple[Outcome, TokenStream]:
    """``exclude_own``: the user's documents that are copies of this one (never reported as sources)."""
    s = get_settings()
    stream, exclusions = build_stream(blocks, sections)
    n = len(stream.canon)
    stop = canonical_stopwords()
    sh = shingles(stream.canon, stop)
    modules: dict = {"corpus": False, "own": False, "web": False, "paraphrase": False}
    sources: list[Source] = []

    # ---- reference corpus
    if use_corpus and sh:
        modules["corpus"] = True
        found = corpus.lookup_hashes(db, [h for h, _ in sh])
        per_doc: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for h, g in sh:
            for doc_id, pos in found.get(h, ()):
                per_doc[doc_id].append((g, pos))
        docs = {d.id: d for d in db.scalars(select(RefDocument).where(RefDocument.id.in_([k for k, v in per_doc.items() if len(v) >= 2]))).all()} if per_doc else {}
        for doc_id, hits in per_doc.items():
            if doc_id not in docs:
                continue
            d = docs[doc_id]
            sources.append(Source(f"ref:{doc_id}", "corpus", d.title, d.source_url or (f"https://doi.org/{d.doi}" if d.doi else None),
                                  d.authors, d.year, doc_id, d.doc_kind, covered=_cover_from_hits(n, hits)))
    if progress:
        progress("corpus")

    # ---- the user's own earlier documents
    if document is not None and sh:
        modules["own"] = True
        hashes = list({h for h, _ in sh})
        per_own: dict[str, list[tuple[int, None]]] = defaultdict(list)
        g_by_hash: dict[int, list[int]] = defaultdict(list)
        for h, g in sh:
            g_by_hash[h].append(g)
        for i in range(0, len(hashes), 900):
            rows = db.execute(
                select(DocumentFingerprint.hash, DocumentFingerprint.document_id).where(
                    DocumentFingerprint.owner_id == document.owner_id, DocumentFingerprint.document_id != document.id,
                    DocumentFingerprint.hash.in_(hashes[i : i + 900]),
                )
            ).all()
            for h, doc_id in rows:
                if doc_id in exclude_own:
                    continue
                per_own[doc_id].extend((g, None) for g in g_by_hash[h])
        if per_own:
            names = dict(db.execute(select(Document.id, Document.original_filename).where(Document.id.in_(list(per_own)))).all())
            for doc_id, hits in per_own.items():
                if len(hits) >= 2 and doc_id in names:
                    sources.append(Source(f"own:{doc_id}", "own", names[doc_id], covered=_cover_from_hits(n, list(set(hits)))))

    # ---- web pages
    if web_sources:
        modules["web"] = True
        for ws in web_sources:
            hits = [(g, None) for h, g in sh if h in ws.hashes]
            if len(hits) >= 2:
                sources.append(Source(f"web:{ws.url}", "web", ws.title or ws.url, ws.url, covered=_cover_from_hits(n, hits)))

    verbatim_any = np.zeros(n, dtype=bool)
    for src in sources:
        verbatim_any |= src.covered

    # ---- paraphrase / semantic similarity against the corpus
    if use_corpus and run_paraphrase and n >= 40:
        para = _paraphrase(db, stream, verbatim_any, sources)
        if para is not None:
            modules["paraphrase"] = para
    if progress:
        progress("paraphrase")

    # ---- classify tokens
    min_words = s.PLAGIARISM_MIN_SOURCE_WORDS
    sources = [src for src in sources if int(src.covered.sum()) >= min_words]
    matched_any = np.zeros(n, dtype=bool)
    para_any = np.zeros(n, dtype=bool)
    for src in sources:
        matched_any |= src.covered
        if src.paraphrase is not None:
            para_any |= src.paraphrase
    citation = stream.cited | (stream.quoted & matched_any)
    borrowing = matched_any & ~citation
    denom = max(1, n)
    pct = lambda m: round(100.0 * int(m.sum()) / denom, 2)  # noqa: E731
    borrowing_pct, citation_pct = pct(borrowing), pct(citation)
    originality_pct = round(max(0.0, 100.0 - borrowing_pct - citation_pct), 2)

    # ---- source shares: "in text" (overlapping) and "in report" (exclusive, greedy)
    sources.sort(key=lambda x: -int((x.covered & ~citation).sum()))
    claimed = np.zeros(n, dtype=bool)
    out_sources: list[dict] = []
    owner = np.full(n, -1, dtype=np.int32)
    for idx, src in enumerate(sources[:60]):
        cov = src.covered & ~citation
        excl = cov & ~claimed
        claimed |= cov
        owner[excl & (owner < 0)] = idx
        out_sources.append({
            "index": idx, "module": src.module, "title": src.title, "url": src.url, "authors": src.authors, "year": src.year,
            "ref_doc_id": src.ref_doc_id, "doc_kind": src.doc_kind,
            "share_text": pct(cov), "share_report": pct(excl), "words": int(cov.sum()),
            "paraphrase_words": int((src.paraphrase & cov).sum()) if src.paraphrase is not None else 0,
            "max_similarity": src.max_similarity,
        })
    # citation spans are attributed to the best matching source when there is one
    cit_owner = np.full(n, -1, dtype=np.int32)
    for idx, src in enumerate(sources[:60]):
        m = src.covered & citation & (cit_owner < 0)
        cit_owner[m] = idx

    spans = _spans(stream, borrowing, citation, para_any, owner, cit_owner)
    excluded_words = sum(exclusions.values())
    outcome = Outcome(
        checked_words=n, excluded_words=excluded_words, originality=originality_pct, borrowing=borrowing_pct, citation=citation_pct,
        paraphrase_share=pct(para_any & borrowing), sources=out_sources, spans=spans, exclusions=exclusions, modules=modules,
    )
    return outcome, stream


def _paraphrase(db: Session, stream: TokenStream, verbatim_any: np.ndarray, sources: list[Source]) -> dict | None:
    s = get_settings()
    ids, centroids = corpus.vector_index.centroids(db)
    if centroids is None or not len(ids):
        return None
    be = embeddings.get_backend()
    hash_backend = isinstance(be, embeddings.HashBackend)
    threshold = s.PARAPHRASE_THRESHOLD_HASH if hash_backend else s.PARAPHRASE_THRESHOLD_MODEL
    spans = embeddings.chunk_windows(stream.canon)
    spans = [(a, b) for a, b in spans if verbatim_any[a:b].mean() < 0.5 and not stream.cited[a:b].any()]
    if not spans:
        return {"backend": be.id, "chunks": 0, "matches": 0}
    source_words = stream.canon if hash_backend else stream.words
    q = be.encode([" ".join(source_words[a:b]) for a, b in spans])
    # candidate documents: centroid similarity of document segments + documents with fingerprint hits
    seg = max(1, len(q) // 20)
    seg_c = np.vstack([q[i : i + seg].mean(axis=0) for i in range(0, len(q), seg)])
    seg_c /= np.maximum(np.linalg.norm(seg_c, axis=1, keepdims=True), 1e-9)
    sims = seg_c @ centroids.T
    top = set(np.argsort(-sims.max(axis=0))[: s.PARAPHRASE_CANDIDATE_DOCS].tolist())
    same_backend = set(ids)  # vectors of another backend/dimension are never compared
    cand = ({ids[i] for i in top} | {src.ref_doc_id for src in sources if src.ref_doc_id}) & same_backend
    best_score = np.zeros(len(spans), dtype=np.float32)
    best_doc: list[str | None] = [None] * len(spans)
    best_vec = np.zeros_like(q)
    for doc_id in cand:
        _, mat = corpus.vector_index.chunk_vectors(db, [doc_id])
        if mat is None:
            continue
        sims_doc = q @ mat.T
        idx = sims_doc.argmax(axis=1)
        sc = sims_doc[np.arange(len(q)), idx]
        better = sc > best_score
        best_score[better] = sc[better]
        best_vec[better] = mat[idx[better]]
        for i in np.nonzero(better)[0]:
            best_doc[i] = doc_id

    # Windows are coarse (50 words) and can spill into neighbouring paragraphs. Marking is
    # therefore decided per paragraph: a paragraph touched by a matching window is marked only
    # if the paragraph's own text is similar enough to the matched source chunk.
    n = len(stream.canon)
    block_tokens: dict[int, list[int]] = {}
    for i, b in enumerate(stream.block):
        block_tokens.setdefault(b, []).append(i)
    per_block: dict[int, dict[str, list[int]]] = {}
    for i, (a, b) in enumerate(spans):
        doc_id = best_doc[i]
        if not doc_id or best_score[i] < threshold:
            continue
        for blk in set(stream.block[a:b]):
            per_block.setdefault(blk, {}).setdefault(doc_id, []).append(i)
    by_key = {src.ref_doc_id: src for src in sources if src.ref_doc_id}
    new_docs = {d for m in per_block.values() for d in m if d not in by_key}
    meta = {d.id: d for d in db.scalars(select(RefDocument).where(RefDocument.id.in_(list(new_docs))))} if new_docs else {}
    block_ids = list(per_block)
    block_vecs = be.encode([" ".join(source_words[j] for j in block_tokens[blk]) for blk in block_ids]) if block_ids else None
    matches = 0
    for k, blk in enumerate(block_ids):
        toks = np.array(block_tokens[blk])
        if len(toks) < 8 or verbatim_any[toks].mean() > 0.5:
            continue
        doc_id, wins = max(per_block[blk].items(), key=lambda kv: max(best_score[w] for w in kv[1]))
        sim = float(max(block_vecs[k] @ best_vec[w] for w in wins))
        if sim < threshold - 0.05:
            continue
        src = by_key.get(doc_id)
        if src is None:
            d = meta.get(doc_id)
            if d is None:
                continue
            src = Source(f"ref:{doc_id}", "corpus", d.title, d.source_url or (f"https://doi.org/{d.doi}" if d.doi else None),
                         d.authors, d.year, doc_id, d.doc_kind, covered=np.zeros(n, dtype=bool))
            sources.append(src)
            by_key[doc_id] = src
        if src.paraphrase is None:
            src.paraphrase = np.zeros(n, dtype=bool)
        region = np.zeros(n, dtype=bool)
        region[toks] = True
        region &= ~verbatim_any
        src.paraphrase |= region
        src.covered |= region
        src.max_similarity = round(max(src.max_similarity or 0.0, sim), 3)
        matches += 1
    return {"backend": be.id, "chunks": len(spans), "matches": matches, "threshold": threshold}


def _spans(stream: TokenStream, borrowing, citation, para_any, owner, cit_owner) -> list[list]:
    """[[block_index, char_start, char_end, source_index, cls]] with cls b=borrowed, p=paraphrase, c=citation."""
    out: list[list] = []
    cur = None
    for i in range(len(stream.canon)):
        if citation[i]:
            key = (stream.block[i], int(cit_owner[i]), "c")
        elif borrowing[i]:
            key = (stream.block[i], int(owner[i]), "p" if para_any[i] else "b")
        else:
            key = None
        if key and cur and cur[0] == key and cur[2] == i - 1:
            cur[1][2] = stream.end[i]
            cur[2] = i
        elif key:
            span = [stream.block[i], stream.start[i], stream.end[i], key[1], key[2]]
            out.append(span)
            cur = [key, span, i]
        else:
            cur = None
    return out
