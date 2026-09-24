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
from app.plagiarism import corpus, embeddings, templates
from app.plagiarism.fingerprint import K, WINNOW, shingles
from app.plagiarism.textnorm import canonical_stopwords, display_text, tokenize

EXCLUDE_SECTION_KINDS = {"references": "references", "toc": "toc", "title": "title"}
_QUOTE_RE = re.compile(r"«[^«»]{12,1500}»|“[^“”]{12,1500}”|„[^„“”]{12,1500}[“”]|\"[^\"]{12,1500}\"")
_CITE_AFTER_RE = re.compile(r"^\s*[,.;:]?\s*(\[\s*\d+[^\]]{0,30}\]|\([^()]{0,80}?(19|20)\d{2}[a-z]?[^()]{0,20}\)|\[\s*[A-ZА-ЯЁa-z][^\]]{0,60}\])")
_MATH_CHARS = set("=+−-*/^_∑∫√≈≠≤≥×÷±∞∂∆∇αβγδεθλμπσφω(){}[]|<>0123456789.,")


def _ref_module(d) -> str:
    """Reference documents harvested from OJS journals form their own module."""
    return "ojs" if d.source_type == "ojs" else "corpus"


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
    """A source found online in this check (web page, scholarly record, patent, legal act, …)."""

    url: str
    title: str
    hashes: set[int]
    module: str = "web"
    authors: str = ""
    year: int | None = None
    vectors: np.ndarray | None = None  # chunk embeddings (paraphrase / translation)
    language: str | None = None


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
    translated: np.ndarray | None = None  # cross-language (translated) part of ``paraphrase``
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
    enabled: set[str] | None = None,
    doc_language: str | None = None,
) -> tuple[Outcome, TokenStream]:
    """``exclude_own``: the user's documents that are copies of this one (never reported as sources).
    ``enabled``: module keys (see modules.py); None = legacy behaviour (corpus incl. OJS, own documents)."""
    s = get_settings()
    if enabled is None:
        enabled = ({"corpus", "ojs"} if use_corpus else set()) | ({"own"} if document is not None else set())
    use_corpus = bool({"corpus", "ojs"} & enabled)
    stream, exclusions = build_stream(blocks, sections)
    n = len(stream.canon)
    stop = canonical_stopwords()
    sh = shingles(stream.canon, stop)
    modules: dict = {"corpus": False, "own": False, "web": False, "paraphrase": False}
    corpus_modules = {"corpus", "ojs"} & enabled
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
            if _ref_module(d) not in corpus_modules:
                continue
            sources.append(Source(f"ref:{doc_id}", _ref_module(d), d.title, d.source_url or (f"https://doi.org/{d.doi}" if d.doi else None),
                                  d.authors, d.year, doc_id, d.doc_kind, covered=_cover_from_hits(n, hits)))
    if progress:
        progress("corpus")

    # ---- the user's own earlier documents
    if document is not None and sh and "own" in enabled:
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
        for ws in web_sources:
            modules[ws.module] = True
            hits = [(g, None) for h, g in sh if h in ws.hashes]
            if len(hits) >= 2:
                sources.append(Source(f"{ws.module}:{ws.url}", ws.module, ws.title or ws.url, ws.url, ws.authors, ws.year,
                                      covered=_cover_from_hits(n, hits)))

    verbatim_any = np.zeros(n, dtype=bool)
    for src in sources:
        verbatim_any |= src.covered

    # ---- paraphrase / semantic similarity against the corpus
    live = [ws for ws in web_sources or [] if ws.vectors is not None]
    if run_paraphrase and n >= 40 and (use_corpus or live):
        para = _paraphrase(db, stream, verbatim_any, sources, corpus_modules, live, doc_language, "translation" in enabled)
        if para is not None:
            modules["paraphrase"] = para
    if progress:
        progress("paraphrase")

    # ---- classify tokens
    min_words = s.PLAGIARISM_MIN_SOURCE_WORDS
    template = np.zeros(n, dtype=bool)
    template_matched = 0
    if "templates" in enabled and n:
        template, occurrences = templates.mask(stream.canon)
        before = np.zeros(n, dtype=bool)
        for src in sources:
            before |= src.covered
            src.covered &= ~template  # standard phrases are never "borrowed"
        template_matched = int((before & template).sum())
    sources = [src for src in sources if int(src.covered.sum()) >= min_words]
    matched_any = np.zeros(n, dtype=bool)
    para_any = np.zeros(n, dtype=bool)
    trans_any = np.zeros(n, dtype=bool)
    for src in sources:
        matched_any |= src.covered
        if src.paraphrase is not None:
            para_any |= src.paraphrase
        if src.translated is not None:
            trans_any |= src.translated
    if "templates" in enabled:
        modules["templates"] = {"occurrences": int(occurrences), "words": int(template.sum()), "excluded_from_borrowing": template_matched}
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
            "translation_words": int((src.translated & cov).sum()) if src.translated is not None else 0,
            "max_similarity": src.max_similarity,
        })
    # citation spans are attributed to the best matching source when there is one
    cit_owner = np.full(n, -1, dtype=np.int32)
    for idx, src in enumerate(sources[:60]):
        m = src.covered & citation & (cit_owner < 0)
        cit_owner[m] = idx

    spans = _spans(stream, borrowing, citation, para_any, owner, cit_owner, trans_any)
    modules["translation_share"] = pct(trans_any & borrowing)
    excluded_words = sum(exclusions.values())
    outcome = Outcome(
        checked_words=n, excluded_words=excluded_words, originality=originality_pct, borrowing=borrowing_pct, citation=citation_pct,
        paraphrase_share=pct(para_any & borrowing), sources=out_sources, spans=spans, exclusions=exclusions, modules=modules,
    )
    return outcome, stream


def _paraphrase(db: Session, stream: TokenStream, verbatim_any: np.ndarray, sources: list[Source],
                corpus_modules: set[str] | None = None, live: list[WebSource] | None = None,
                doc_language: str | None = None, translation: bool = False) -> dict | None:
    """Semantic matches (paraphrase) against reference-corpus chunk vectors and against online sources
    fetched in this check. A match with a source in another language is a *translation* (only when the
    translation module is on and a multilingual model is loaded: hash vectors cannot cross languages)."""
    s = get_settings()
    corpus_modules = {"corpus", "ojs"} if corpus_modules is None else corpus_modules
    live = live or []
    be = embeddings.get_backend()
    hash_backend = isinstance(be, embeddings.HashBackend)
    threshold = s.PARAPHRASE_THRESHOLD_HASH if hash_backend else s.PARAPHRASE_THRESHOLD_MODEL
    cross_ok = translation and not hash_backend
    doc_lang = doc_language if doc_language and doc_language != "unknown" else None

    def is_cross(lang: str | None) -> bool:
        return bool(doc_lang and lang and lang != "unknown" and lang != doc_lang)

    ids, centroids = corpus.vector_index.centroids(db) if corpus_modules else ([], None)
    if (centroids is None or not len(ids)) and not live:
        return None
    spans = embeddings.chunk_windows(stream.canon)
    spans = [(a, b) for a, b in spans if verbatim_any[a:b].mean() < 0.5 and not stream.cited[a:b].any()]
    if not spans:
        return {"backend": be.id, "chunks": 0, "matches": 0}
    source_words = stream.canon if hash_backend else stream.words
    q = be.encode([" ".join(source_words[a:b]) for a, b in spans])

    # ---- candidates: key -> (matrix loader, language)
    cand: dict[str, tuple] = {}
    if centroids is not None and len(ids):
        meta_rows = {r[0]: (r[1], r[2]) for r in db.execute(select(RefDocument.id, RefDocument.source_type, RefDocument.language)
                                                             .where(RefDocument.id.in_(ids)))}
        seg = max(1, len(q) // 20)
        seg_c = np.vstack([q[i : i + seg].mean(axis=0) for i in range(0, len(q), seg)])
        seg_c /= np.maximum(np.linalg.norm(seg_c, axis=1, keepdims=True), 1e-9)
        best = (seg_c @ centroids.T).max(axis=0)
        order = np.argsort(-best)
        chosen: list[int] = []
        per_lang: dict[str, int] = defaultdict(int)
        for i in order:
            st, lang = meta_rows.get(ids[i], ("upload", None))
            if ("ojs" if st == "ojs" else "corpus") not in corpus_modules:
                continue
            if is_cross(lang) and not cross_ok:
                continue
            # centroids of other-language documents score lower: give every language its own quota
            key_lang = lang or "?"
            if len(chosen) < s.PARAPHRASE_CANDIDATE_DOCS or (cross_ok and per_lang[key_lang] < 10):
                chosen.append(i)
                per_lang[key_lang] += 1
            if len(chosen) >= s.PARAPHRASE_CANDIDATE_DOCS * 2:
                break
        fp_docs = {src.ref_doc_id for src in sources if src.ref_doc_id}
        for i in chosen:
            cand[f"ref:{ids[i]}"] = ("ref", ids[i], meta_rows.get(ids[i], (None, None))[1])
        for d in fp_docs & set(ids):
            lang = meta_rows.get(d, (None, None))[1]
            if not (is_cross(lang) and not cross_ok):
                cand.setdefault(f"ref:{d}", ("ref", d, lang))
    live_by_key = {}
    for ws in live:
        if is_cross(ws.language) and not cross_ok:
            continue
        key = f"{ws.module}:{ws.url}"
        live_by_key[key] = ws
        cand[key] = ("live", key, ws.language)

    best_score = np.zeros(len(spans), dtype=np.float32)
    best_key: list[str | None] = [None] * len(spans)
    mats: dict[str, np.ndarray] = {}
    for key, (kind, ref, lang) in cand.items():
        if kind == "ref":
            _, mat = corpus.vector_index.chunk_vectors(db, [ref])
        else:
            mat = live_by_key[ref].vectors
        if mat is None or not len(mat) or mat.shape[1] != q.shape[1]:
            continue
        sims_doc = q @ mat.T
        idx = sims_doc.argmax(axis=1)
        sc = sims_doc[np.arange(len(q)), idx]
        if is_cross(lang):
            sc = sc - (s.TRANSLATION_THRESHOLD - threshold)  # compare against the cross-language threshold
        better = sc > best_score
        if better.any():
            mats[key] = mat
        best_score[better] = sc[better]
        for i in np.nonzero(better)[0]:
            best_key[i] = key

    # Windows are coarse (50 words, stride 25) and can spill into neighbouring paragraphs. Marking is
    # therefore verified per paragraph piece: every paragraph touched by a matching window is cut into
    # ~50-word pieces, and only pieces that are themselves similar to some chunk of that source are marked.
    n = len(stream.canon)
    block_tokens: dict[int, list[int]] = {}
    for i, b in enumerate(stream.block):
        block_tokens.setdefault(b, []).append(i)
    per_block: dict[int, dict[str, list[int]]] = {}
    for i, (a, b) in enumerate(spans):
        key = best_key[i]
        if not key or best_score[i] < threshold:
            continue
        for blk in set(stream.block[a:b]):
            per_block.setdefault(blk, {}).setdefault(key, []).append(i)
    by_key = {src.key: src for src in sources}
    new_refs = {cand[k][1] for m in per_block.values() for k in m if k not in by_key and cand[k][0] == "ref"}
    meta = {d.id: d for d in db.scalars(select(RefDocument).where(RefDocument.id.in_(list(new_refs))))} if new_refs else {}
    matches = translations = 0
    for blk in per_block:
        toks_all = np.array(block_tokens[blk])
        if len(toks_all) < 8 or verbatim_any[toks_all].mean() > 0.5:
            continue
        key, _wins = max(per_block[blk].items(), key=lambda kv: max(best_score[w] for w in kv[1]))
        kind, ref, lang = cand[key]
        cross = is_cross(lang)
        pieces = _pieces(toks_all)
        pv = be.encode([" ".join(source_words[j] for j in piece) for piece in pieces])
        piece_sims = (pv @ mats[key].T).max(axis=1)
        need = (s.TRANSLATION_THRESHOLD if cross else threshold) - 0.05
        good = [piece for piece, sc in zip(pieces, piece_sims) if sc >= need]
        if not good:
            continue
        toks = np.concatenate(good)
        sim = float(piece_sims.max())
        src = by_key.get(key)
        if src is None:
            if kind == "ref":
                d = meta.get(ref)
                if d is None:
                    continue
                src = Source(key, _ref_module(d), d.title, d.source_url or (f"https://doi.org/{d.doi}" if d.doi else None),
                             d.authors, d.year, ref, d.doc_kind, covered=np.zeros(n, dtype=bool))
            else:
                ws = live_by_key[ref]
                src = Source(key, ws.module, ws.title or ws.url, ws.url, ws.authors, ws.year, covered=np.zeros(n, dtype=bool))
            sources.append(src)
            by_key[key] = src
        if src.paraphrase is None:
            src.paraphrase = np.zeros(n, dtype=bool)
        region = np.zeros(n, dtype=bool)
        region[toks] = True
        region &= ~verbatim_any
        src.paraphrase |= region
        src.covered |= region
        if cross:
            if src.translated is None:
                src.translated = np.zeros(n, dtype=bool)
            src.translated |= region
            translations += 1
        src.max_similarity = round(max(src.max_similarity or 0.0, sim), 3)
        matches += 1
    return {"backend": be.id, "chunks": len(spans), "matches": matches, "translations": translations, "threshold": threshold,
            "translation": cross_ok, "translation_threshold": s.TRANSLATION_THRESHOLD if cross_ok else None,
            "candidates": len(cand)}


def _pieces(toks: np.ndarray, size: int = embeddings.WINDOW) -> list[np.ndarray]:
    """Consecutive pieces of about ``size`` tokens; a short tail is merged into the previous piece."""
    out = [toks[i : i + size] for i in range(0, len(toks), size)]
    if len(out) > 1 and len(out[-1]) < size // 2:
        tail = out.pop()
        out[-1] = np.concatenate([out[-1], tail])
    return out


def _spans(stream: TokenStream, borrowing, citation, para_any, owner, cit_owner, trans_any=None) -> list[list]:
    """[[block_index, char_start, char_end, source_index, cls]] with cls b=borrowed, p=paraphrase, t=translated, c=citation."""
    out: list[list] = []
    cur = None
    for i in range(len(stream.canon)):
        if citation[i]:
            key = (stream.block[i], int(cit_owner[i]), "c")
        elif borrowing[i]:
            cls = "t" if (trans_any is not None and trans_any[i]) else ("p" if para_any[i] else "b")
            key = (stream.block[i], int(owner[i]), cls)
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
